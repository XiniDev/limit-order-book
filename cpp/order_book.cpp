#include "order_book.hpp"

#include <algorithm>
#include <chrono>
#include <functional>
#include <stdexcept>


namespace lob {


using Clock = std::chrono::steady_clock;

// Return a monotonic timestamp in nanoseconds.
// Used for order and trade timestamps.
static std::int64_t now_ts() {
    auto now = Clock::now().time_since_epoch();
    return std::chrono::duration_cast<std::chrono::nanoseconds>(now).count();
}


// ============================================================================
// Public API (implementation only — documentation in .hpp)
// ============================================================================


OrderBook::OrderId OrderBook::addLimitOrder(
    Side side,
    Price price,
    Quantity quantity,
    std::optional<OrderId> order_id,
    std::optional<std::int64_t> ts_ns)
{
    OrderId id;
    if (!order_id) {
        id = nextFreeId();
    } else {
        id = *order_id;
        if (order_map_.find(id) != order_map_.end()) {
            throw std::invalid_argument(
                "Order ID" + std::to_string(id)
                + "already exists in the order book"
            );
        }
    }
    std::int64_t ts = ts_ns.value_or(now_ts());

    Order order{ id, side, price, quantity, ts };
    matchIncoming(order);

    if (order.quantity > 0) {
        addRestingOrder(order);
    }

    return id;
}


OrderBook::OrderId OrderBook::addMarketOrder(
    Side side,
    Quantity quantity,
    std::optional<OrderId> order_id,
    std::optional<std::int64_t> ts_ns)
{

    OrderId id;
    if (!order_id) {
        id = nextFreeId();
    } else {
        id = *order_id;
        if (order_map_.find(id) != order_map_.end()) {
            throw std::invalid_argument(
                "Order ID" + std::to_string(id)
                + "already exists in the order book"
            );
        }
    }
    std::int64_t ts = ts_ns.value_or(now_ts());

    Order order{ id, side, std::nullopt, quantity, ts };
    matchIncoming(order);

    return id;
}


bool OrderBook::cancelOrder(OrderId id) {
    auto it = order_map_.find(id);
    if (it == order_map_.end()) {
        return false;
    }

    const OrderInfo& info = it->second;
    Side side       = info.side;
    double price    = info.price;
    OrderNode* node = info.node;

    PriceMap& book_side = book(side);

    auto level_it = book_side.find(price);
    if (level_it == book_side.end()) {
        return false;
    }

    PriceLevel& level = level_it->second;

    // optimise later with cpp's built in doubly linked list - std::list
    OrderNode* prev = node->prev;
    OrderNode* next = node->next;

    if (prev) prev->next = next;
    else      level.head = next;

    if (next) next->prev = prev;
    else      level.tail = prev;
    // --

    if (!level.head) {
        book_side.erase(level_it);
    }

    order_map_.erase(it);
    delete node;
    return true;
}


std::optional<std::pair<OrderBook::Price, OrderBook::Quantity>>
OrderBook::bestBid() const
{
    auto price_opt = peekBestPrice(Side::Buy);
    if (!price_opt) return std::nullopt;

    Price price = *price_opt;
    const auto& book_side = book(Side::Buy);

    const PriceLevel &level = book_side.at(price);

    return { { price, sumLevelQuantity(level) } };
}

std::optional<std::pair<OrderBook::Price, OrderBook::Quantity>>
OrderBook::bestAsk() const
{
    auto price_opt = peekBestPrice(Side::Sell);
    if (!price_opt) return std::nullopt;

    Price price = *price_opt;
    const auto& book_side = book(Side::Sell);

    const PriceLevel &level = book_side.at(price);

    return { { price, sumLevelQuantity(level) } };
}


std::vector<std::pair<OrderBook::Price, OrderBook::Quantity>>
OrderBook::getDepth(Side side, std::size_t levels) const
{
    std::vector<std::pair<Price, Quantity>> result;

    const PriceMap& book_side = book(side);
    if (book_side.empty() || levels == 0) {
        return result;
    }

    std::vector<Price> prices;
    prices.reserve(book_side.size());
    for (const auto& kv : book_side) {
        prices.push_back(kv.first);
    }

    if (side == Side::Buy) {
        std::sort(prices.begin(), prices.end(), std::greater<Price>());
    } else {
        std::sort(prices.begin(), prices.end());
    }

    std::size_t count = std::min(levels, prices.size());
    result.reserve(count);

    for (std::size_t i = 0; i < count; ++i) {
        Price p = prices[i];
        const PriceLevel& level = book_side.at(p);
        result.emplace_back(p, sumLevelQuantity(level));
    }

    return result;
}


void OrderBook::clear() {
    // Free all OrderNode memory on both sides
    auto free_side = [](PriceMap& m) {
        for (auto& [price, level] : m) {
            OrderNode* node = level.head;
            while (node) {
                OrderNode* next = node->next;
                delete node;
                node = next;
            }
        }
        m.clear();
    };

    free_side(bids_);
    free_side(asks_);

    // Reset heaps by reassigning empty ones
    bid_heap_ = PriceQueue{};
    ask_heap_ = MinPriceQueue{};

    order_map_.clear();
    trades_.clear();
    next_order_id_ = 1;
}


// ============================================================================
// Internal Helpers
// ============================================================================


// Simple side selector
OrderBook::PriceMap& OrderBook::book(Side side) {
    return (side == Side::Buy) ? bids_ : asks_;
}


const OrderBook::PriceMap& OrderBook::book(Side side) const {
    return (side == Side::Buy) ? bids_ : asks_;
}


OrderBook::Quantity OrderBook::sumLevelQuantity(const PriceLevel& level) {
    Quantity total = 0;
    for (OrderNode* node = level.head; node; node = node->next) {
        total += node->order.quantity;
    }
    return total;
}


OrderBook::OrderId OrderBook::nextFreeId() {
    // Increment until an unused ID is found.
    while (order_map_.find(next_order_id_) != order_map_.end()) {
        ++next_order_id_;
    }
    return next_order_id_++;
}


void OrderBook::matchIncoming(Order& incoming) {
    // Check whether the incoming order crosses the best price.
    auto price_ok = [&](Price best_price) {
        if (!incoming.price) return true; // market order
        double limit = *incoming.price;
        return (incoming.side == Side::Buy) ? (best_price <= limit)
                                            : (best_price >= limit);
    };

    Side opp = opposite(incoming.side);
    PriceMap& opp_book = book(opp);

    while (incoming.quantity > 0) {
        auto best_price_opt = popBestPrice(opp);
        if (!best_price_opt) break;

        Price best_price = *best_price_opt;

        // No acceptable price
        if (!price_ok(best_price)) {
            pushPrice(best_price, opp);
            break;
        }

        auto lvl_it = opp_book.find(best_price);
        if (lvl_it == opp_book.end() || !lvl_it->second.head) {
            continue;
        }

        PriceLevel& level = lvl_it->second;

        // FIFO matching
        while (level.head && incoming.quantity > 0) {
            OrderNode* node = level.head;
            Order& resting = node->order;

            Quantity qty = std::min(incoming.quantity, resting.quantity);
            recordTrade(incoming, resting, best_price, qty);

            incoming.quantity -= qty;
            resting.quantity  -= qty;

            // Remove fully filled resting order
            if (resting.quantity == 0) {
                OrderNode* next = node->next;
                level.head = next;
                if (next) next->prev = nullptr;
                else      level.tail = nullptr;

                order_map_.erase(resting.order_id);
                delete node;
            }
        }

        // Remove empty price level
        if (!level.head) {
            opp_book.erase(best_price);
        } else {
            // Still liquidity; put price level back into heap
            pushPrice(best_price, opp);
        }
    }
}


void OrderBook::addRestingOrder(const Order& order) {
    if (!order.price) {
        throw std::runtime_error("Resting market orders are not supported");
    }

    Price p = *order.price;
    PriceMap& book_side = book(order.side);

    // Get or create new price level
    auto [it, created] = book_side.try_emplace(p, PriceLevel{});
    PriceLevel& level = it->second;

    if (created) {
        pushPrice(p, order.side);
    }

    // FIFO
    OrderNode* node = new OrderNode{order, nullptr, nullptr};

    if (!level.tail) {
        level.head = level.tail = node;
    } else {
        level.tail->next = node;
        node->prev = level.tail;
        level.tail = node;
    }

    order_map_[order.order_id] = OrderInfo{order.side, p, node};
}


void OrderBook::pushPrice(Price price, Side side) {
    // No reverse vs Python (heaps are already max and min)
    if (side == Side::Buy) bid_heap_.push(price);
    else                   ask_heap_.push(price);
}


std::optional<OrderBook::Price> OrderBook::peekBestPrice(Side side) const {
    auto* self = const_cast<OrderBook*>(this);
    PriceMap& book_side = self->book(side);

    if (side == Side::Buy) {
        while (!self->bid_heap_.empty()) {
            Price p = self->bid_heap_.top();

            auto it = book_side.find(p);
            if (it != book_side.end() && it->second.head != nullptr) {
                return p;
            }

            self->bid_heap_.pop();
        }
    } else {
        while (!self->ask_heap_.empty()) {
            Price p = self->ask_heap_.top();

            auto it = book_side.find(p);
            if (it != book_side.end() && it->second.head != nullptr) {
                return p;
            }

            self->ask_heap_.pop();
        }
    }

    return std::nullopt;
}


std::optional<OrderBook::Price> OrderBook::popBestPrice(Side side) {
    PriceMap& book_side = book(side);

    if (side == Side::Buy) {
        while (!bid_heap_.empty()) {
            Price p = bid_heap_.top();
            bid_heap_.pop();

            auto it = book_side.find(p);
            if (it != book_side.end() && it->second.head != nullptr) {
                return p;
            }
        }
    } else {
        while (!ask_heap_.empty()) {
            Price p = ask_heap_.top();
            ask_heap_.pop();

            auto it = book_side.find(p);
            if (it != book_side.end() && it->second.head != nullptr) {
                return p;
            }
        }
    }

    return std::nullopt;
}


void OrderBook::recordTrade(const Order& incoming,
                            const Order& resting,
                            Price price,
                            Quantity qty)
{
    // Determine correct buy/sell IDs based on trade direction
    std::int64_t buy_id =
        (incoming.side == Side::Buy) ? incoming.order_id : resting.order_id;

    std::int64_t sell_id =
        (incoming.side == Side::Sell) ? incoming.order_id : resting.order_id;

    trades_.push_back(Trade{
        buy_id,
        sell_id,
        price,
        qty,
        now_ts()
    });
}


} // namespace lob

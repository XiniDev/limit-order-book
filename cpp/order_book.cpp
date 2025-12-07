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
        if (order_map_.contains(id)) {
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
        if (order_map_.contains(id)) {
            throw std::invalid_argument(
                "Order ID" + std::to_string(id)
                + "already exists in the order book"
            );
        }
    }
    std::int64_t ts = ts_ns.value_or(now_ts());

    Order order{ id, side, price, quantity, ts };
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

    auto it = book_side.at(price);

    return { { price, sumLevelQuantity(it->second) } };
}

std::optional<std::pair<OrderBook::Price, OrderBook::Quantity>>
OrderBook::bestAsk() const
{
    auto price_opt = peekBestPrice(Side::Sell);
    if (!price_opt) return std::nullopt;

    Price price = *price_opt;
    const auto& book_side = book(Side::Sell);

    auto it = book_side.at(price);

    return { { price, sumLevelQuantity(it->second) } };
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
        const PriceLevel& level = side_book.at(p);
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
    while (order_map_.contains(next_order_id_)) {
        ++next_order_id_;
    }
    return next_order_id_++;
}

// NOT FINISHED


} // namespace lob

#include <iostream>
#include <optional>
#include <utility>
#include <vector>

#include "order_book.hpp"

using lob::OrderBook;
using lob::Side;

static const char* sideName(Side s) {
    return (s == Side::Buy) ? "BUY" : "SELL";
}

static void printBest(const char* label,
                      const std::optional<std::pair<OrderBook::Price, OrderBook::Quantity>>& x)
{
    std::cout << label << ": ";
    if (!x) {
        std::cout << "None\n";
        return;
    }
    std::cout << "(" << x->first << ", " << x->second << ")\n";
}

static void printDepth(const char* label,
                       const std::vector<std::pair<OrderBook::Price, OrderBook::Quantity>>& depth)
{
    std::cout << label << ": [";
    for (std::size_t i = 0; i < depth.size(); ++i) {
        if (i) std::cout << ", ";
        std::cout << "(" << depth[i].first << ", " << depth[i].second << ")";
    }
    std::cout << "]\n";
}

static void printTrades(const std::vector<lob::Trade>& trades) {
    std::cout << "\nTrades:\n";
    for (const auto& t : trades) {
        std::cout
            << "  Trade{buy=" << t.buy_order_id
            << ", sell=" << t.sell_order_id
            << ", price=" << t.price
            << ", qty=" << t.quantity
            << ", ts=" << t.timestamp
            << "}\n";
    }
}

int main() {
    OrderBook ob;

    // Resting orders
    ob.addLimitOrder(Side::Sell, 101.0, 100);
    ob.addLimitOrder(Side::Sell, 102.0, 200);
    ob.addLimitOrder(Side::Buy,   99.0, 150);
    ob.addLimitOrder(Side::Buy,   98.0, 250);

    printBest("Best bid", ob.bestBid());
    printBest("Best ask", ob.bestAsk());
    printDepth("Depth (bids)", ob.getDepth(Side::Buy));
    printDepth("Depth (asks)", ob.getDepth(Side::Sell));

    // Aggressive buy that crosses best ask
    ob.addLimitOrder(Side::Buy, 102.0, 180);

    std::cout << "\nAfter aggressive buy:\n";
    printBest("Best bid", ob.bestBid());
    printBest("Best ask", ob.bestAsk());

    printTrades(ob.trades());
    return 0;
}

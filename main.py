from order_book import Side, OrderBook

if __name__ == "__main__":
    ob = OrderBook()

    # resting orders
    ob.add_limit_order(Side.SELL, price=101.0, quantity=100)
    ob.add_limit_order(Side.SELL, price=102.0, quantity=200)
    ob.add_limit_order(Side.BUY, price=99.0, quantity=150)
    ob.add_limit_order(Side.BUY, price=98.0, quantity=250)

    print("Best bid:", ob.best_bid())
    print("Best ask:", ob.best_ask())
    print("Depth (bids):", ob.get_depth(Side.BUY))
    print("Depth (asks):", ob.get_depth(Side.SELL))

    # aggressive buy that crosses best ask
    ob.add_limit_order(Side.BUY, price=102.0, quantity=180)

    print("\nAfter aggressive buy:")
    print("Best bid:", ob.best_bid())
    print("Best ask:", ob.best_ask())

    print("\nTrades:")
    for t in ob.get_trades():
        print(t)

import pytest
from order_book import OrderBook, Side


def make_book() -> OrderBook:
    """
    Create a fresh order book for each test.
    """
    return OrderBook()


def test_no_crossing_no_trades():
    """
    Scenario:
    - Add a BUY at 99 and a SELL at 101.
    - Prices do NOT cross (99 < 101), so no trades should occur.
    """
    ob = make_book()
    ob.add_limit_order(Side.BUY, price=99.0, quantity=100)
    ob.add_limit_order(Side.SELL, price=101.0, quantity=200)

    assert ob.best_bid() == (99.0, 100)
    assert ob.best_ask() == (101.0, 200)

    assert ob.get_trades() == []


def test_empty_book_best_bid_ask_are_none():
    """
    Scenario:
    - On a completely empty book, best_bid() and best_ask() must return None.
    - This makes the API behaviour explicit for the empty state.
    - Then add crossing orders (BUY at 10.0, SELL at 9.0), book should still be empty.
    """
    ob = make_book()

    assert ob.best_bid() is None
    assert ob.best_ask() is None

    ob.add_limit_order(Side.BUY, price=10.0, quantity=50)
    ob.add_limit_order(Side.SELL, price=9.0, quantity=50)

    assert ob.best_bid() is None
    assert ob.best_ask() is None


def test_crossing_limit_sell():
    """
    Scenario:
    - Add a BUY at 10.0 for 100 units.
    - Then add a SELL at 9.5 for 100 units.
    - Prices cross and quantities match exactly -> one full trade.
    - Book should be empty after, trades recorded correctly (full quantity).
    """
    ob = make_book()

    buy_id = ob.add_limit_order(Side.BUY, price=10.0, quantity=100)
    sell_id = ob.add_limit_order(Side.SELL, price=9.5, quantity=100)

    assert ob.best_bid() is None
    assert ob.best_ask() is None

    trades = ob.get_trades()
    assert len(trades) == 1
    t = trades[0]

    assert t.buy_order_id == buy_id
    assert t.sell_order_id == sell_id
    assert t.price == pytest.approx(10.0)
    assert t.quantity == 100


def test_full_fill_crossing_limit_buy():
    """
    Scenario:
    - Add a SELL at 10.0 for 100 units.
    - Then add a BUY at 11.0 for 100 units.
    - Prices cross and quantities match exactly -> one full trade.
    - Book should be empty after, trades recorded correctly (full quantity).
    """
    ob = make_book()
    sell_id = ob.add_limit_order(Side.SELL, price=10.0, quantity=100)
    buy_id = ob.add_limit_order(Side.BUY, price=11.0, quantity=100)

    assert ob.best_bid() is None
    assert ob.best_ask() is None

    trades = ob.get_trades()
    assert len(trades) == 1
    t = trades[0]

    assert t.buy_order_id == buy_id
    assert t.sell_order_id == sell_id

    assert t.price == pytest.approx(10.0)
    assert t.quantity == 100


def test_partial_fill_limit_buy():
    """
    Scenario:
    - Add a SELL at 10.0 for 200 units.
    - Then add a BUY at 11.0 for 100 units.
    - Buy is fully filled; SELL is partially filled (100 left).
    - Book should show remaining SELL; trade recorded correctly.
    """
    ob = make_book()
    sell_id = ob.add_limit_order(Side.SELL, price=10.0, quantity=200)
    buy_id = ob.add_limit_order(Side.BUY, price=11.0, quantity=100)

    assert ob.best_bid() is None
    assert ob.best_ask() == (10.0, 100)

    trades = ob.get_trades()
    assert len(trades) == 1
    t = trades[0]

    assert t.buy_order_id == buy_id
    assert t.sell_order_id == sell_id
    assert t.price == pytest.approx(10.0)
    assert t.quantity == 100

def test_multi_level_fill():
    """
    Scenario:
    - Add SELL at 10.0 for 100 (s1).
    - Add SELL at 11.0 for 200 (s2).
    - Then add BUY at 11.0 for 250 (b).
    - Matching should:
      * First clear 10.0 (100 units from s1).
      * Then take 150 units from 11.0 (s2).
      * Leave 50 units at 11.0 on the ask side.
    """
    ob = make_book()
    s1 = ob.add_limit_order(Side.SELL, price=10.0, quantity=100)
    s2 = ob.add_limit_order(Side.SELL, price=11.0, quantity=200)

    b = ob.add_limit_order(Side.BUY, price=11.0, quantity=250)

    assert ob.best_bid() is None
    assert ob.best_ask() == (11.0, 50)

    trades = ob.get_trades()
    assert len(trades) == 2

    assert trades[0].sell_order_id == s1
    assert trades[0].buy_order_id == b
    assert trades[0].price == pytest.approx(10.0)
    assert trades[0].quantity == 100

    assert trades[1].sell_order_id == s2
    assert trades[1].buy_order_id == b
    assert trades[1].price == pytest.approx(11.0)
    assert trades[1].quantity == 150


def test_fifo_within_price_level():
    """
    Scenario:
    - Two SELLs at the same price 10.0: s1 then s2.
    - Add BUY at 11.0 for 150 units.
    - Matching should:
      * Fill all 100 of s1 first (FIFO).
      * Then take 50 from s2.
      * Leave 50 from s2 resting at 10.0.
    """
    ob = make_book()
    s1 = ob.add_limit_order(Side.SELL, price=10.0, quantity=100)
    s2 = ob.add_limit_order(Side.SELL, price=10.0, quantity=100)

    b = ob.add_limit_order(Side.BUY, price=11.0, quantity=150)

    trades = ob.get_trades()
    assert len(trades) == 2

    assert trades[0].sell_order_id == s1
    assert trades[0].buy_order_id == b
    assert trades[0].quantity == 100
    assert trades[0].price == pytest.approx(10.0)

    assert trades[1].sell_order_id == s2
    assert trades[1].buy_order_id == b
    assert trades[1].quantity == 50
    assert trades[1].price == pytest.approx(10.0)

    assert ob.best_ask() == (10.0, 50)
    assert ob.best_bid() is None


def test_cancel_unknown_order_returns_false():
    """
    Scenario:
    - Attempt to cancel an order_id that does not exist in the book.
    - cancel_order should return False and not throw.
    """
    ob = make_book()

    assert ob.cancel_order(9999) is False

    real_id = ob.add_limit_order(Side.BUY, price=10.0, quantity=100)
    assert ob.cancel_order(real_id + 1) is False

    assert ob.best_bid() == (10.0, 100)


def test_cancel_order_removes_correct_node():
    """
    Scenario:
    - Two SELLs at 10.0: s1 then s2 (FIFO queue).
    - Cancel s1.
    - Then add BUY at 11.0 for 150 units.
    - Matching should skip s1 entirely and only trade against s2.
    - Leave 50 units resting from the BUY at 11.0.
    """
    ob = make_book()
    s1 = ob.add_limit_order(Side.SELL, price=10.0, quantity=100)
    s2 = ob.add_limit_order(Side.SELL, price=10.0, quantity=100)

    assert ob.cancel_order(s1) is True

    b = ob.add_limit_order(Side.BUY, price=11.0, quantity=150)

    trades = ob.get_trades()
    assert len(trades) == 1
    t = trades[0]

    assert t.sell_order_id == s2
    assert t.buy_order_id == b
    assert t.quantity == 100
    assert t.price == pytest.approx(10.0)

    assert ob.best_ask() is None
    best_bid = ob.best_bid()
    assert best_bid is not None
    assert best_bid[1] == 50


def test_market_order_buy():
    """
    Scenario:
    - Add a single SELL: 100 @ 10.0.
    - Then send a market BUY for 70 units.
    - Market order should fill 70 @ 10.0 and leave 30 on the ask side.
    """
    ob = make_book()
    s = ob.add_limit_order(Side.SELL, price=10.0, quantity=100)

    b = ob.add_market_order(Side.BUY, quantity=70)

    trades = ob.get_trades()
    assert len(trades) == 1
    t = trades[0]

    assert t.sell_order_id == s
    assert t.buy_order_id == b
    assert t.price == pytest.approx(10.0)
    assert t.quantity == 70

    assert ob.best_ask() == (10.0, 30)


def test_market_order_stops_when_book_empty():
    """
    Scenario:
    - Add a single SELL: 50 @ 10.0.
    - Then send a market BUY for 100 units.
    - Only 50 are available, so the market order should trade 50 and stop.
    - It must NOT "overfill" beyond available liquidity.
    """
    ob = make_book()
    s = ob.add_limit_order(Side.SELL, price=10.0, quantity=50)

    b = ob.add_market_order(Side.BUY, quantity=100)

    trades = ob.get_trades()
    assert len(trades) == 1
    t = trades[0]

    assert t.quantity == 50

    assert ob.best_bid() is None
    assert ob.best_ask() is None

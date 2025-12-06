from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple
import heapq
import itertools
import time


class Side(Enum):
    """
    Represents the direction of an order.

    BUY  - the trader wants to purchase, matching against the best ask.
    SELL - the trader wants to sell, matching against the best bid.
    """
    BUY = auto()
    SELL = auto()

    def opposite(self) -> "Side":
        return Side.BUY if self is Side.SELL else Side.SELL


@dataclass
class Order:
    """
    Represents an order submitted to the limit order book.

    Attributes:
        order_id : Unique key for order.
        side     : BUY or SELL.
        price    : Limit price.
                   - For limit orders: a float (e.g., 101.5).
                   - For market orders: None = “execute immediately
                     at the best available price”.
        quantity : Number of units to buy or sell.
        timestamp: Used for FIFO priority when price is equal
                   (price-time priority).
    """
    order_id: int
    side: Side
    price: Optional[float]
    quantity: int
    timestamp: float


@dataclass
class Trade:
    """
    Represents an executed trade between a buy order and a sell order.

    Attributes:
        buy_order_id  : ID of the order on the buy side.
        sell_order_id : ID of the order on the sell side.
        price         : Execution price (resting order's price).
        quantity      : Amount traded.
        timestamp     : Time of execution.
    """
    buy_order_id: int
    sell_order_id: int
    price: float
    quantity: int
    timestamp: float


@dataclass
class OrderNode:
    """
    A node in the doubly linked list for a price level.

    Attributes:
        order : The Order object associated with this node.
        prev  : Pointer to the previous order node.
        next  : Pointer to the next node order node.
    """

    order: Order
    prev: Optional["OrderNode"] = None
    next: Optional["OrderNode"] = None


@dataclass
class PriceLevel:
    """
    Doubly linked list structure of resting orders at a single price.

    Attributes:
        head : First order node in the price level.
        tail : Last order node in the price level.
    """
    head: Optional[OrderNode] = None
    tail: Optional[OrderNode] = None


class OrderBook:
    """
    Simple single-instrument (one asset) limit order book with price-time priority:
    best price first, and FIFO within each price level.

    Separated data structures for price and orders:
    - Heaps store ONLY price levels (quick to find best price, smaller heaps).
    - Doubly linked lists (per price) store individual orders (for time priority).

    - Bids: max-heap on price (using min-heap of negative prices)
    - Asks: min-heap on price
    """
    def __init__(self) -> None:
        # PriceLevel doubly linked list (FIFO at each price)
        self.bids: Dict[float, PriceLevel] = {}
        self.asks: Dict[float, PriceLevel] = {}

        # Heaps of prices
        self.bid_heap: List[float] = []
        self.ask_heap: List[float] = []

        # Map order_id -> (side, price, OrderNode)
        self.order_map: Dict[int, Tuple[Side, float, OrderNode]] = {}

        # Trade log
        self.trades: List[Trade] = []

        # For incrementing order IDs
        self._order_id_counter = itertools.count(1)

    # ---------- Public API ----------

    def add_limit_order(
        self,
        side: Side,
        price: float,
        quantity: int,
        order_id: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> int:
        """
        Add a limit order and immediately match against the opposite side.
        Returns the order ID (generated if not supplied).
        """
        if order_id is None:
            order_id = self._next_free_id()
        else:
            if order_id in self.order_map:
                raise ValueError(f"Order ID {order_id} already exists in the order book.")
        if timestamp is None:
            timestamp = time.time()

        order = Order(order_id, side, price, quantity, timestamp)
        self._match(order)

        # Rest remaining quantity after match on the book
        if order.quantity > 0:
            self._add_resting_order(order)

        return order_id

    def add_market_order(
        self,
        side: Side,
        quantity: int,
        order_id: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> int:
        """
        Add a market order which matches against the best available prices
        until it is fully filled or book is empty. Any remaining quantity is discarded.
        """
        if order_id is None:
            order_id = next(self._order_id_counter)
        if timestamp is None:
            timestamp = time.time()

        order = Order(order_id, side, price=None, quantity=quantity, timestamp=timestamp)
        self._match(order)

        # No resting, ignore any remaining quantities
        return order_id

    def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an existing resting order. Returns True if cancelled, False if not found
        or already fully executed.

        O(1) removal by unlinking node pointers in a doubly linked list.
        """
        info = self.order_map.get(order_id)
        if info is None:
            return False

        side, price, node = info
        book_side = self._book(side)
        level = book_side.get(price)
        if level is None:
            return False

        # Unlink node
        prev_node = node.prev
        next_node = node.next

        if prev_node:
            prev_node.next = next_node
        else:
            # Order node was head
            level.head = next_node

        if next_node:
            next_node.prev = prev_node
        else:
            # Order node was tail
            level.tail = prev_node

        # Remove if empty price level
        if level.head is None:
            del book_side[price]

        # Remove from order map
        del self.order_map[order_id]
        return True

    def best_bid(self) -> Optional[Tuple[float, int]]:
        """
        Return (price, total_quantity_at_price) for best bid, or None if no bids.
        """
        price = self._peek_best_price(Side.BUY)
        if price is None:
            return None
        book_side = self._book(Side.BUY)
        level = book_side[price]
        qty = self._sum_level_quantity(level)
        return price, qty

    def best_ask(self) -> Optional[Tuple[float, int]]:
        """
        Return (price, total_quantity_at_price) for best ask, or None if no asks.
        """
        price = self._peek_best_price(Side.SELL)
        if price is None:
            return None
        book_side = self._book(Side.SELL)
        level = book_side[price]
        qty = self._sum_level_quantity(level)
        return price, qty

    def get_depth(self, side: Side, levels: int = 5) -> List[Tuple[float, int]]:
        """
        Return top N price levels on given side as list of (price, total_quantity),
        sorted best-to-worst (descending for bids, ascending for asks).
        """
        book_side = self._book(side)

        if side == Side.BUY:
            prices = sorted(book_side.keys(), reverse=True)
        else:
            prices = sorted(book_side.keys())

        result: List[Tuple[float, int]] = []
        for p in prices[:levels]:
            level = book_side[p]
            qty = self._sum_level_quantity(level)
            result.append((p, qty))
        return result

    def get_trades(self) -> List[Trade]:
        """
        Return list of all trades executed so far.
        """
        return list(self.trades)

    # ---------- Internal helpers ----------

    def _book(self, side: Side) -> Dict[float, PriceLevel]:
        """
        Return the price -> PriceLevel mapping for the given side.
        """
        return self.bids if side == Side.BUY else self.asks

    def _heap(self, side: Side) -> List[float]:
        """
        Return the heap of prices for the given side.
        """
        return self.bid_heap if side == Side.BUY else self.ask_heap

    def _sum_level_quantity(self, level: PriceLevel) -> int:
        """
        Sum total quantity at a given price level by traversing its linked list.
        """
        total = 0
        node = level.head
        while node is not None:
            total += node.order.quantity
            node = node.next
        return total

    def _next_free_id(self) -> int:
        """
        Return the next available (non-duplicated) order ID from iterator.
        """
        while (oid := next(self._order_id_counter)) in self.order_map:
            pass
        return oid

    def _match(self, incoming: Order) -> None:
        """
        Match incoming order against the opposite side until it is fully filled,
        book is empty, or price limits are violated.
        """
        if incoming.side == Side.BUY:
            price_cmp = lambda best_price: (
                incoming.price is None or best_price <= incoming.price
            )
        else:
            price_cmp = lambda best_price: (
                incoming.price is None or best_price >= incoming.price
            )

        opposite_side = incoming.side.opposite()
        opposite_book = self._book(opposite_side)

        while incoming.quantity > 0:
            # Sweep through the best available price levels on the opposite side,
            # matching as much of the incoming order as possible, and
            # stop when incoming order is fully filled or no acceptable prices.
            best_price = self._pop_best_price_from_heap(opposite_side)
            if best_price is None:
                # No liquidity
                break

            if not price_cmp(best_price):
                # Push back the popped price if no acceptable price
                self._push_price(best_price, opposite_side)
                break

            level = opposite_book.get(best_price)
            if not level or level.head is None:
                opposite_book.pop(best_price, None)
                continue

            # Match first resting order at this price level (FIFO)
            while level.head is not None and incoming.quantity > 0:
                node = level.head
                resting = node.order

                traded_qty = min(incoming.quantity, resting.quantity)
                trade_price = best_price  # trade at resting order price
                self._record_trade(incoming, resting, trade_price, traded_qty)

                incoming.quantity -= traded_qty
                resting.quantity -= traded_qty

                if resting.quantity == 0:
                    # Remove this resting order from the head of the linked list
                    next_node = node.next
                    level.head = next_node
                    if next_node is not None:
                        next_node.prev = None
                    else:
                        # List became empty
                        level.tail = None
                    # Remove from order map
                    self.order_map.pop(resting.order_id, None)

            if level.head is None:
                # Remove if empty price level
                del opposite_book[best_price]
            else:
                # Still has liquidity, push back price into heap
                self._push_price(best_price, opposite_side)

    def _add_resting_order(self, order: Order) -> None:
        """
        Insert a partially filled or new order into its side of the book.
        """
        if order.price is None:
            raise ValueError("Resting market orders are not supported")

        book_side = self._book(order.side)

        # Get or create price level
        level = book_side.get(order.price)
        if level is None:
            level = PriceLevel()
            book_side[order.price] = level
            self._push_price(order.price, order.side)

        # Append to tail (FIFO)
        node = OrderNode(order=order)
        if level.tail is None:
            # Empty list
            level.head = level.tail = node
        else:
            level.tail.next = node
            node.prev = level.tail
            level.tail = node

        # Store node pointer in order map
        self.order_map[order.order_id] = (order.side, order.price, node)

    def _push_price(self, price: float, side: Side) -> None:
        """
        Insert a price into the appropriate heap.
        """
        if side == Side.BUY:
            heapq.heappush(self.bid_heap, -price)
        else:
            heapq.heappush(self.ask_heap, price)

    def _peek_best_price(self, side: Side) -> Optional[float]:
        """
        Peek best price without removing it.
        """
        heap = self._heap(side)
        book_side = self._book(side)

        while heap:
            raw = heap[0]
            price = -raw if side == Side.BUY else raw
            level = book_side.get(price)
            if level is not None and level.head is not None:
                return price
            else:
                # Lazy cleanup of stale price levels, ensures that trades are done
                # quicker, as heap removal of an arbitrary element is O(n).
                heapq.heappop(heap)
        return None

    def _pop_best_price_from_heap(self, side: Side) -> Optional[float]:
        """
        Pop and return best price, ensuring it still has liquidity.
        """
        heap = self._heap(side)
        book_side = self._book(side)

        while heap:
            raw = heapq.heappop(heap)
            price = -raw if side == Side.BUY else raw
            level = book_side.get(price)
            if level is not None and level.head is not None:
                return price
        return None

    def _record_trade(self, incoming: Order, resting: Order, price: float, qty: int) -> None:
        """
        Record an executed trade.
        """
        ts = time.time()
        if incoming.side == Side.BUY:
            buy_id, sell_id = incoming.order_id, resting.order_id
        else:
            buy_id, sell_id = resting.order_id, incoming.order_id

        self.trades.append(
            Trade(
                buy_order_id=buy_id,
                sell_order_id=sell_id,
                price=price,
                quantity=qty,
                timestamp=ts,
            )
        )

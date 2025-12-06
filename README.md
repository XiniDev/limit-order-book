# Simple Limit Order Book (Python)

This project implements a **single-instrument limit order book (LOB)** in Python with:

- **Price–time priority** (best price first, FIFO within each price level)  
- **Doubly linked lists** for O(1) order cancellation  
- **Heaps** for fast best bid/ask lookup  
- Support for **limit orders** and **market orders**  
- A growing **pytest test suite** that specifies the matching behaviour

The structure mirrors how real matching engines manage price levels and queues, and is suitable for **educational use**, **simulation**, and **quant dev interview prep**.

---

## 📦 Features

- **Limit orders**
  - Stored at per-price queues in strict FIFO order  
  - Matched against the opposite side when prices cross  

- **Market orders**
  - Execute immediately against the best available prices  
  - Any unfilled quantity is discarded (no resting market orders)

- **Efficient cancellation**
  - O(1) cancel by unlinking from a doubly linked list using a stored node pointer

- **Efficient price discovery**
  - `bid_heap`: max-heap (implemented as a min-heap over negative prices)  
  - `ask_heap`: min-heap  
  - Fast best bid / best ask lookups

- **Book queries**
  - `best_bid()`, `best_ask()`  
  - `get_depth(side, levels)` for simple depth snapshots  
  - `get_trades()` for a full trade log

---

## 🧠 Core Data Structures

| Component      | Purpose |
|---------------|---------|
| `Order`       | Order metadata: side, price, quantity, timestamp |
| `Trade`       | Executed trade record between a buy and a sell order |
| `OrderNode`   | Node in a doubly linked list at a single price level |
| `PriceLevel`  | Holds `head`/`tail` of the linked list for FIFO matching |
| `bids` / `asks` | `Dict[price, PriceLevel]` storing per-price queues |
| `bid_heap`    | Heap of (negative) bid prices → efficient best bid lookup |
| `ask_heap`    | Heap of ask prices → efficient best ask lookup |
| `order_map`   | `order_id → (side, price, OrderNode)` for O(1) cancellation |

**Design choice:**  
Heaps store **only prices**, while linked lists store **orders per price**. This keeps heaps small and preserves price–time priority.

---

## ▶️ Example Usage

Run the demo script:

```bash
python main.py
```

Example output (simplified):

```text
Initial book:
Best bid: (99.0, 150)
Best ask: (101.0, 100)
BIDS: [(99.0, 150), (98.0, 250)]
ASKS: [(101.0, 100), (102.0, 200)]
----------------------------------------
After aggressive buy:
Best bid: (99.0, 150)
Best ask: (102.0, 120)
BIDS: [(99.0, 150), (98.0, 250)]
ASKS: [(102.0, 120)]
----------------------------------------
Trades:
Trade(buy_order_id=5, sell_order_id=1, price=101.0, quantity=100, ...)
Trade(buy_order_id=5, sell_order_id=2, price=102.0, quantity=80, ...)
```

This shows:

* Initial resting bids/asks at multiple price levels
* An “aggressive” buy order that crosses the spread and matches multiple levels
* Resulting trades and updated book state

---

## ✅ Tests (pytest)

Tests live in `test_order_book.py` and cover:

* Non-crossing orders (no trades, just resting)
* Full fills and partial fills
* Multi-level matching (sweeping several price levels)
* FIFO behaviour within a single price level
* Order cancellation and its impact on subsequent matches
* Market-order behaviour (including when the book runs out of liquidity)
* Edge cases such as crossing sells, cancelling unknown orders, and empty-book behaviour

### Running the tests

1. (Optional but recommended) Create and activate a virtualenv.

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run pytest:

   ```bash
   pytest -q
   ```

If everything is set up correctly, all tests should pass and serve as a **specification** for the order book’s behaviour.

---

## 🔍 Static Type Checking (mypy)

The core implementation is type-annotated and checked with **mypy**.

To run mypy:

```bash
mypy order_book.py
```

With the `mypy.ini` configuration, mypy will validate that the main engine code is type-safe.

---

## 🔬 Synthetic Performance Benchmark

A simple synthetic benchmark inserts `num_orders` random limit orders into a fresh
`OrderBook` instance and measures the runtime:

```bash
python benchmark_order_book.py
```

The script prints:

* total time taken
* approximate orders processed per second

and appends a summary line to `benchmark_results.txt`, e.g.:

```text
[2025-12-06T12:15:48] num_orders=100,000, elapsed=0.4439s, throughput≈225,267 orders/ss
```

---

## 📁 Project Structure

```text
order_book.py            # Core limit order book implementation
main.py                  # Example usage / demo script
test_order_book.py       # Pytest suite covering core matching logic
benchmark_order_book.py  # Synthetic performance benchmark script
benchmark_results.txt    # (Created/appended) benchmark runs
requirements.txt         # Python dependencies (pytest, mypy, etc.)
mypy.ini                 # mypy configuration (optional but recommended)
```

---

## 📝 Implementation Notes

* **Lazy heap cleanup**
  When orders are fully matched or cancelled, the corresponding price may remain in
  the heap. Instead of removing arbitrary elements (O(n)), the implementation
  performs **lazy cleanup**: stale prices are discarded when they reach the top
  of the heap.

* **Price–time priority**
  All orders at the same price are stored in a doubly linked list. New orders
  are appended at the tail; matching always occurs from the head. This guarantees
  FIFO within each price level.

* **Single instrument**
  The current implementation maintains a single order book (one instrument).
  Extending this to multiple instruments would typically involve a
  `Dict[symbol, OrderBook]` and routing logic on top.

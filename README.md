# Simple Limit Order Book (Python)

This project implements a **high-performance limit order book (LOB)** in Python,
featuring:

- **Price–time priority**  
- **Doubly linked lists** for O(1) order cancellation  
- **Heaps** for fast best bid/ask lookup  
- **Lazy cleanup** of stale price levels  
- Support for **limit orders**, **market orders**, and **FIFO matching**

The structure closely resembles real exchange matching engines and is fully
suitable for educational, simulation, and interview preparation purposes.

---

## 📦 Features

- **Limit orders**: Stored at price levels in FIFO order  
- **Market orders**: Match against best available prices  
- **O(1) cancellation** using node pointers  
- **Efficient matching** using per-price linked lists  
- **Bid/ask heaps** for fast top-of-book access  
- **Depth queries** for order book snapshots  

---

## 🧠 Core Data Structures

| Component        | Purpose |
|------------------|---------|
| `PriceLevel`     | Doubly linked list of resting orders at a given price |
| `OrderNode`      | Represents a single order within the price-level queue |
| `bid_heap`       | Max-heap (via negative numbers) for fast best bid lookup |
| `ask_heap`       | Min-heap for fast best ask lookup |
| `order_map`      | Maps order IDs → O(1) cancel via stored node pointer |

---

## ▶️ Example Usage

```python main.py```

---

## 📁 Project Structure

```text
order_book.py   # Main LOB implementation
main.py         # Example usage & demonstration
```

## 📝 Notes

- **Heaps may contain stale prices** after orders are matched or cancelled.  
  This is intentional: removing arbitrary heap elements is **O(n)**.  
  Instead, stale values are removed **lazily** when they reach the top.

- **Linked lists guarantee FIFO matching and O(1) cancellation**,  
  which mirrors how real exchange matching engines manage order queues.

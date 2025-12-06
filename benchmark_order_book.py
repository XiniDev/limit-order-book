import random
import time
from datetime import datetime

from order_book import OrderBook, Side


def run_benchmark(num_orders: int = 100_000, output_path: str = "benchmark_results.txt") -> None:
    """
    Run a simple synthetic performance benchmark for the OrderBook.

    Random side, price, and quantity for limit orders are generated to test:
        - total time taken
        - approximate orders processed per second

    Ranges:
        - Price: base price (100) ±0.5
        - Quantity: 1 to 100 units

    Results are printed to stdout and saved as 'benchmark_results.txt'.
    """
    ob = OrderBook()

    # Seed for reproducibility
    random.seed(42)

    base_price = 100.0

    start = time.perf_counter()

    for i in range(num_orders):
        side = Side.BUY if random.random() < 0.5 else Side.SELL

        price = base_price + random.uniform(-0.5, 0.5)

        quantity = random.randint(1, 100)

        ob.add_limit_order(side=side, price=price, quantity=quantity)

    elapsed = time.perf_counter() - start
    orders_per_second = num_orders / elapsed if elapsed > 0 else float("inf")

    # Console output
    print(f"Processed {num_orders:,} orders in {elapsed:.4f} seconds")
    print(f"≈ {orders_per_second:,.0f} orders/second")

    # Append to text file
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(
            f"[{timestamp}] num_orders={num_orders:,}, "
            f"elapsed={elapsed:.4f}s, "
            f"throughput≈{orders_per_second:,.0f} orders/s\n"
        )


if __name__ == "__main__":
    run_benchmark()

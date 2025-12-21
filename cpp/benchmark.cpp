#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <string>

#include "order_book.hpp"

using lob::OrderBook;
using lob::Side;

static std::string iso_timestamp_seconds_local() {
    using namespace std::chrono;
    auto now = system_clock::now();
    std::time_t t = system_clock::to_time_t(now);

    std::tm tm{};
#if defined(_WIN32)
    localtime_s(&tm, &t);
#else
    localtime_r(&t, &tm);
#endif

    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%S");
    return oss.str();
}

static void run_benchmark(std::int64_t num_orders = 100'000,
                          const std::string& output_path = "benchmark_results.txt")
{
    OrderBook ob;

    // Seed for reproducibility
    std::mt19937 rng(42);

    std::bernoulli_distribution side_coin(0.5);
    std::uniform_real_distribution<double> price_delta(-0.5, 0.5);
    std::uniform_int_distribution<std::int64_t> qty_dist(1, 100);

    const double base_price = 100.0;

    using clock = std::chrono::steady_clock;
    auto start = clock::now();

    for (std::int64_t i = 0; i < num_orders; ++i) {
        Side side = side_coin(rng) ? Side::Buy : Side::Sell;
        double price = base_price + price_delta(rng);
        std::int64_t quantity = qty_dist(rng);

        ob.addLimitOrder(side, price, quantity);
    }

    auto end = clock::now();
    std::chrono::duration<double> elapsed = end - start;

    const double seconds = elapsed.count();
    const double orders_per_second = (seconds > 0.0) ? (static_cast<double>(num_orders) / seconds)
                                                     : std::numeric_limits<double>::infinity();

    // Console output
    std::cout << "Processed " << num_orders << " orders in "
              << std::fixed << std::setprecision(4) << seconds << " seconds\n";
    std::cout << "≈ " << std::fixed << std::setprecision(0) << orders_per_second
              << " orders/second\n";

    // Append to text file (like Python)
    const std::string timestamp = iso_timestamp_seconds_local();
    std::ofstream f(output_path, std::ios::app);
    if (!f) {
        std::cerr << "Warning: failed to open output file: " << output_path << "\n";
        return;
    }

    f << "[" << timestamp << "] "
      << "num_orders=" << num_orders << ", "
      << "elapsed=" << std::fixed << std::setprecision(4) << seconds << "s, "
      << "throughput≈" << std::fixed << std::setprecision(0) << orders_per_second
      << " orders/s\n";
}

int main(int argc, char** argv) {
    std::int64_t num_orders = 100'000;
    std::string output_path = "benchmark_results.txt";

    if (argc >= 2) {
        num_orders = std::stoll(argv[1]);
    }
    if (argc >= 3) {
        output_path = argv[2];
    }

    run_benchmark(num_orders, output_path);
    return 0;
}

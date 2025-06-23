"""Encryption performance benchmarking utilities.

This module benchmarks encryption performance for FHIR Patient Resource data
and other healthcare information.

Note: This module handles PHI-related encryption benchmarking.
- Access Control: Implement strict access control for benchmarking operations that handle PHI data
"""

import concurrent.futures
import json
import os
import statistics
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple

try:
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from src.healthcare.fhir_validator import FHIRValidator
from src.utils.encryption import EncryptionService, FieldEncryption
from src.utils.logging import get_logger

# FHIR resource type for this module
__fhir_resource__ = "Patient"

logger = get_logger(__name__)


class EncryptionBenchmark:
    """Benchmark encryption and decryption performance."""

    def __init__(self) -> None:
        """Initialize benchmark suite."""
        self.encryption_service = EncryptionService()
        self.field_encryption = FieldEncryption()
        self.validator = FHIRValidator()  # Initialize validator
        self.results: Dict[str, Any] = {
            "encryption": {},
            "decryption": {},
            "field_encryption": {},
            "field_decryption": {},
            "summary": {},
        }

    def generate_test_data(self, size_category: str) -> str:
        """Generate test data of various sizes."""
        sizes = {
            "tiny": 100,  # 100 bytes
            "small": 1024,  # 1 KB
            "medium": 10240,  # 10 KB
            "large": 102400,  # 100 KB
            "xlarge": 1048576,  # 1 MB
            "huge": 10485760,  # 10 MB
        }

        size = sizes.get(size_category, 1024)
        # Generate realistic health data pattern
        base_data = {
            "patient_id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Test Patient",
            "diagnosis": "Sample diagnosis text",
            "medications": ["Med1", "Med2", "Med3"],
            "notes": "Clinical notes " * (size // 100),
        }

        return json.dumps(base_data)[:size]

    def benchmark_single_operation(
        self, operation: Callable[[Any], Any], data: Any, iterations: int = 100
    ) -> Tuple[float, float, float, float, List[float]]:
        """Benchmark a single operation multiple times."""
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            _ = operation(data)
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to milliseconds

        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0

        return avg_time, min_time, max_time, std_dev, times

    def benchmark_encryption(self) -> Dict[str, Any]:
        """Benchmark encryption performance for various data sizes."""
        logger.info("Starting encryption benchmarks...")

        for size_category in ["tiny", "small", "medium", "large", "xlarge"]:
            test_data = self.generate_test_data(size_category)
            data_size = len(test_data.encode())

            # Benchmark encryption
            avg_time, min_time, max_time, std_dev, times = (
                self.benchmark_single_operation(
                    self.encryption_service.encrypt, test_data
                )
            )

            throughput_mbps = (data_size / (avg_time / 1000)) / (1024 * 1024)

            self.results["encryption"][size_category] = {
                "data_size_bytes": data_size,
                "avg_time_ms": round(avg_time, 3),
                "min_time_ms": round(min_time, 3),
                "max_time_ms": round(max_time, 3),
                "std_dev_ms": round(std_dev, 3),
                "throughput_mbps": round(throughput_mbps, 2),
                "raw_times": times,
            }

            logger.info(
                f"Encryption - Size: {size_category} ({data_size} bytes), "
                f"Avg: {avg_time:.3f}ms, Throughput: {throughput_mbps:.2f} MB/s"
            )

        return dict(self.results["encryption"])

    def benchmark_decryption(self) -> Dict[str, Any]:
        """Benchmark decryption performance for various data sizes."""
        logger.info("Starting decryption benchmarks...")

        for size_category in ["tiny", "small", "medium", "large", "xlarge"]:
            test_data = self.generate_test_data(size_category)
            encrypted_data = self.encryption_service.encrypt(test_data)
            data_size = len(test_data.encode())

            # Benchmark decryption
            avg_time, min_time, max_time, std_dev, times = (
                self.benchmark_single_operation(
                    self.encryption_service.decrypt, encrypted_data
                )
            )

            throughput_mbps = (data_size / (avg_time / 1000)) / (1024 * 1024)

            self.results["decryption"][size_category] = {
                "data_size_bytes": data_size,
                "avg_time_ms": round(avg_time, 3),
                "min_time_ms": round(min_time, 3),
                "max_time_ms": round(max_time, 3),
                "std_dev_ms": round(std_dev, 3),
                "throughput_mbps": round(throughput_mbps, 2),
                "raw_times": times,
            }

            logger.info(
                f"Decryption - Size: {size_category} ({data_size} bytes), "
                f"Avg: {avg_time:.3f}ms, Throughput: {throughput_mbps:.2f} MB/s"
            )

        return dict(self.results["decryption"])

    def benchmark_field_encryption(self) -> Dict[str, Any]:
        """Benchmark field-level encryption for documents."""
        logger.info("Starting field encryption benchmarks...")

        test_documents = [
            {
                "name": "John Doe",
                "ssn": "123-45-6789",
                "email": "john@example.com",
                "medical_record_number": "MRN123456",
                "diagnosis": "Sample diagnosis",
                "unhcr_case_number": "UNHCR-12345",
            },
            {
                "patient_data": {
                    "passport_number": "P123456789",
                    "biometric_data": "fingerprint_hash_12345",
                    "genetic_data": "genome_sequence_sample",
                },
                "contact": {"phone": "+1234567890", "address": "123 Main St"},
            },
        ]

        for i, doc in enumerate(test_documents):
            doc_size = len(json.dumps(doc).encode())

            # Benchmark field encryption
            avg_time, min_time, max_time, std_dev, _ = self.benchmark_single_operation(
                self.field_encryption.encrypt_document, doc, iterations=100
            )

            self.results["field_encryption"][f"document_{i+1}"] = {
                "document_size_bytes": doc_size,
                "fields_encrypted": (
                    sum(
                        1
                        for field in doc
                        if self.field_encryption.should_encrypt_field(field)
                    )
                    if isinstance(doc, dict)
                    else 0
                ),
                "avg_time_ms": round(avg_time, 3),
                "min_time_ms": round(min_time, 3),
                "max_time_ms": round(max_time, 3),
                "std_dev_ms": round(std_dev, 3),
            }

            logger.info(
                f"Field Encryption - Document {i+1} ({doc_size} bytes), "
                f"Avg: {avg_time:.3f}ms"
            )

        return dict(self.results["field_encryption"])

    def benchmark_concurrent_operations(self, num_threads: int = 10) -> Dict[str, Any]:
        """Benchmark concurrent encryption/decryption operations."""
        logger.info(
            f"Starting concurrent operations benchmark with {num_threads} threads..."
        )

        test_data = self.generate_test_data("medium")
        operations_per_thread = 100

        def encrypt_decrypt_cycle() -> List[float]:
            times = []
            for _ in range(operations_per_thread):
                start = time.perf_counter()
                encrypted = self.encryption_service.encrypt(test_data)
                _ = self.encryption_service.decrypt(encrypted)
                end = time.perf_counter()
                times.append((end - start) * 1000)
            return times

        # Run concurrent operations
        start_time = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(encrypt_decrypt_cycle) for _ in range(num_threads)
            ]
            all_times = []
            for future in concurrent.futures.as_completed(futures):
                all_times.extend(future.result())
        end_time = time.perf_counter()

        total_operations = num_threads * operations_per_thread * 2  # encrypt + decrypt
        total_time = (end_time - start_time) * 1000
        operations_per_second = (total_operations / total_time) * 1000

        concurrent_results = {
            "num_threads": num_threads,
            "total_operations": total_operations,
            "total_time_ms": round(total_time, 3),
            "operations_per_second": round(operations_per_second, 2),
            "avg_operation_time_ms": round(statistics.mean(all_times), 3),
            "min_operation_time_ms": round(min(all_times), 3),
            "max_operation_time_ms": round(max(all_times), 3),
        }

        logger.info(
            f"Concurrent Operations - {total_operations} ops in {total_time:.3f}ms, "
            f"{operations_per_second:.2f} ops/sec"
        )

        return concurrent_results

    def calculate_summary_statistics(self) -> Dict[str, Any]:
        """Calculate summary statistics from all benchmarks."""
        summary: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "encryption_performance": {
                "best_throughput_mbps": 0,
                "worst_throughput_mbps": float("inf"),
                "avg_throughput_mbps": 0,
            },
            "decryption_performance": {
                "best_throughput_mbps": 0,
                "worst_throughput_mbps": float("inf"),
                "avg_throughput_mbps": 0,
            },
            "recommendations": [],
        }

        # Calculate encryption statistics
        enc_throughputs = [
            result["throughput_mbps"] for result in self.results["encryption"].values()
        ]
        if enc_throughputs:
            summary["encryption_performance"]["best_throughput_mbps"] = max(
                enc_throughputs
            )
            summary["encryption_performance"]["worst_throughput_mbps"] = min(
                enc_throughputs
            )
            summary["encryption_performance"]["avg_throughput_mbps"] = statistics.mean(
                enc_throughputs
            )

        # Calculate decryption statistics
        dec_throughputs = [
            result["throughput_mbps"] for result in self.results["decryption"].values()
        ]
        if dec_throughputs:
            summary["decryption_performance"]["best_throughput_mbps"] = max(
                dec_throughputs
            )
            summary["decryption_performance"]["worst_throughput_mbps"] = min(
                dec_throughputs
            )
            summary["decryption_performance"]["avg_throughput_mbps"] = statistics.mean(
                dec_throughputs
            )

        # Generate recommendations
        avg_throughput = (
            summary["encryption_performance"]["avg_throughput_mbps"]
            + summary["decryption_performance"]["avg_throughput_mbps"]
        ) / 2

        if avg_throughput < 10:
            summary["recommendations"].append(
                "Consider hardware acceleration for encryption operations"
            )

        if summary["encryption_performance"]["worst_throughput_mbps"] < 5:
            summary["recommendations"].append(
                "Large file encryption may be slow - consider chunking"
            )

        # Check field encryption performance
        field_enc_times = [
            result["avg_time_ms"]
            for result in self.results["field_encryption"].values()
        ]
        if field_enc_times and max(field_enc_times) > 10:
            summary["recommendations"].append(
                "Field encryption taking >10ms - consider caching encrypted values"
            )

        self.results["summary"] = summary
        return summary

    def generate_performance_report(
        self, output_file: str = "encryption_benchmark_report.json"
    ) -> None:
        """Generate a comprehensive performance report."""
        report = {
            "benchmark_results": self.results,
            "environment": {
                "timestamp": datetime.utcnow().isoformat(),
                "python_version": "3.9+",
                "encryption_library": "cryptography",
                "algorithm": "AES-256-GCM",
            },
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Performance report saved to {output_file}")

    def plot_performance_graphs(self, output_dir: str = "benchmark_plots") -> None:
        """Generate performance visualization graphs."""
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib not available - skipping graph generation")
            return

        os.makedirs(output_dir, exist_ok=True)

        # Throughput comparison
        sizes = list(self.results["encryption"].keys())
        enc_throughputs = [
            self.results["encryption"][s]["throughput_mbps"] for s in sizes
        ]
        dec_throughputs = [
            self.results["decryption"][s]["throughput_mbps"] for s in sizes
        ]

        plt.figure(figsize=(10, 6))
        x = range(len(sizes))
        plt.bar(
            [i - 0.2 for i in x], enc_throughputs, 0.4, label="Encryption", alpha=0.8
        )
        plt.bar(
            [i + 0.2 for i in x], dec_throughputs, 0.4, label="Decryption", alpha=0.8
        )
        plt.xlabel("Data Size Category")
        plt.ylabel("Throughput (MB/s)")
        plt.title("Encryption/Decryption Throughput by Data Size")
        plt.xticks(x, sizes)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(
            f"{output_dir}/throughput_comparison.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

        # Response time distribution
        plt.figure(figsize=(10, 6))
        for size in ["small", "medium", "large"]:
            if size in self.results["encryption"]:
                times = self.results["encryption"][size]["raw_times"]
                plt.hist(
                    times, bins=30, alpha=0.5, label=f"{size} ({len(times)} samples)"
                )

        plt.xlabel("Time (ms)")
        plt.ylabel("Frequency")
        plt.title("Encryption Time Distribution")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{output_dir}/time_distribution.png", dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Performance graphs saved to {output_dir}/")

    def run_full_benchmark(self) -> Dict[str, Any]:
        """Run the complete benchmark suite."""
        logger.info("Starting full encryption benchmark suite...")

        # Run all benchmarks
        self.benchmark_encryption()
        self.benchmark_decryption()
        self.benchmark_field_encryption()

        # Run concurrent benchmark
        concurrent_results = self.benchmark_concurrent_operations()
        self.results["concurrent"] = concurrent_results

        # Calculate summary
        self.calculate_summary_statistics()

        # Generate outputs
        self.generate_performance_report()

        try:
            self.plot_performance_graphs()
        except ImportError:
            logger.warning("Matplotlib not available - skipping graph generation")

        logger.info("Benchmark suite completed!")

        return self.results


# CLI interface for running benchmarks
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run encryption performance benchmarks"
    )
    parser.add_argument(
        "--quick", action="store_true", help="Run quick benchmark with fewer iterations"
    )
    parser.add_argument(
        "--output",
        default="encryption_benchmark_report.json",
        help="Output file for benchmark report",
    )

    args = parser.parse_args()

    benchmark = EncryptionBenchmark()

    if args.quick:
        # Quick benchmark with smaller datasets
        benchmark.results["encryption"]["small"] = benchmark.benchmark_single_operation(
            benchmark.encryption_service.encrypt,
            benchmark.generate_test_data("small"),
            iterations=10,
        )
        benchmark.calculate_summary_statistics()
    else:
        # Full benchmark
        benchmark.run_full_benchmark()

    print("\nBenchmark Summary:")
    print(
        f"Encryption Avg Throughput: {benchmark.results['summary']['encryption_performance']['avg_throughput_mbps']:.2f} MB/s"
    )
    print(
        f"Decryption Avg Throughput: {benchmark.results['summary']['decryption_performance']['avg_throughput_mbps']:.2f} MB/s"
    )

    if benchmark.results["summary"]["recommendations"]:
        print("\nRecommendations:")
        for rec in benchmark.results["summary"]["recommendations"]:
            print(f"- {rec}")

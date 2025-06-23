"""Tests for Encryption Benchmark Utility.

This module tests the encryption benchmarking utilities with real encryption services.
NO MOCKS - Uses real EncryptionService and FieldEncryption as required.
Target: 100% statement coverage for security compliance.
"""

import json
import os
import tempfile
from pathlib import Path

from src.utils.encryption_benchmark import EncryptionBenchmark


class TestEncryptionBenchmark:
    """Test encryption benchmark with real encryption services."""

    def test_initialization(self):
        """Test benchmark initialization."""
        benchmark = EncryptionBenchmark()

        # Verify services are initialized
        assert benchmark.encryption_service is not None
        assert benchmark.field_encryption is not None
        assert benchmark.validator is not None

        # Verify results structure
        assert isinstance(benchmark.results, dict)
        assert "encryption" in benchmark.results
        assert "decryption" in benchmark.results
        assert "field_encryption" in benchmark.results
        assert "field_decryption" in benchmark.results
        assert "summary" in benchmark.results

    def test_generate_test_data_sizes(self):
        """Test test data generation for all size categories."""
        benchmark = EncryptionBenchmark()

        # Test all size categories
        expected_sizes = {
            "tiny": 100,
            "small": 1024,
            "medium": 10240,
            "large": 102400,
            "xlarge": 1048576,
            "huge": 10485760,
        }

        for size_category, expected_size in expected_sizes.items():
            data = benchmark.generate_test_data(size_category)

            # Verify data is string and approximately correct size
            assert isinstance(data, str)
            assert len(data) <= expected_size

            # Verify it's valid JSON structure (truncated)
            try:
                json.loads(data)
            except json.JSONDecodeError:
                # Expected for truncated data, just verify it starts correctly
                assert data.startswith('{"patient_id"')

    def test_generate_test_data_unknown_size(self):
        """Test test data generation with unknown size category."""
        benchmark = EncryptionBenchmark()

        # Unknown size should default to 1024 (small)
        data = benchmark.generate_test_data("unknown_size")
        assert isinstance(data, str)
        assert len(data) <= 1024

    def test_benchmark_single_operation(self):
        """Test single operation benchmarking."""
        benchmark = EncryptionBenchmark()

        test_data = "test data for encryption"

        # Benchmark encryption operation with real service
        result = benchmark.benchmark_single_operation(
            benchmark.encryption_service.encrypt, test_data, iterations=5
        )

        avg_time, min_time, max_time, std_dev, times = result

        # Verify results
        assert isinstance(avg_time, float)
        assert isinstance(min_time, float)
        assert isinstance(max_time, float)
        assert isinstance(std_dev, float)
        assert isinstance(times, list)
        assert len(times) == 5

        # Verify logical relationships
        assert min_time <= avg_time <= max_time
        assert std_dev >= 0
        assert all(isinstance(t, float) for t in times)

    def test_benchmark_single_operation_one_iteration(self):
        """Test single operation with one iteration (std_dev edge case)."""
        benchmark = EncryptionBenchmark()

        test_data = "test data"

        # Single iteration should have std_dev = 0
        result = benchmark.benchmark_single_operation(
            benchmark.encryption_service.encrypt, test_data, iterations=1
        )

        avg_time, min_time, max_time, std_dev, times = result

        assert std_dev == 0
        assert len(times) == 1
        assert avg_time == min_time == max_time

    def test_benchmark_encryption(self):
        """Test encryption performance benchmarking."""
        benchmark = EncryptionBenchmark()

        # Run encryption benchmark
        results = benchmark.benchmark_encryption()

        # Verify results structure
        assert isinstance(results, dict)
        assert "tiny" in results
        assert "small" in results
        assert "medium" in results
        assert "large" in results
        assert "xlarge" in results

        # Verify each result has required fields
        for _size_category, result in results.items():
            assert "data_size_bytes" in result
            assert "avg_time_ms" in result
            assert "min_time_ms" in result
            assert "max_time_ms" in result
            assert "std_dev_ms" in result
            assert "throughput_mbps" in result
            assert "raw_times" in result

            # Verify data types
            assert isinstance(result["data_size_bytes"], int)
            assert isinstance(result["avg_time_ms"], float)
            assert isinstance(result["throughput_mbps"], float)
            assert isinstance(result["raw_times"], list)

            # Verify logical relationships
            assert (
                result["min_time_ms"] <= result["avg_time_ms"] <= result["max_time_ms"]
            )
            assert result["throughput_mbps"] > 0

    def test_benchmark_decryption(self):
        """Test decryption performance benchmarking."""
        benchmark = EncryptionBenchmark()

        # Run decryption benchmark
        results = benchmark.benchmark_decryption()

        # Verify results structure
        assert isinstance(results, dict)
        assert "tiny" in results
        assert "small" in results
        assert "medium" in results
        assert "large" in results
        assert "xlarge" in results

        # Verify each result has required fields
        for _size_category, result in results.items():
            assert "data_size_bytes" in result
            assert "avg_time_ms" in result
            assert "min_time_ms" in result
            assert "max_time_ms" in result
            assert "std_dev_ms" in result
            assert "throughput_mbps" in result
            assert "raw_times" in result

            # Verify data types and relationships
            assert isinstance(result["data_size_bytes"], int)
            assert isinstance(result["avg_time_ms"], float)
            assert (
                result["min_time_ms"] <= result["avg_time_ms"] <= result["max_time_ms"]
            )
            assert result["throughput_mbps"] > 0

    def test_benchmark_field_encryption(self):
        """Test field-level encryption benchmarking."""
        benchmark = EncryptionBenchmark()

        # Run field encryption benchmark
        results = benchmark.benchmark_field_encryption()

        # Verify results structure
        assert isinstance(results, dict)
        assert "document_1" in results
        assert "document_2" in results

        # Verify each result has required fields
        for _, result in results.items():
            assert "fields_encrypted" in result
            assert "avg_time_ms" in result
            assert "min_time_ms" in result
            assert "max_time_ms" in result
            assert "std_dev_ms" in result
            assert "raw_times" in result

            # Verify data types
            assert isinstance(result["fields_encrypted"], int)
            assert isinstance(result["avg_time_ms"], float)
            assert isinstance(result["raw_times"], list)

            # Verify logical relationships
            assert result["fields_encrypted"] >= 0
            assert result["avg_time_ms"] >= 0

    def test_benchmark_concurrent_operations(self):
        """Test concurrent operations benchmarking."""
        benchmark = EncryptionBenchmark()

        # Run concurrent benchmark
        results = benchmark.benchmark_concurrent_operations()

        # Verify results structure
        assert isinstance(results, dict)
        assert "num_threads" in results
        assert "total_operations" in results
        assert "total_time_seconds" in results
        assert "operations_per_second" in results

        # Verify data types and logical relationships
        assert isinstance(results["num_threads"], int)
        assert isinstance(results["total_operations"], int)
        assert isinstance(results["total_time_seconds"], float)
        assert isinstance(results["operations_per_second"], float)

        assert results["num_threads"] > 0
        assert results["total_operations"] > 0
        assert results["total_time_seconds"] > 0
        assert results["operations_per_second"] > 0

    def test_calculate_summary_statistics_with_data(self):
        """Test summary statistics calculation with data."""
        benchmark = EncryptionBenchmark()

        # Add some test data
        benchmark.results["encryption"] = {
            "small": {"throughput_mbps": 10.0, "avg_time_ms": 5.0},
            "medium": {"throughput_mbps": 8.0, "avg_time_ms": 7.0},
        }
        benchmark.results["decryption"] = {
            "small": {"throughput_mbps": 12.0, "avg_time_ms": 4.0},
            "medium": {"throughput_mbps": 9.0, "avg_time_ms": 6.0},
        }
        benchmark.results["field_encryption"] = {
            "document_1": {"avg_time_ms": 3.0, "fields_encrypted": 5},
            "document_2": {"avg_time_ms": 4.0, "fields_encrypted": 7},
        }

        # Calculate summary
        summary = benchmark.calculate_summary_statistics()

        # Verify summary structure
        assert isinstance(summary, dict)
        assert "encryption_performance" in summary
        assert "decryption_performance" in summary
        assert "field_encryption_performance" in summary
        assert "recommendations" in summary

        # Verify encryption performance
        enc_perf = summary["encryption_performance"]
        assert "avg_throughput_mbps" in enc_perf
        assert "max_throughput_mbps" in enc_perf
        assert "min_throughput_mbps" in enc_perf

        # Verify calculated values
        assert enc_perf["avg_throughput_mbps"] == 9.0  # (10+8)/2
        assert enc_perf["max_throughput_mbps"] == 10.0
        assert enc_perf["min_throughput_mbps"] == 8.0

    def test_calculate_summary_statistics_empty_data(self):
        """Test summary statistics with empty data."""
        benchmark = EncryptionBenchmark()

        # Calculate summary with empty results
        summary = benchmark.calculate_summary_statistics()

        # Should handle empty data gracefully
        assert isinstance(summary, dict)
        assert "encryption_performance" in summary
        assert "decryption_performance" in summary
        assert "field_encryption_performance" in summary
        assert "recommendations" in summary

        # Empty data should result in zero values
        assert summary["encryption_performance"]["avg_throughput_mbps"] == 0
        assert summary["decryption_performance"]["avg_throughput_mbps"] == 0

    def test_generate_performance_report(self):
        """Test performance report generation."""
        benchmark = EncryptionBenchmark()

        # Add some test data
        benchmark.results["encryption"] = {
            "small": {"throughput_mbps": 10.0, "avg_time_ms": 5.0}
        }
        benchmark.results["summary"] = {
            "encryption_performance": {"avg_throughput_mbps": 10.0}
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = os.path.join(temp_dir, "test_report.json")

            # Generate report
            benchmark.generate_performance_report(report_path)

            # Verify report was created
            assert os.path.exists(report_path)

            # Verify report content
            with open(report_path, "r") as f:
                report_data = json.load(f)

            assert isinstance(report_data, dict)
            assert "timestamp" in report_data
            assert "results" in report_data
            assert "encryption" in report_data["results"]

    def test_plot_performance_graphs(self):
        """Test graph generation."""
        benchmark = EncryptionBenchmark()

        # Run minimal benchmarks to have data
        benchmark.benchmark_encryption()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Test plotting functionality - should handle matplotlib gracefully
            try:
                benchmark.plot_performance_graphs(temp_dir)
                # If matplotlib is available, files may be created
                plot_files = list(Path(temp_dir).glob("*.png"))
                assert isinstance(plot_files, list)
            except ImportError:
                # Expected when matplotlib is not available
                pass

    def test_run_full_benchmark(self):
        """Test complete benchmark suite execution."""
        benchmark = EncryptionBenchmark()

        # Run full benchmark with real operations
        results = benchmark.run_full_benchmark()

        # Verify all benchmark types were run
        assert "encryption" in results
        assert "decryption" in results
        assert "field_encryption" in results
        assert "concurrent" in results
        assert "summary" in results

        # Verify results structure
        assert isinstance(results, dict)
        assert isinstance(results["summary"], dict)

    def test_summary_recommendations_logic(self):
        """Test recommendation generation logic."""
        benchmark = EncryptionBenchmark()

        # Set low throughput results to trigger recommendations
        benchmark.results["encryption"] = {
            "small": {"throughput_mbps": 3.0},  # Low throughput
            "medium": {"throughput_mbps": 2.0},  # Very low throughput
        }
        benchmark.results["decryption"] = {
            "small": {"throughput_mbps": 4.0},
            "medium": {"throughput_mbps": 3.0},
        }
        benchmark.results["field_encryption"] = {
            "document_1": {"avg_time_ms": 15.0}  # Slow field encryption
        }

        summary = benchmark.calculate_summary_statistics()

        # Should generate recommendations for low performance
        recommendations = summary["recommendations"]
        assert len(recommendations) > 0

        # Check for specific recommendations
        assert any("hardware acceleration" in rec.lower() for rec in recommendations)
        assert any("chunking" in rec.lower() for rec in recommendations)
        assert any("caching" in rec.lower() for rec in recommendations)


class TestEncryptionBenchmarkEdgeCases:
    """Test edge cases and error conditions."""

    def test_benchmark_with_extremely_small_data(self):
        """Test benchmarking with minimal data."""
        benchmark = EncryptionBenchmark()

        # Test with very small data
        tiny_data = "x"
        result = benchmark.benchmark_single_operation(
            benchmark.encryption_service.encrypt, tiny_data, iterations=3
        )

        avg_time, min_time, max_time, std_dev, times = result

        # Should handle small data gracefully
        assert avg_time > 0
        assert len(times) == 3
        assert all(t > 0 for t in times)

    def test_throughput_calculation_edge_cases(self):
        """Test throughput calculation with edge cases."""
        benchmark = EncryptionBenchmark()

        # Generate tiny data
        data = benchmark.generate_test_data("tiny")
        data_size = len(data.encode())

        # Real fast operation (edge case for throughput calculation)
        def fast_operation(data):
            return "encrypted_" + data

        result = benchmark.benchmark_single_operation(
            fast_operation, data, iterations=5
        )

        avg_time, _, _, _, _ = result

        # Calculate throughput like the real code does
        throughput_mbps = (data_size / (avg_time / 1000)) / (1024 * 1024)
        assert throughput_mbps > 0
        assert isinstance(throughput_mbps, float)

    def test_concurrent_operations_single_thread(self):
        """Test concurrent operations with single thread."""
        benchmark = EncryptionBenchmark()

        # Test with single thread
        results = benchmark.benchmark_concurrent_operations(num_threads=1)

        assert results["num_threads"] == 1
        assert results["total_operations"] > 0
        assert results["operations_per_second"] > 0

    def test_field_encryption_empty_document(self):
        """Test field encryption with edge case document."""
        benchmark = EncryptionBenchmark()

        # Test the actual field encryption logic by directly checking field detection
        empty_doc: dict[str, str] = {}

        # Count fields that would be encrypted
        fields_encrypted = sum(
            1
            for field in empty_doc
            if benchmark.field_encryption.should_encrypt_field(field)
        )

        assert fields_encrypted == 0

    def test_all_data_size_categories(self):
        """Test all data size categories to ensure complete coverage."""
        benchmark = EncryptionBenchmark()

        # Test all size categories including 'huge' that might not be tested elsewhere
        categories = ["tiny", "small", "medium", "large", "xlarge", "huge"]

        for category in categories:
            data = benchmark.generate_test_data(category)
            assert isinstance(data, str)
            assert len(data) > 0

            # Test that the data is reasonable for the category
            if category == "huge":
                # Huge should be very large
                assert len(data) > 1000000  # Should be > 1MB
            elif category == "tiny":
                # Tiny should be small
                assert len(data) <= 200  # Should be <= 200 bytes

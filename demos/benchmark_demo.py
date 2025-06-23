"""
Demo script for Performance Benchmarks System

This script demonstrates the functionality of the performance benchmarks system
for translation quality monitoring.
"""

import asyncio
from datetime import datetime

from src.ai.translation.config import Language, TranslationMode
from src.ai.translation.validation import (
    BenchmarkLevel,
    PerformanceBenchmarkManager,
    TranslationMetrics,
)


async def demo_benchmarks():
    """Demonstrate performance benchmarks functionality."""

    # Initialize benchmark manager
    benchmark_manager = PerformanceBenchmarkManager()

    print("🎯 Initializing Performance Benchmarks System...")
    await benchmark_manager.initialize_benchmarks()

    # Create sample metrics
    metrics = TranslationMetrics(
        total_validations=100,
        passed_validations=99,  # 99% pass rate
        failed_validations=1,
        warnings=2,
        confidence_score=0.94,
        validation_time=1.2,  # 1.2 seconds
        semantic_similarity=0.93,
        terminology_accuracy=0.99,  # Meets the 99% requirement
        format_preservation=0.98,
        fluency_score=0.92,
    )

    print("\n📊 Sample Translation Metrics:")
    print(f"  - Pass Rate: {metrics.pass_rate:.1%}")
    print(f"  - Quality Score: {metrics.quality_score:.3f}")
    print(f"  - Validation Time: {metrics.validation_time}s")
    print(f"  - Terminology Accuracy: {metrics.terminology_accuracy:.1%}")

    # Evaluate against benchmarks
    print("\n🔍 Evaluating against Performance Benchmarks...")
    results = await benchmark_manager.evaluate_metrics(
        metrics=metrics,
        language_pair=("en", "es"),
        mode="medical",
        additional_metrics={
            "api_response_time": 0.45,  # 450ms (meets <500ms target)
            "uptime": 0.999,  # 99.9% uptime (meets requirement)
        },
    )

    # Display results
    print("\n📈 Benchmark Evaluation Results:")
    for result in results:
        status = "✅" if result.is_passing else "❌"
        level_emoji = {
            BenchmarkLevel.WORLD_CLASS: "🌟",
            BenchmarkLevel.EXCELLENT: "⭐",
            BenchmarkLevel.TARGET: "✓",
            BenchmarkLevel.MINIMUM: "⚠️",
        }

        print(f"\n  {status} {result.benchmark_name}")
        print(
            f"     Level: {level_emoji.get(result.achieved_level, '')} {result.achieved_level.value}"
        )
        print(f"     Value: {result.actual_value:.3f}")
        print(f"     Target Achievement: {result.target_percentage:.1f}%")

    # Generate report
    print("\n📄 Generating Performance Report...")
    report = await benchmark_manager.generate_benchmark_report(
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        output_format="markdown",
    )

    # Display summary from report
    print("\n📋 Report Preview:")
    print(report.split("\n## Benchmark Details")[0])  # Show just the summary

    # Show passing/failing summary
    passing = sum(1 for r in results if r.is_passing)
    exceeding = sum(1 for r in results if r.exceeds_target)
    total = len(results)

    print(f"\n✨ Summary:")
    print(f"   - Total Benchmarks: {total}")
    print(f"   - Passing: {passing} ({passing/total*100:.1f}%)")
    print(f"   - Exceeding Target: {exceeding}")

    print("\n✅ Performance Benchmarks Demo Complete!")


if __name__ == "__main__":
    asyncio.run(demo_benchmarks())

"""
Quality Assurance System Integration.

This module demonstrates how all quality assurance components work together.
"""

import asyncio
from typing import Any, Dict

from .ab_testing.ab_testing import ABTestingFramework
from .continuous_improvement import ContinuousImprovementEngine
from .feedback_collector import FeedbackCollector
from .metrics_tracker import MetricsTracker
from .quality_monitoring import QualityMonitoringSystem


class IntegratedQualitySystem:
    """Integrated quality assurance system combining all components."""

    def __init__(self) -> None:
        """Initialize all quality components."""
        # Core components
        self.metrics_tracker = MetricsTracker()
        self.feedback_collector = FeedbackCollector(
            metrics_tracker=self.metrics_tracker
        )
        self.improvement_engine = ContinuousImprovementEngine(
            metrics_tracker=self.metrics_tracker,
            feedback_collector=self.feedback_collector,
        )
        self.ab_framework = ABTestingFramework(metrics_tracker=self.metrics_tracker)
        self.monitoring = QualityMonitoringSystem()

    async def start_all_systems(self) -> None:
        """Start all background processes."""
        # Start metrics aggregation
        await self.metrics_tracker.start_background_aggregation()

        # Start feedback analysis
        await self.feedback_collector.start_background_analysis()

        # Start continuous improvement
        await self.improvement_engine.start_continuous_improvement()

        # A/B test monitoring starts automatically when tests are created

        print("All quality systems started")

    async def process_improvement_cycle(self) -> Dict[str, Any]:
        """Run a complete improvement cycle."""
        # 1. Detect patterns
        patterns = await self.improvement_engine.detect_patterns()

        # 2. Generate improvement proposals
        proposals = await self.improvement_engine.generate_improvements(patterns)

        # 3. Create A/B tests for proposals
        for proposal in proposals:
            test_config = await self.ab_framework.create_test_from_proposal(proposal)
            await self.ab_framework.start_test(test_config.test_id)

        # 4. Monitor tests
        active_tests = list(self.ab_framework.active_tests)

        # 5. Deploy successful improvements
        for test_id in active_tests:
            results = await self.ab_framework.get_test_results(
                test_id, include_intermediate=True
            )
            if results.get("winner"):
                # Deploy the improvement
                proposal_id = test_id.replace("test_", "")
                await self.improvement_engine.deploy_improvement(proposal_id)

        return {
            "patterns_detected": len(patterns),
            "proposals_generated": len(proposals),
            "tests_running": len(active_tests),
        }

    async def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health metrics."""
        # Get recent metrics summary
        recent_metrics = await self.metrics_tracker.get_recent_metrics(limit=10)

        # Get feedback analysis
        feedback_analysis = await self.feedback_collector.analyze_feedback()

        # Get improvement summary
        improvement_summary = await self.improvement_engine.get_improvement_summary()

        # Get active tests
        active_tests = list(self.ab_framework.active_tests)

        return {
            "metrics": {
                "recent_count": len(recent_metrics),
                "average_quality": (
                    sum(m.metrics.quality_score for m in recent_metrics)
                    / len(recent_metrics)
                    if recent_metrics
                    else 0
                ),
            },
            "feedback": {
                "total": feedback_analysis.total_feedback,
                "average_rating": feedback_analysis.average_rating,
                "sentiment": feedback_analysis.sentiment_score,
            },
            "improvements": improvement_summary,
            "active_tests": len(active_tests),
        }

    async def close_all_systems(self) -> None:
        """Gracefully shut down all systems."""
        await self.metrics_tracker.close()
        await self.feedback_collector.close()
        await self.improvement_engine.close()
        # A/B framework doesn't need explicit closure

        print("All quality systems closed")


# Example usage
async def main() -> None:
    """Demonstrate integrated quality system usage."""
    system = IntegratedQualitySystem()

    # Start all systems
    await system.start_all_systems()

    # Run improvement cycle
    cycle_results = await system.process_improvement_cycle()
    print(f"Improvement cycle: {cycle_results}")

    # Check system health
    health = await system.get_system_health()
    print(f"System health: {health}")

    # Graceful shutdown
    await system.close_all_systems()


if __name__ == "__main__":
    asyncio.run(main())

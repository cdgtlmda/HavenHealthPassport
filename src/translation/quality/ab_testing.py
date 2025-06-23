"""A/B Testing for Translation Quality."""

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ABTestVariant:
    """A variant in an A/B test."""

    variant_id: str
    name: str
    description: str
    config: Dict[str, Any]
    metrics: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    sample_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ABTest:
    """An A/B test for translation quality."""

    test_id: str
    name: str
    description: str
    variants: List[ABTestVariant]
    status: str
    start_date: datetime
    end_date: Optional[datetime] = None
    target_sample_size: int = 1000
    confidence_level: float = 0.95
    minimum_effect_size: float = 0.05
    winner: Optional[str] = None


class TranslationABTester:
    """Manages A/B testing for translation quality."""

    def __init__(self, storage_path: str):
        """Initialize A/B tester with storage path."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.active_tests: Dict[str, ABTest] = {}
        self.completed_tests: Dict[str, ABTest] = {}
        self._load_tests()

    def _load_tests(self) -> None:
        """Load tests from storage."""
        tests_file = self.storage_path / "ab_tests.json"
        if tests_file.exists():
            try:
                with open(tests_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Load active tests
                for test_data in data.get("active_tests", []):
                    test = self._deserialize_test(test_data)
                    if test:
                        self.active_tests[test.test_id] = test

                # Load completed tests
                for test_data in data.get("completed_tests", []):
                    test = self._deserialize_test(test_data)
                    if test:
                        self.completed_tests[test.test_id] = test

            except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                logger.error(f"Error loading tests: {e}")

    def _save_tests(self) -> None:
        """Save tests to storage."""
        tests_file = self.storage_path / "ab_tests.json"

        data = {
            "updated_at": datetime.now().isoformat(),
            "active_tests": [
                self._serialize_test(t) for t in self.active_tests.values()
            ],
            "completed_tests": [
                self._serialize_test(t) for t in self.completed_tests.values()
            ],
        }

        with open(tests_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _serialize_test(self, test: ABTest) -> Dict[str, Any]:
        """Serialize test to JSON-compatible format."""
        return {
            "test_id": test.test_id,
            "name": test.name,
            "description": test.description,
            "variants": [self._serialize_variant(v) for v in test.variants],
            "status": test.status,
            "start_date": test.start_date.isoformat(),
            "end_date": test.end_date.isoformat() if test.end_date else None,
            "target_sample_size": test.target_sample_size,
            "confidence_level": test.confidence_level,
            "minimum_effect_size": test.minimum_effect_size,
            "winner": test.winner,
        }

    def _serialize_variant(self, variant: ABTestVariant) -> Dict[str, Any]:
        """Serialize variant to JSON-compatible format."""
        return {
            "variant_id": variant.variant_id,
            "name": variant.name,
            "description": variant.description,
            "config": variant.config,
            "metrics": dict(variant.metrics),
            "sample_count": variant.sample_count,
            "created_at": variant.created_at.isoformat(),
        }

    def _deserialize_test(self, data: Dict[str, Any]) -> Optional[ABTest]:
        """Deserialize test from JSON data."""
        try:
            variants = [self._deserialize_variant(v) for v in data["variants"]]

            return ABTest(
                test_id=data["test_id"],
                name=data["name"],
                description=data["description"],
                variants=variants,
                status=data["status"],
                start_date=datetime.fromisoformat(data["start_date"]),
                end_date=(
                    datetime.fromisoformat(data["end_date"])
                    if data["end_date"]
                    else None
                ),
                target_sample_size=data["target_sample_size"],
                confidence_level=data["confidence_level"],
                minimum_effect_size=data["minimum_effect_size"],
                winner=data.get("winner"),
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Error deserializing test: {e}")
            return None

    def _deserialize_variant(self, data: Dict[str, Any]) -> ABTestVariant:
        """Deserialize variant from JSON data."""
        variant = ABTestVariant(
            variant_id=data["variant_id"],
            name=data["name"],
            description=data["description"],
            config=data["config"],
            sample_count=data["sample_count"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )

        # Restore metrics
        for metric_name, values in data.get("metrics", {}).items():
            variant.metrics[metric_name] = values

        return variant

    def create_test(
        self,
        name: str,
        description: str,
        variants: List[Dict[str, Any]],
        target_sample_size: int = 1000,
        confidence_level: float = 0.95,
        minimum_effect_size: float = 0.05,
    ) -> ABTest:
        """Create a new A/B test."""
        test_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create variant objects
        variant_objects = []
        for i, variant_config in enumerate(variants):
            variant = ABTestVariant(
                variant_id=f"{test_id}_v{i}",
                name=variant_config["name"],
                description=variant_config.get("description", ""),
                config=variant_config.get("config", {}),
            )
            variant_objects.append(variant)

        # Create test
        test = ABTest(
            test_id=test_id,
            name=name,
            description=description,
            variants=variant_objects,
            status="active",
            start_date=datetime.now(),
            target_sample_size=target_sample_size,
            confidence_level=confidence_level,
            minimum_effect_size=minimum_effect_size,
        )

        self.active_tests[test_id] = test
        self._save_tests()

        logger.info(f"Created A/B test: {test_id}")

        return test

    def get_variant_for_user(
        self, test_id: str, user_id: str
    ) -> Optional[ABTestVariant]:
        """Get variant assignment for a user."""
        test = self.active_tests.get(test_id)
        if not test or test.status != "active":
            return None

        # Use consistent hashing for variant assignment
        hash_input = f"{test_id}_{user_id}"
        hash_value = hash(hash_input)

        # Assign to variant based on hash
        variant_index = hash_value % len(test.variants)

        return test.variants[variant_index]

    def record_metric(
        self, test_id: str, variant_id: str, metric_name: str, value: float
    ) -> None:
        """Record a metric for a variant."""
        test = self.active_tests.get(test_id)
        if not test:
            logger.warning(f"Test {test_id} not found")
            return

        # Find variant
        variant = None
        for v in test.variants:
            if v.variant_id == variant_id:
                variant = v
                break

        if not variant:
            logger.warning(f"Variant {variant_id} not found in test {test_id}")
            return

        # Record metric
        variant.metrics[metric_name].append(value)
        variant.sample_count += 1

        # Check if test should be completed
        if variant.sample_count >= test.target_sample_size:
            self._check_test_completion(test)

        # Save periodically
        if variant.sample_count % 10 == 0:
            self._save_tests()

    def _check_test_completion(self, test: ABTest) -> None:
        """Check if test has enough data to determine winner."""
        # Check if all variants have enough samples
        min_samples = min(v.sample_count for v in test.variants)

        if min_samples < test.target_sample_size:
            return

        # Perform statistical analysis
        results = self._analyze_test_results(test)

        if results and results["significant"]:
            # We have a winner
            test.winner = results["winner"]
            test.status = "completed"
            test.end_date = datetime.now()

            # Move to completed tests
            self.completed_tests[test.test_id] = test
            del self.active_tests[test.test_id]

            self._save_tests()

            logger.info(f"Test {test.test_id} completed. Winner: {test.winner}")

    def _analyze_test_results(self, test: ABTest) -> Optional[Dict[str, Any]]:
        """Analyze test results for statistical significance."""
        if len(test.variants) != 2:
            # For simplicity, only handle A/B tests (2 variants)
            return None

        # Get primary metric (e.g., 'quality_score')
        primary_metric = "quality_score"

        variant_a = test.variants[0]
        variant_b = test.variants[1]

        metrics_a = variant_a.metrics.get(primary_metric, [])
        metrics_b = variant_b.metrics.get(primary_metric, [])

        if not metrics_a or not metrics_b:
            return None

        # Calculate means
        mean_a = statistics.mean(metrics_a)
        mean_b = statistics.mean(metrics_b)

        # Perform t-test (simplified - in production use scipy.stats)
        # This is a placeholder for the actual statistical test
        difference = abs(mean_a - mean_b)
        is_significant = difference > test.minimum_effect_size

        winner = variant_a.variant_id if mean_a > mean_b else variant_b.variant_id

        return {
            "significant": is_significant,
            "winner": winner,
            "mean_a": mean_a,
            "mean_b": mean_b,
            "difference": difference,
        }

    def get_test_results(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get current results of a test."""
        test = self.active_tests.get(test_id) or self.completed_tests.get(test_id)
        if not test:
            return None

        results: Dict[str, Any] = {
            "test_id": test_id,
            "name": test.name,
            "status": test.status,
            "start_date": test.start_date.isoformat(),
            "end_date": test.end_date.isoformat() if test.end_date else None,
            "variants": [],
        }

        for variant in test.variants:
            variant_stats = {
                "variant_id": variant.variant_id,
                "name": variant.name,
                "sample_count": variant.sample_count,
                "metrics": {},
            }

            # Calculate stats for each metric
            for metric_name, values in variant.metrics.items():
                if values:
                    metrics = variant_stats.get("metrics", {})
                    if isinstance(metrics, dict):
                        metrics[metric_name] = {
                            "mean": statistics.mean(values),
                            "median": statistics.median(values),
                            "std_dev": (
                                statistics.stdev(values) if len(values) > 1 else 0
                            ),
                            "min": min(values),
                            "max": max(values),
                            "count": len(values),
                        }

            variants_list = results.get("variants", [])
            if isinstance(variants_list, list):
                variants_list.append(variant_stats)

        # Add winner info if test is completed
        if test.status == "completed" and test.winner:
            results["winner"] = test.winner
            results["analysis"] = self._analyze_test_results(test)

        return results

    def pause_test(self, test_id: str) -> None:
        """Pause an active test."""
        if test_id in self.active_tests:
            self.active_tests[test_id].status = "paused"
            self._save_tests()

    def resume_test(self, test_id: str) -> None:
        """Resume a paused test."""
        if test_id in self.active_tests:
            self.active_tests[test_id].status = "active"
            self._save_tests()

    def get_active_tests(self) -> List[ABTest]:
        """Get all active tests."""
        return list(self.active_tests.values())

    def get_completed_tests(self) -> List[ABTest]:
        """Get all completed tests."""
        return list(self.completed_tests.values())

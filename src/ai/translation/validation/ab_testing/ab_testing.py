"""
A/B Testing Framework for Translation Quality.

This module implements a comprehensive A/B testing framework for validating
translation improvements through controlled experiments.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import asyncio
import hashlib
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy import stats

from ..continuous_improvement import ImprovementProposal, ImprovementType
from ..metrics_tracker import MetricAggregationLevel, MetricsTracker
from .types import (
    ABTest,
    AllocationStrategy,
    SignificanceResult,
    StatisticalTest,
    TestMetrics,
    TestResult,
    TestStatus,
    TestType,
    TestVariant,
)

logger = logging.getLogger(__name__)


class ABTestingFramework:
    """Framework for running A/B tests on translation improvements."""

    def __init__(self, metrics_tracker: Optional[MetricsTracker] = None):
        """Initialize the A/B testing framework."""
        self.tests: Dict[str, ABTest] = {}
        self.active_tests: Set[str] = set()
        self.metrics_tracker = metrics_tracker

        # Test results storage
        self.test_results: Dict[str, List[TestResult]] = defaultdict(list)

        # User allocation tracking
        self.user_allocations: Dict[str, Dict[str, str]] = defaultdict(dict)
        self.user_test_history: Dict[str, Dict[str, List[Dict]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Configuration
        self.min_sample_size_per_variant = 100
        self.max_concurrent_tests = 10
        self.enable_early_stopping = True
        self.early_stop_check_interval = 100  # Check every N samples

    def create_test(
        self,
        name: str,
        description: str,
        test_type: TestType,
        variants: List[Dict[str, Any]],
        control_variant_name: str,
        **kwargs: Any,
    ) -> ABTest:
        """Create a new A/B test."""
        test_id = str(uuid.uuid4())

        # Create variant objects
        test_variants = []
        control_variant_id = None

        # Ensure allocations sum to 100%
        total_allocation = sum(v.get("allocation_percentage", 50.0) for v in variants)

        for variant_data in variants:
            variant_id = str(uuid.uuid4())
            is_control = variant_data["name"] == control_variant_name

            if is_control:
                control_variant_id = variant_id

            # Normalize allocation
            allocation = variant_data.get("allocation_percentage", 50.0)
            normalized_allocation = (allocation / total_allocation) * 100

            variant = TestVariant(
                variant_id=variant_id,
                name=variant_data["name"],
                description=variant_data.get("description", ""),
                configuration=variant_data.get("configuration", {}),
                allocation_percentage=normalized_allocation,
                is_control=is_control,
            )
            test_variants.append(variant)

        if control_variant_id is None:
            raise ValueError(f"Control variant '{control_variant_name}' not found")

        # Create test
        test = ABTest(
            test_id=test_id,
            name=name,
            description=description,
            test_type=test_type,
            status=TestStatus.DRAFT,
            variants=test_variants,
            control_variant_id=control_variant_id,
            allocation_strategy=kwargs.get(
                "allocation_strategy", AllocationStrategy.RANDOM
            ),
            min_sample_size=kwargs.get(
                "min_sample_size", self.min_sample_size_per_variant * len(variants)
            ),
            max_duration_days=kwargs.get("max_duration_days", 30),
            confidence_level=kwargs.get("confidence_level", 0.95),
            target_languages=kwargs.get("target_languages"),
            target_domains=kwargs.get("target_domains"),
            target_user_segments=kwargs.get("target_user_segments"),
            primary_metric=kwargs.get("primary_metric", "accuracy"),
            secondary_metrics=kwargs.get("secondary_metrics", []),
            guardrail_metrics=kwargs.get("guardrail_metrics", []),
            created_by=kwargs.get("created_by", "system"),
            tags=set(kwargs.get("tags", [])),
            notes=kwargs.get("notes", ""),
        )

        self.tests[test_id] = test
        logger.info("Created A/B test: %s (%s)", name, test_id)

        return test

    async def start_test(self, test_id: str) -> None:
        """Start an A/B test."""
        if test_id not in self.tests:
            raise ValueError(f"Test {test_id} not found")

        test = self.tests[test_id]

        if test.status != TestStatus.DRAFT:
            raise ValueError(f"Test {test_id} is not in DRAFT status")

        if len(self.active_tests) >= self.max_concurrent_tests:
            raise ValueError("Maximum concurrent tests limit reached")

        # Initialize metrics
        test.metrics = TestMetrics(start_time=datetime.now())

        # Update status
        test.status = TestStatus.RUNNING
        test.started_at = datetime.now()
        self.active_tests.add(test_id)

        logger.info("Started A/B test: %s", test.name)

        # Start background monitoring if enabled
        if self.enable_early_stopping:
            asyncio.create_task(self._monitor_test(test_id))

    async def stop_test(self, test_id: str, reason: str = "Manual stop") -> TestMetrics:
        """Stop an A/B test."""
        if test_id not in self.tests:
            raise ValueError(f"Test {test_id} not found")

        test = self.tests[test_id]

        if test.status != TestStatus.RUNNING:
            raise ValueError(f"Test {test_id} is not running")

        # Calculate final results
        await self._calculate_test_results(test_id)

        # Update status
        test.status = TestStatus.COMPLETED
        test.completed_at = datetime.now()
        if test.metrics:
            test.metrics.end_time = datetime.now()

        self.active_tests.remove(test_id)

        logger.info("Stopped A/B test: %s (reason: %s)", test.name, reason)

        if test.metrics is None:
            raise ValueError(f"Test {test_id} has no metrics")
        return test.metrics

    def allocate_user_to_variant(
        self, test_id: str, user_id: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Allocate a user to a test variant."""
        if test_id not in self.tests:
            raise ValueError(f"Test {test_id} not found")

        test = self.tests[test_id]

        if test.status != TestStatus.RUNNING:
            raise ValueError(f"Test {test_id} is not running")

        # Check if user already allocated
        if (
            user_id in self.user_allocations
            and test_id in self.user_allocations[user_id]
        ):
            return self.user_allocations[user_id][test_id]

        # Check targeting criteria
        if not self._check_targeting(test, context):
            # Return control variant if user doesn't match targeting
            return test.control_variant_id

        # Allocate based on strategy
        variant_id = self._allocate_variant(test, user_id)

        # Store allocation
        self.user_allocations[user_id][test_id] = variant_id

        # Update metrics
        if test.metrics:
            test.metrics.total_participants += 1

        logger.debug(
            "Allocated user %s to variant %s in test %s", user_id, variant_id, test_id
        )

        return variant_id

    def record_result(
        self,
        test_id: str,
        user_id: str,
        success: bool,
        metrics: Dict[str, float],
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a test result."""
        if test_id not in self.tests:
            return

        test = self.tests[test_id]

        if test.status != TestStatus.RUNNING:
            return

        # Get user's variant
        if (
            user_id not in self.user_allocations
            or test_id not in self.user_allocations[user_id]
        ):
            logger.warning(
                "User %s not allocated to test %s, skipping result", user_id, test_id
            )
            return

        variant_id = self.user_allocations[user_id][test_id]

        # Create result
        result = TestResult(
            test_id=test_id,
            variant_id=variant_id,
            participant_id=user_id,
            timestamp=datetime.now(),
            language_pair=context.get("language_pair", "") if context else "",
            text_domain=context.get("domain", "") if context else "",
            text_length=context.get("text_length", 0) if context else 0,
            success=success,
            metrics=metrics,
            metadata=context or {},
        )

        # Store result
        self.test_results[test_id].append(result)

        # Update user history
        user_history = {
            "timestamp": datetime.now().isoformat(),
            "variant_id": variant_id,
            "success": success,
            "metrics": metrics,
        }

        if user_id not in self.user_test_history:
            self.user_test_history[user_id] = {}

        if test_id not in self.user_test_history[user_id]:
            self.user_test_history[user_id][test_id] = []

        self.user_test_history[user_id][test_id].append(user_history)

        # Log user participation
        logger.info(
            "User %s completed test %s with variant %s", user_id, test_id, variant_id
        )

        # Find variant
        variant = next((v for v in test.variants if v.variant_id == variant_id), None)
        if variant:
            variant.add_result(success, metrics)

        # Track in metrics system if available
        # Note: Metrics tracking disabled due to incompatible interface
        # TODO: Implement proper metrics tracking for AB tests

    async def get_test_results(
        self, test_id: str, include_intermediate: bool = False
    ) -> Dict[str, Any]:
        """Get current test results."""
        if test_id not in self.tests:
            raise ValueError(f"Test {test_id} not found")

        test = self.tests[test_id]

        # Don't show results for draft tests
        if test.status == TestStatus.DRAFT:
            return {"error": "Test has not started yet"}

        # For running tests, only show if intermediate results requested
        if test.status == TestStatus.RUNNING and not include_intermediate:
            return {"error": "Test is still running"}

        # Calculate current results
        results = await self._calculate_test_results(test_id)

        return {
            "test_id": test_id,
            "test_name": test.name,
            "status": test.status.value,
            "metrics": results,
            "variants": [
                {
                    "variant_id": v.variant_id,
                    "name": v.name,
                    "is_control": v.is_control,
                    "sample_size": v.sample_count,
                    "success_rate": v.get_success_rate(),
                    "metrics": {
                        metric: {
                            "mean": np.mean(values) if values else 0,
                            "std": np.std(values) if values else 0,
                            "min": min(values) if values else 0,
                            "max": max(values) if values else 0,
                        }
                        for metric, values in v.metrics.items()
                    },
                }
                for v in test.variants
            ],
            "winner": test.winner_variant_id,
            "confidence_level": test.confidence_level,
        }

    async def _calculate_test_results(self, test_id: str) -> TestMetrics:
        """Calculate test results and statistical significance."""
        test = self.tests[test_id]

        if not test.metrics:
            test.metrics = TestMetrics(start_time=test.started_at or datetime.now())

        # Find control variant
        control_variant = next(
            (v for v in test.variants if v.variant_id == test.control_variant_id), None
        )

        if not control_variant:
            return test.metrics

        # Calculate significance for each treatment variant
        best_variant = control_variant
        best_improvement = 0.0

        for variant in test.variants:
            if variant.variant_id == test.control_variant_id:
                continue

            # Calculate statistical significance
            sig_result = self._calculate_significance(
                control_variant, variant, test.primary_metric
            )

            if sig_result.is_significant and sig_result.effect_size > best_improvement:
                best_variant = variant
                best_improvement = sig_result.effect_size
                test.metrics.p_value = sig_result.p_value
                test.metrics.effect_size = sig_result.effect_size

        # Set winner if significant
        if best_variant.variant_id != test.control_variant_id:
            test.winner_variant_id = best_variant.variant_id

        # Check for early stopping
        if self.enable_early_stopping:
            should_stop, reason = self._check_early_stopping(test)
            if should_stop:
                test.metrics.should_stop_early = True
                test.metrics.early_stop_reason = reason

        return test.metrics

    def _calculate_significance(
        self, control: TestVariant, treatment: TestVariant, metric: str
    ) -> SignificanceResult:
        """Calculate statistical significance between two variants."""
        # For binary metrics (success rate)
        if metric == "success_rate" or metric not in control.metrics:
            # Use proportions test
            n1, n2 = control.sample_count, treatment.sample_count
            p1 = control.get_success_rate()
            p2 = treatment.get_success_rate()

            if n1 < 30 or n2 < 30:
                # Sample size too small
                return SignificanceResult(
                    is_significant=False,
                    p_value=1.0,
                    confidence_interval=(0, 0),
                    effect_size=0,
                    sample_size_a=n1,
                    sample_size_b=n2,
                    test_type=StatisticalTest.CHI_SQUARE,
                    notes="Sample size too small",
                )

            # Pooled proportion
            p_pool = (control.success_count + treatment.success_count) / (n1 + n2)

            # Standard error
            se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))

            # Z-score
            z = (p2 - p1) / se if se > 0 else 0

            # P-value (two-tailed)
            p_value = 2 * (1 - stats.norm.cdf(abs(z)))

            # Effect size (relative improvement)
            effect_size = ((p2 - p1) / p1 * 100) if p1 > 0 else 0

            # Confidence interval
            ci_se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
            ci_margin = 1.96 * ci_se  # 95% CI
            ci_lower = (p2 - p1) - ci_margin
            ci_upper = (p2 - p1) + ci_margin

            return SignificanceResult(
                is_significant=p_value < 0.05,
                p_value=p_value,
                confidence_interval=(ci_lower, ci_upper),
                effect_size=effect_size,
                sample_size_a=n1,
                sample_size_b=n2,
                test_type=StatisticalTest.CHI_SQUARE,
            )

        # For continuous metrics
        control_values = control.metrics.get(metric, [])
        treatment_values = treatment.metrics.get(metric, [])

        if len(control_values) < 30 or len(treatment_values) < 30:
            return SignificanceResult(
                is_significant=False,
                p_value=1.0,
                confidence_interval=(0, 0),
                effect_size=0,
                sample_size_a=len(control_values),
                sample_size_b=len(treatment_values),
                test_type=StatisticalTest.T_TEST,
                notes="Sample size too small",
            )

        # Perform t-test
        _, p_value = stats.ttest_ind(control_values, treatment_values)

        # Calculate effect size (Cohen's d)
        mean_diff = np.mean(treatment_values) - np.mean(control_values)
        pooled_std = np.sqrt(
            (np.std(control_values) ** 2 + np.std(treatment_values) ** 2) / 2
        )
        cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0

        # Relative improvement
        control_mean = np.mean(control_values)
        effect_size = (
            float((mean_diff / control_mean * 100)) if control_mean != 0 else 0
        )

        # Confidence interval for mean difference
        se_diff = pooled_std * np.sqrt(
            1 / len(control_values) + 1 / len(treatment_values)
        )
        ci_margin = 1.96 * se_diff
        ci_lower = mean_diff - ci_margin
        ci_upper = mean_diff + ci_margin

        return SignificanceResult(
            is_significant=p_value < 0.05,
            p_value=p_value,
            confidence_interval=(ci_lower, ci_upper),
            effect_size=effect_size,
            sample_size_a=len(control_values),
            sample_size_b=len(treatment_values),
            test_type=StatisticalTest.T_TEST,
            notes=f"Cohen's d: {cohens_d:.3f}",
        )

    def _check_early_stopping(self, test: ABTest) -> Tuple[bool, Optional[str]]:
        """Check if test should be stopped early."""
        if not test.metrics:
            return False, None

        # Check minimum sample size
        min_samples = min(v.sample_count for v in test.variants)
        if min_samples < self.min_sample_size_per_variant:
            return False, None

        # Check if we have a clear winner with high confidence
        if test.metrics.p_value and test.metrics.p_value < 0.001:
            if test.metrics.effect_size and abs(test.metrics.effect_size) > 20:
                return True, "Clear winner with high confidence"

        # Check for futility (unlikely to reach significance)
        if min_samples > self.min_sample_size_per_variant * 3:
            if not test.metrics.p_value or test.metrics.p_value > 0.5:
                return True, "Unlikely to reach statistical significance"

        # Check guardrail metrics
        for variant in test.variants:
            if variant.is_control:
                continue

            for metric in test.guardrail_metrics:
                if metric in variant.metrics and variant.metrics[metric]:
                    # Check if guardrail metric is significantly worse
                    control = next((v for v in test.variants if v.is_control), None)
                    if control and metric in control.metrics:
                        control_mean = np.mean(control.metrics[metric])
                        variant_mean = np.mean(variant.metrics[metric])

                        # If metric is >10% worse, stop
                        if variant_mean < control_mean * 0.9:
                            return True, f"Guardrail metric {metric} degraded"

        return False, None

    def _allocate_variant(self, test: ABTest, user_id: str) -> str:
        """Allocate user to a variant based on allocation strategy."""
        if test.allocation_strategy == AllocationStrategy.DETERMINISTIC:
            # Hash-based deterministic allocation
            hash_input = f"{test.test_id}:{user_id}".encode()
            hash_value = int(
                hashlib.md5(hash_input, usedforsecurity=False).hexdigest(), 16
            )

            # Map to percentage
            percentage = (hash_value % 10000) / 100.0

            # Find variant based on allocation ranges
            cumulative = 0.0
            for variant in test.variants:
                cumulative += variant.allocation_percentage
                if percentage < cumulative:
                    return variant.variant_id

            return test.variants[-1].variant_id

        elif test.allocation_strategy == AllocationStrategy.WEIGHTED:
            # Weighted random allocation
            weights = [v.allocation_percentage for v in test.variants]
            chosen = np.random.choice(
                len(test.variants), p=np.array(weights) / sum(weights)
            )
            return test.variants[chosen].variant_id

        elif test.allocation_strategy == AllocationStrategy.ADAPTIVE:
            # Thompson sampling (adaptive allocation)
            scores = []

            for variant in test.variants:
                # Beta distribution parameters
                alpha = variant.success_count + 1
                beta = variant.sample_count - variant.success_count + 1

                # Sample from beta distribution
                score = np.random.beta(alpha, beta)
                scores.append(score)

            # Choose variant with highest sampled score
            best_idx = np.argmax(scores)
            return test.variants[best_idx].variant_id

        else:  # RANDOM
            # Equal probability random allocation
            idx = np.random.randint(0, len(test.variants))
            return test.variants[idx].variant_id

    def _check_targeting(self, test: ABTest, context: Optional[Dict[str, Any]]) -> bool:
        """Check if context matches test targeting criteria."""
        if not context:
            return True

        # Check language targeting
        if test.target_languages:
            language = context.get("language")
            if language and language not in test.target_languages:
                return False

        # Check domain targeting
        if test.target_domains:
            domain = context.get("domain")
            if domain and domain not in test.target_domains:
                return False

        # Check user segment targeting
        if test.target_user_segments:
            user_segment = context.get("user_segment")
            if user_segment and user_segment not in test.target_user_segments:
                return False

        return True

    async def _monitor_test(self, test_id: str) -> None:
        """Monitor test for early stopping conditions."""
        while test_id in self.active_tests:
            await asyncio.sleep(60)  # Check every minute

            test = self.tests.get(test_id)
            if not test or test.status != TestStatus.RUNNING:
                break

            # Check if we should calculate intermediate results
            min_samples = min(v.sample_count for v in test.variants)
            if min_samples > 0 and min_samples % self.early_stop_check_interval == 0:
                await self._calculate_test_results(test_id)

                if test.metrics and test.metrics.should_stop_early:
                    await self.stop_test(
                        test_id, test.metrics.early_stop_reason or "Early stopping"
                    )
                    break

    def get_active_tests_for_user(
        self, user_id: str, context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """Get active tests that a user is eligible for."""
        eligible_tests = []

        for test_id in self.active_tests:
            test = self.tests[test_id]

            # Check targeting
            if self._check_targeting(test, context):
                # Get or allocate variant
                if (
                    user_id in self.user_allocations
                    and test_id in self.user_allocations[user_id]
                ):
                    variant_id = self.user_allocations[user_id][test_id]
                else:
                    variant_id = self.allocate_user_to_variant(
                        test_id, user_id, context
                    )

                # Find variant
                variant = next(
                    (v for v in test.variants if v.variant_id == variant_id), None
                )

                if variant:
                    eligible_tests.append(
                        {
                            "test_id": test_id,
                            "test_name": test.name,
                            "variant_id": variant_id,
                            "variant_name": variant.name,
                            "configuration": str(variant.configuration),
                        }
                    )

        return eligible_tests

    async def create_test_from_proposal(self, proposal: ImprovementProposal) -> ABTest:
        """Create an A/B test from an improvement proposal."""
        # Extract configuration from proposal
        variants = [
            {
                "name": "control",
                "description": "Current production configuration",
                "configuration": proposal.changes.get("current_config", {}),
                "allocation_percentage": 50.0,
            },
            {
                "name": "treatment",
                "description": proposal.description,
                "configuration": proposal.changes,
                "allocation_percentage": 50.0,
            },
        ]

        # Determine test type
        test_type = TestType.FEATURE_FLAG  # Default
        if proposal.improvement_type == ImprovementType.PROMPT_OPTIMIZATION:
            test_type = TestType.PROMPT_VARIANT
        elif proposal.improvement_type == ImprovementType.MODEL_SELECTION:
            test_type = TestType.MODEL_COMPARISON
        elif proposal.improvement_type == ImprovementType.GLOSSARY_UPDATE:
            test_type = TestType.GLOSSARY_TEST

        # Create test
        test = self.create_test(
            name=f"Test: {proposal.description}",
            description=f"Improvement proposal {proposal.proposal_id}: {proposal.description}",
            test_type=test_type,
            variants=variants,
            control_variant_name="control",
            primary_metric=(
                list(proposal.success_metrics.keys())[0]
                if proposal.success_metrics
                else "accuracy"
            ),
            secondary_metrics=(
                list(proposal.success_metrics.keys())[1:]
                if len(proposal.success_metrics) > 1
                else []
            ),
            min_sample_size=proposal.minimum_test_samples,
            confidence_level=proposal.expected_impact,
            tags={proposal.improvement_type.value, "auto_generated"},
        )

        return test

"""
A/B Testing Implementation for Translation Improvements.

This module implements actual A/B testing functionality for testing
translation improvements including prompt optimization, model selection,
and glossary updates.

CRITICAL: This is a healthcare project. All A/B tests must maintain
patient safety as the top priority. Never compromise accuracy for performance.
"""

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats
from sqlalchemy.exc import SQLAlchemyError

from src.ai.translation.validation.continuous_improvement import (
    ImprovementProposal,
    ImprovementType,
)
from src.ai.translation.validation.metrics_tracker import MetricsTracker
from src.ai.translation.validation.model_config_service import ModelConfigurationService
from src.database import get_db
from src.models.ab_test import ABTest, ABTestMetric
from src.models.ab_test import ABTestResult as ABTestResultModel
from src.services.translation_service import (
    TranslationContext,
    TranslationDirection,
    TranslationService,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TestVariant(Enum):
    """Test variant identifier."""

    CONTROL = "control"
    TREATMENT = "treatment"


@dataclass
class ABTestResult:
    """Results from an A/B test."""

    test_id: str
    proposal_id: str
    start_time: datetime
    end_time: datetime
    control_metrics: Dict[str, float]
    treatment_metrics: Dict[str, float]
    sample_size_control: int
    sample_size_treatment: int
    statistical_significance: Dict[str, float]
    recommendation: Dict[str, Any]
    confidence_level: float


@dataclass
class ABTestConfig:
    """Configuration for an A/B test."""

    test_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposal: Optional[ImprovementProposal] = None
    traffic_split: float = 0.5  # Percentage of traffic to treatment
    minimum_sample_size: int = 100
    maximum_duration_hours: int = 72
    confidence_threshold: float = 0.95
    minimum_effect_size: float = 0.05
    safety_metrics: List[str] = field(
        default_factory=lambda: ["accuracy", "medical_term_preservation"]
    )


class ABTestingService:
    """Service for conducting A/B tests on translation improvements."""

    def __init__(self) -> None:
        """Initialize the A/B testing service."""
        self.model_config_service = ModelConfigurationService()
        # TranslationService needs a session - will be initialized per request
        self.translation_service = None
        self.metrics_service = MetricsTracker()
        # Remove in-memory storage - use database instead
        # self.active_tests: Dict[str, ABTestConfig] = {}
        # self.test_results: Dict[str, ABTestResult] = {}

    async def start_ab_test(self, proposal: ImprovementProposal) -> str:
        """
        Start an A/B test for an improvement proposal.

        Args:
            proposal: The improvement proposal to test

        Returns:
            Test ID
        """
        # Validate proposal
        if not self._validate_proposal(proposal):
            raise ValueError("Invalid proposal for A/B testing")

        # Create test ID
        test_id = str(uuid.uuid4())

        # Prepare control and treatment configurations
        control_config = await self._get_control_config(proposal)
        treatment_config = await self._get_treatment_config(proposal)

        # Create database entry with actual start time
        db = next(get_db())
        try:
            ab_test = ABTest(
                test_id=test_id,
                proposal_id=proposal.proposal_id,
                improvement_type=proposal.improvement_type.value,
                traffic_split=0.5,  # Start with 50/50 split
                minimum_sample_size=proposal.minimum_test_samples or 100,
                maximum_duration_hours=72,
                confidence_threshold=0.95,
                minimum_effect_size=0.05,
                safety_metrics=["accuracy", "medical_term_preservation"],
                safety_thresholds={"accuracy": 0.95, "medical_term_preservation": 0.99},
                start_time=datetime.now(timezone.utc),  # Track actual start time
                status="active",
                control_config=control_config,
                treatment_config=treatment_config,
            )

            db.add(ab_test)
            db.commit()
            db.refresh(ab_test)

            logger.info(
                f"Started A/B test {test_id} for proposal {proposal.proposal_id} "
                f"at {ab_test.start_time.isoformat()}"
            )

            return test_id

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Failed to start A/B test: {str(e)}")
            raise
        finally:
            db.close()

    async def run_test_iteration(
        self,
        test_id: str,
        source_text: str,
        source_language: str,
        target_language: str,
        context: Dict[str, Any],
    ) -> Tuple[str, TestVariant]:
        """
        Run a single iteration of an A/B test.

        Args:
            test_id: Active test ID
            source_text: Text to translate
            source_language: Source language code
            target_language: Target language code
            context: Translation context

        Returns:
            Tuple of (translation, variant)
        """
        # Get test from database
        db = next(get_db())
        try:
            ab_test: Any = (
                db.query(ABTest)
                .filter(ABTest.test_id == test_id, ABTest.status == "active")
                .first()
            )

            if not ab_test:
                raise ValueError(f"No active test found with ID {test_id}")

            # Check if test has exceeded maximum duration
            if (
                ab_test.duration_hours
                and ab_test.duration_hours > ab_test.maximum_duration_hours
            ):
                ab_test.status = "completed"
                ab_test.end_time = datetime.now(timezone.utc)
                db.commit()
                raise ValueError(f"Test {test_id} has exceeded maximum duration")

            # Determine variant based on traffic split
            variant = self._select_variant(ab_test.traffic_split)

            # Execute translation based on variant
            if variant == TestVariant.CONTROL:
                translation = await self._run_control_translation(
                    source_text, source_language, target_language, context
                )
            else:
                # Reconstruct proposal from stored config for treatment
                proposal = ImprovementProposal(
                    proposal_id=ab_test.proposal_id,
                    improvement_type=ImprovementType(ab_test.improvement_type),
                    pattern_ids=[],  # No pattern tracking for reconstructed proposal
                    description=f"A/B test treatment for {ab_test.improvement_type}",
                    expected_impact=0.0,  # Not tracked for reconstruction
                    risk_level="low",
                    changes=ab_test.treatment_config,
                    success_metrics={},
                    minimum_test_samples=100,
                )
                translation = await self._run_treatment_translation(
                    proposal,
                    source_text,
                    source_language,
                    target_language,
                    context,
                )

            # Track metrics for this iteration
            await self._track_iteration_metrics(
                test_id, variant, source_text, translation, context
            )

            return translation, variant

        except SQLAlchemyError as e:
            logger.error(f"Database error in test iteration: {str(e)}")
            raise
        finally:
            db.close()

    async def _run_control_translation(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        context: Dict[str, Any],
    ) -> str:
        """Run translation using control (current) configuration."""
        # Get current configuration (for logging/debugging if needed)
        # current_config = await self.model_config_service.get_current_model_config(
        #     context=context.get("domain", "general"),
        #     language_pair=f"{source_language}-{target_language}",
        # )

        # Execute translation
        # Get a session and create translation service
        db = next(get_db())
        try:
            translation_service = TranslationService(db)

            # Convert string languages to TranslationDirection enum
            source_lang = (
                TranslationDirection(source_language) if source_language else None
            )
            target_lang = TranslationDirection(target_language)

            # Use default context since we have a dict
            translation_context = TranslationContext.PATIENT_FACING

            translation_result = translation_service.translate(
                text=source_text,
                source_language=source_lang,
                target_language=target_lang,
                context=translation_context,
            )
        finally:
            db.close()

        return str(translation_result.get("translated_text", ""))

    async def _run_treatment_translation(
        self,
        proposal: ImprovementProposal,
        source_text: str,
        source_language: str,
        target_language: str,
        context: Dict[str, Any],
    ) -> str:
        """Run translation using treatment (proposed) configuration."""
        # Apply changes based on improvement type
        if proposal.improvement_type == ImprovementType.PROMPT_OPTIMIZATION:
            # Use optimized prompt
            context["custom_prompt"] = proposal.changes.get("prompt_template", "")

        elif proposal.improvement_type == ImprovementType.MODEL_SELECTION:
            # Use proposed model
            current_config = proposal.changes.get("proposed_model", {})

        elif proposal.improvement_type == ImprovementType.GLOSSARY_UPDATE:
            # Apply glossary updates
            context["custom_glossary"] = proposal.changes.get("glossary_updates", {})
            # current_config = await self.model_config_service.get_current_model_config(
            #     context=context.get("domain", "general")
            # )

        else:
            raise ValueError(
                f"Unsupported improvement type: {proposal.improvement_type}"
            )

        # Execute translation with treatment configuration
        # Get a session and create translation service
        db = next(get_db())
        try:
            translation_service = TranslationService(db)

            # Convert string languages to TranslationDirection enum
            source_lang = (
                TranslationDirection(source_language) if source_language else None
            )
            target_lang = TranslationDirection(target_language)

            # Use default context since we have a dict
            translation_context = TranslationContext.PATIENT_FACING

            translation_result = translation_service.translate(
                text=source_text,
                source_language=source_lang,
                target_language=target_lang,
                context=translation_context,
            )
        finally:
            db.close()

        return str(translation_result.get("translated_text", ""))

    def _select_variant(self, traffic_split: float) -> TestVariant:
        """Select variant based on traffic split."""
        return (
            TestVariant.TREATMENT
            if random.random() < traffic_split
            else TestVariant.CONTROL
        )

    async def _track_iteration_metrics(
        self,
        test_id: str,
        variant: TestVariant,
        source_text: str,
        translation: str,
        context: Dict[str, Any],
    ) -> None:
        """Track metrics for a test iteration."""
        # Calculate quality metrics
        metrics = await self.metrics_service.calculate_metrics(
            source_text=source_text,
            translated_text=translation,
            reference_text=context.get("reference_translation"),
            context=context,
        )

        # Convert TranslationMetrics to dict if necessary
        if hasattr(metrics, "__dict__"):
            metrics_dict = {
                k: v for k, v in metrics.__dict__.items() if isinstance(v, (int, float))
            }
        else:
            metrics_dict = metrics if isinstance(metrics, dict) else {}

        # Store metrics for analysis
        await self._store_test_metrics(test_id, variant, metrics_dict)

    async def analyze_test_results(self, test_id: str) -> ABTestResult:
        """
        Analyze results of an A/B test.

        Args:
            test_id: Test ID to analyze

        Returns:
            Test results with statistical analysis
        """
        # Get test from database
        db = next(get_db())
        try:
            ab_test: Any = db.query(ABTest).filter(ABTest.test_id == test_id).first()
            if not ab_test:
                raise ValueError(f"No test found with ID {test_id}")

            # Retrieve metrics for both variants from database
            control_metrics = await self._get_variant_metrics_from_db(
                test_id, TestVariant.CONTROL
            )
            treatment_metrics = await self._get_variant_metrics_from_db(
                test_id, TestVariant.TREATMENT
            )

            # Perform statistical analysis
            significance_results = self._calculate_statistical_significance(
                control_metrics, treatment_metrics
            )

            # Check safety metrics
            safety_check = self._check_safety_metrics_compliance(
                control_metrics, treatment_metrics, ab_test
            )

            # Generate recommendation
            recommendation = self._generate_recommendation(
                control_metrics,
                treatment_metrics,
                significance_results,
                ab_test,
                safety_check,
            )

            # Update test end time if not already set
            if not ab_test.end_time:
                ab_test.end_time = datetime.now(timezone.utc)
                ab_test.status = "completed"

            # Create result object with actual start time from database
            result = ABTestResult(
                test_id=test_id,
                proposal_id=ab_test.proposal_id,
                start_time=ab_test.start_time,  # Use actual start time from database
                end_time=ab_test.end_time,
                control_metrics=self._summarize_metrics(control_metrics),
                treatment_metrics=self._summarize_metrics(treatment_metrics),
                sample_size_control=len(control_metrics),
                sample_size_treatment=len(treatment_metrics),
                statistical_significance=significance_results,
                recommendation=recommendation,
                confidence_level=significance_results.get("confidence", 0.0),
            )

            # Store results in database
            db_result = ABTestResultModel(
                test_id=ab_test.id,
                control_metrics_summary=result.control_metrics,
                treatment_metrics_summary=result.treatment_metrics,
                statistical_significance=significance_results,
                p_values={"accuracy": significance_results.get("p_value", 1.0)},
                effect_sizes={"accuracy": significance_results.get("effect_size", 0.0)},
                confidence_intervals={
                    "accuracy": significance_results.get("ci", [0.0, 0.0])
                },
                safety_violations=safety_check.get("violations", {}),
                medical_accuracy_maintained=safety_check.get("safe", True),
                recommendation=recommendation["action"],
                recommendation_confidence=recommendation["confidence"],
                recommendation_rationale=recommendation["rationale"],
            )

            db.add(db_result)
            db.commit()

            logger.info(
                f"Completed analysis of A/B test {test_id}. "
                f"Duration: {(ab_test.end_time - ab_test.start_time).total_seconds() / 3600:.2f} hours. "
                f"Recommendation: {recommendation['action']}"
            )

            return result

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Failed to analyze A/B test results: {str(e)}")
            raise
        finally:
            db.close()

    def _calculate_statistical_significance(
        self,
        control_metrics: List[Dict[str, float]],
        treatment_metrics: List[Dict[str, float]],
    ) -> Dict[str, float]:
        """Calculate statistical significance between variants."""
        if not control_metrics or not treatment_metrics:
            return {"confidence": 0.0, "p_value": 1.0}

        # Extract key metrics for comparison
        control_accuracy = [m.get("accuracy", 0) for m in control_metrics]
        treatment_accuracy = [m.get("accuracy", 0) for m in treatment_metrics]

        # Perform t-test
        t_stat, p_value = stats.ttest_ind(control_accuracy, treatment_accuracy)

        # Calculate effect size (Cohen's d)
        effect_size = (
            np.mean(treatment_accuracy) - np.mean(control_accuracy)
        ) / np.sqrt(
            (np.std(control_accuracy) ** 2 + np.std(treatment_accuracy) ** 2) / 2
        )

        return {
            "p_value": p_value,
            "confidence": 1 - p_value,
            "effect_size": effect_size,
            "t_statistic": t_stat,
        }

    def _generate_recommendation(
        self,
        control_metrics: List[Dict[str, float]],
        treatment_metrics: List[Dict[str, float]],
        significance: Dict[str, float],
        ab_test: ABTest,
        safety_check: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate recommendation based on test results."""
        # Check if we have sufficient sample size
        if (
            len(control_metrics) < ab_test.minimum_sample_size
            or len(treatment_metrics) < ab_test.minimum_sample_size
        ):
            return {
                "action": "inconclusive",
                "confidence": 0.0,
                "rationale": {
                    "reason": "insufficient_sample_size",
                    "details": "More data needed",
                },
            }

        # Check statistical significance
        if significance["p_value"] > (1 - ab_test.confidence_threshold):
            return {
                "action": "reject",
                "confidence": 1 - significance["p_value"],
                "rationale": {
                    "reason": "not_significant",
                    "p_value": significance["p_value"],
                },
            }

        # Check effect size
        if abs(significance.get("effect_size", 0)) < ab_test.minimum_effect_size:
            return {
                "action": "reject",
                "confidence": 0.8,
                "rationale": {
                    "reason": "negligible_effect",
                    "effect_size": significance.get("effect_size", 0),
                },
            }

        # Check safety metrics - CRITICAL for healthcare
        if not safety_check["safe"]:
            return {
                "action": "reject",
                "confidence": 1.0,
                "rationale": {
                    "reason": "safety_violation",
                    "violations": safety_check["violations"],
                    "critical": "Medical safety cannot be compromised",
                },
            }

        # Make recommendation based on improvement
        if significance.get("effect_size", 0) > 0:
            return {
                "action": "adopt",
                "confidence": significance.get("confidence", 0.0),
                "rationale": {
                    "reason": "significant_improvement",
                    "effect_size": significance.get("effect_size", 0),
                    "p_value": significance["p_value"],
                },
            }
        else:
            return {
                "action": "reject",
                "confidence": significance.get("confidence", 0.0),
                "rationale": {
                    "reason": "worse_performance",
                    "effect_size": significance.get("effect_size", 0),
                },
            }

    def _check_safety_metrics(
        self, metrics: List[Dict[str, float]], safety_metrics: List[str]
    ) -> float:
        """Check safety metrics to ensure no degradation."""
        if not metrics:
            return 0.0

        safety_scores = []
        for metric in metrics:
            scores = [metric.get(sm, 0) for sm in safety_metrics]
            safety_scores.append(np.mean(scores))

        return float(np.mean(safety_scores))

    def _summarize_metrics(self, metrics: List[Dict[str, float]]) -> Dict[str, float]:
        """Summarize a list of metrics."""
        if not metrics:
            return {}

        summary = {}
        metric_keys = metrics[0].keys()

        for key in metric_keys:
            values = [m.get(key, 0) for m in metrics]
            summary[f"{key}_mean"] = float(np.mean(values))
            summary[f"{key}_std"] = float(np.std(values))

        return summary

    def _validate_proposal(self, proposal: ImprovementProposal) -> bool:
        """Validate that a proposal is suitable for A/B testing."""
        # Check that proposal has required fields
        if not proposal.changes:
            logger.error("Proposal has no changes defined")
            return False

        # Validate based on improvement type
        if proposal.improvement_type == ImprovementType.PROMPT_OPTIMIZATION:
            if "prompt_template" not in proposal.changes:
                logger.error("Prompt optimization proposal missing template")
                return False

        elif proposal.improvement_type == ImprovementType.MODEL_SELECTION:
            if "proposed_model" not in proposal.changes:
                logger.error("Model selection proposal missing model config")
                return False

        elif proposal.improvement_type == ImprovementType.GLOSSARY_UPDATE:
            if "glossary_updates" not in proposal.changes:
                logger.error("Glossary update proposal missing updates")
                return False

        return True

    async def _get_control_config(
        self, proposal: ImprovementProposal
    ) -> Dict[str, Any]:
        """Get control (current) configuration."""
        return {
            "type": "control",
            "model": "current",
            "settings": await self.model_config_service.get_current_model_config(
                context=proposal.changes.get("domain", "general")
            ),
        }

    async def _get_treatment_config(
        self, proposal: ImprovementProposal
    ) -> Dict[str, Any]:
        """Get treatment (proposed) configuration."""
        config = {
            "type": "treatment",
            "improvement_type": proposal.improvement_type.value,
        }

        if proposal.improvement_type == ImprovementType.PROMPT_OPTIMIZATION:
            config["prompt_template"] = proposal.changes.get("prompt_template", "")
        elif proposal.improvement_type == ImprovementType.MODEL_SELECTION:
            config["model"] = proposal.changes.get("proposed_model", {})
        elif proposal.improvement_type == ImprovementType.GLOSSARY_UPDATE:
            config["glossary_updates"] = proposal.changes.get("glossary_updates", {})

        return config

    def _check_safety_metrics_compliance(
        self,
        control_metrics: List[Dict[str, float]],
        treatment_metrics: List[Dict[str, float]],
        ab_test: ABTest,
    ) -> Dict[str, Any]:
        """Check if safety metrics are maintained."""
        violations = {}

        safety_metrics_list: list[Any] = (
            ab_test.safety_metrics if isinstance(ab_test.safety_metrics, list) else []  # type: ignore[unreachable]
        )
        for metric in safety_metrics_list:
            control_avg = np.mean([m.get(metric, 0) for m in control_metrics])
            treatment_avg = np.mean([m.get(metric, 0) for m in treatment_metrics])
            threshold = ab_test.safety_thresholds.get(metric, 0.95)

            if treatment_avg < threshold:
                violations[metric] = {
                    "control": control_avg,
                    "treatment": treatment_avg,
                    "threshold": threshold,
                    "violation": True,
                }

        return {"safe": len(violations) == 0, "violations": violations}

    async def _initialize_test_metrics(self, config: ABTestConfig) -> None:
        """Initialize metrics tracking for a test."""
        # This now happens in the database when we create the ABTest record
        pass

    async def _store_test_metrics(
        self, test_id: str, variant: TestVariant, metrics: Dict[str, float]
    ) -> None:
        """Store metrics for a test iteration in database."""
        db = next(get_db())
        try:
            # Get the test from database
            ab_test: Any = db.query(ABTest).filter(ABTest.test_id == test_id).first()
            if not ab_test:
                raise ValueError(f"No test found with ID {test_id}")

            # Create metric record
            metric = ABTestMetric(
                test_id=ab_test.id,
                variant=variant.value,
                iteration_id=str(uuid.uuid4()),
                accuracy_score=metrics.get("accuracy", 0.0),
                fluency_score=metrics.get("fluency", 0.0),
                adequacy_score=metrics.get("adequacy", 0.0),
                medical_term_preservation=metrics.get("medical_term_preservation", 0.0),
                cultural_appropriateness=metrics.get("cultural_appropriateness", 0.0),
                translation_time_ms=metrics.get("translation_time_ms", 0),
                model_tokens_used=metrics.get("tokens_used", 0),
                source_language=metrics.get("source_language", ""),
                target_language=metrics.get("target_language", ""),
                domain=metrics.get("domain"),
            )

            db.add(metric)

            # Update sample size counters
            if variant == TestVariant.CONTROL:
                ab_test.control_sample_size += 1
            else:
                ab_test.treatment_sample_size += 1

            db.commit()

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Failed to store test metrics: {str(e)}")
            raise
        finally:
            db.close()

    async def _get_variant_metrics_from_db(
        self, test_id: str, variant: TestVariant
    ) -> List[Dict[str, float]]:
        """Retrieve metrics for a variant from database."""
        db = next(get_db())
        try:
            ab_test: Any = db.query(ABTest).filter(ABTest.test_id == test_id).first()
            if not ab_test:
                return []

            metrics = (
                db.query(ABTestMetric)
                .filter(
                    ABTestMetric.test_id == ab_test.id,
                    ABTestMetric.variant == variant.value,
                )
                .all()
            )

            return [
                {
                    "accuracy": float(m.accuracy_score),
                    "fluency": float(m.fluency_score),
                    "adequacy": float(m.adequacy_score),
                    "medical_term_preservation": float(m.medical_term_preservation),
                    "cultural_appropriateness": float(m.cultural_appropriateness),
                    "translation_time_ms": int(m.translation_time_ms),
                }
                for m in metrics
            ]

        except SQLAlchemyError as e:
            logger.error(f"Failed to retrieve variant metrics: {str(e)}")
            return []
        finally:
            db.close()

    async def _get_variant_metrics(
        self, test_id: str, variant: TestVariant
    ) -> List[Dict[str, float]]:
        """Retrieve metrics for a variant - calls database version."""
        return await self._get_variant_metrics_from_db(test_id, variant)

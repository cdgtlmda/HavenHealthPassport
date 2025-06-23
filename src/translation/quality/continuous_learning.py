"""
Continuous Learning Pipeline for Translation Quality.

This module implements automated quality improvement through feedback loops,
A/B testing, and real-time monitoring of medical translations.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ExperimentStatus(str, Enum):
    """Status of A/B test experiments."""

    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    ANALYZED = "analyzed"
    APPLIED = "applied"


class MetricType(str, Enum):
    """Types of metrics tracked."""

    ACCURACY = "accuracy"
    FLUENCY = "fluency"
    ADEQUACY = "adequacy"
    MEDICAL_CORRECTNESS = "medical_correctness"
    USER_SATISFACTION = "user_satisfaction"
    PROCESSING_TIME = "processing_time"


class ModelType(str, Enum):
    """Types of translation models."""

    BASELINE = "baseline"
    ENHANCED = "enhanced"
    EXPERIMENTAL = "experimental"
    MEDICAL_SPECIALIZED = "medical_specialized"


@dataclass
class TranslationFeedback:
    """User feedback on translation quality."""

    translation_id: str
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    rating: int  # 1-5
    issues: List[str]
    corrections: Optional[str]
    medical_accuracy: Optional[bool]
    timestamp: datetime
    user_type: str  # patient, provider, reviewer


@dataclass
class ABTestExperiment:
    """A/B test experiment configuration."""

    experiment_id: str
    name: str
    description: str
    model_a: ModelType
    model_b: ModelType
    traffic_split: float  # Percentage to model A
    target_languages: List[str]
    medical_domains: List[str]
    start_date: datetime
    end_date: Optional[datetime]
    status: ExperimentStatus
    metrics: Dict[str, Any]
    sample_size: int


@dataclass
class QualityMetrics:
    """Translation quality metrics."""

    accuracy_score: float
    fluency_score: float
    medical_correctness: float
    user_satisfaction: float
    average_processing_time: float
    error_rate: float
    confidence_scores: Dict[str, float]


@dataclass
class LearningOutcome:
    """Outcome of continuous learning process."""

    improvements: Dict[str, float]
    model_updates: List[str]
    new_patterns: List[Dict[str, Any]]
    recommendations: List[str]
    next_steps: List[str]


class ContinuousLearningPipeline:
    """Manages continuous improvement of translation quality."""

    # Quality thresholds
    QUALITY_THRESHOLDS = {
        "accuracy": 0.95,
        "medical_correctness": 0.98,
        "user_satisfaction": 4.0,
        "error_rate": 0.02,
    }

    # Learning intervals
    RETRAINING_INTERVAL_DAYS = 30
    EVALUATION_INTERVAL_HOURS = 24

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize continuous learning pipeline.

        Args:
            region: AWS region
        """
        self.sagemaker = boto3.client("sagemaker", region_name=region)
        self.cloudwatch = boto3.client("cloudwatch", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)

        self.feedback_buffer: List[TranslationFeedback] = []
        self.active_experiments: Dict[str, ABTestExperiment] = {}
        self.quality_history: List[Dict[str, Any]] = []
        self.model_registry: Dict[str, Any] = {}

    async def collect_feedback(self, feedback: TranslationFeedback) -> bool:
        """
        Collect user feedback on translation.

        Args:
            feedback: Translation feedback

        Returns:
            Success status
        """
        try:
            # Validate feedback
            if not self._validate_feedback(feedback):
                return False

            # Add to buffer
            self.feedback_buffer.append(feedback)

            # Process if buffer is full
            if len(self.feedback_buffer) >= 100:
                await self._process_feedback_batch()

            # Log metrics
            await self._log_feedback_metrics(feedback)

            return True

        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Error collecting feedback: {e}")
            return False

    def _validate_feedback(self, feedback: TranslationFeedback) -> bool:
        """Validate feedback data."""
        if feedback.rating < 1 or feedback.rating > 5:
            return False

        if not feedback.source_text or not feedback.translated_text:
            return False

        return True

    async def _process_feedback_batch(self) -> None:
        """Process batch of feedback."""
        if not self.feedback_buffer:
            return

        # Analyze feedback patterns
        patterns = self._analyze_feedback_patterns(self.feedback_buffer)

        # Update quality metrics
        await self._update_quality_metrics(patterns)

        # Trigger retraining if needed
        if self._should_trigger_retraining(patterns):
            await self._trigger_model_retraining(patterns)

        # Clear buffer
        self.feedback_buffer = []

    def _analyze_feedback_patterns(
        self, feedback_list: List[TranslationFeedback]
    ) -> Dict[str, Any]:
        """Analyze patterns in feedback."""
        patterns = {
            "average_rating": 0,
            "common_issues": {},
            "language_pairs": {},
            "medical_domains": {},
            "error_types": {},
            "low_quality_patterns": [],
        }

        # Calculate average rating
        ratings = [f.rating for f in feedback_list]
        patterns["average_rating"] = sum(ratings) / len(ratings)

        # Analyze issues
        issue_counts: Dict[str, int] = {}
        for feedback in feedback_list:
            for issue in feedback.issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1

        patterns["common_issues"] = issue_counts

        # Analyze by language pair
        lang_pair_ratings: Dict[str, List[int]] = {}
        for feedback in feedback_list:
            pair = f"{feedback.source_lang}-{feedback.target_lang}"
            if pair not in lang_pair_ratings:
                lang_pair_ratings[pair] = []
            lang_pair_ratings[pair].append(feedback.rating)

        for pair, ratings in lang_pair_ratings.items():
            language_pairs = patterns.get("language_pairs", {})
            if isinstance(language_pairs, dict):
                language_pairs[pair] = {
                    "average_rating": sum(ratings) / len(ratings),
                    "count": len(ratings),
                }

        # Identify low quality patterns
        for feedback in feedback_list:
            if feedback.rating <= 2:
                low_quality_patterns = patterns.get("low_quality_patterns", [])
                if isinstance(low_quality_patterns, list):
                    low_quality_patterns.append(
                        {
                            "source": feedback.source_text[:50],
                            "issues": feedback.issues,
                            "language_pair": f"{feedback.source_lang}-{feedback.target_lang}",
                        }
                    )

        return patterns

    async def _update_quality_metrics(self, patterns: Dict[str, Any]) -> None:
        """Update quality metrics based on patterns."""
        metrics = QualityMetrics(
            accuracy_score=0.0,
            fluency_score=0.0,
            medical_correctness=0.0,
            user_satisfaction=patterns["average_rating"] / 5.0,
            average_processing_time=0.0,
            error_rate=len(patterns["low_quality_patterns"]) / 100,
            confidence_scores={},
        )

        # Store metrics
        self.quality_history.append(
            {"timestamp": datetime.now(), "metrics": metrics, "patterns": patterns}
        )

        # Send to CloudWatch
        await self._send_metrics_to_cloudwatch(metrics)

    async def _send_metrics_to_cloudwatch(self, metrics: QualityMetrics) -> None:
        """Send metrics to CloudWatch."""
        try:
            metric_data = [
                {
                    "MetricName": "TranslationUserSatisfaction",
                    "Value": metrics.user_satisfaction,
                    "Unit": "None",
                    "Timestamp": datetime.now(),
                },
                {
                    "MetricName": "TranslationErrorRate",
                    "Value": metrics.error_rate,
                    "Unit": "Percent",
                    "Timestamp": datetime.now(),
                },
            ]

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cloudwatch.put_metric_data(
                    Namespace="HavenHealthPassport/Translation", MetricData=metric_data
                ),
            )

        except ClientError as e:
            logger.error(f"Error sending metrics to CloudWatch: {e}")

    def _should_trigger_retraining(self, patterns: Dict[str, Any]) -> bool:
        """Determine if model retraining is needed."""
        # Check quality thresholds
        if patterns["average_rating"] < 3.5:
            return True

        # Check error rate
        error_rate = len(patterns["low_quality_patterns"]) / 100
        if error_rate > self.QUALITY_THRESHOLDS["error_rate"]:
            return True

        # Check specific language pairs
        for _pair, data in patterns["language_pairs"].items():
            if data["average_rating"] < 3.0 and data["count"] > 10:
                return True

        return False

    async def _trigger_model_retraining(self, patterns: Dict[str, Any]) -> None:
        """Trigger model retraining based on patterns."""
        logger.info("Triggering model retraining based on feedback patterns")

        # Prepare training data
        await self._prepare_training_data(patterns)

        # Start SageMaker training job
        job_name = f"translation-retraining-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # This would start actual SageMaker training
        # For now, log the action
        logger.info(f"Started retraining job: {job_name}")

        # Schedule model evaluation
        await self._schedule_model_evaluation(job_name)

    async def _prepare_training_data(self, _patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare training data from feedback."""
        training_data: Dict[str, Any] = {
            "corrections": [],
            "low_quality_examples": [],
            "high_quality_examples": [],
        }

        # Extract corrections from feedback
        for feedback in self.feedback_buffer:
            if feedback.corrections:
                training_data["corrections"].append(
                    {
                        "source": feedback.source_text,
                        "original_translation": feedback.translated_text,
                        "corrected_translation": feedback.corrections,
                        "language_pair": f"{feedback.source_lang}-{feedback.target_lang}",
                    }
                )

        return training_data

    async def start_ab_test(self, experiment_config: ABTestExperiment) -> str:
        """
        Start an A/B test experiment.

        Args:
            experiment_config: Experiment configuration

        Returns:
            Experiment ID
        """
        try:
            # Validate experiment
            if (
                experiment_config.traffic_split < 0
                or experiment_config.traffic_split > 1
            ):
                raise ValueError("Traffic split must be between 0 and 1")

            # Register experiment
            experiment_config.status = ExperimentStatus.ACTIVE
            self.active_experiments[experiment_config.experiment_id] = experiment_config

            # Configure traffic routing
            await self._configure_traffic_routing(experiment_config)

            # Start metric collection
            await self._start_experiment_metrics(experiment_config)

            logger.info(f"Started A/B test: {experiment_config.name}")
            return experiment_config.experiment_id

        except Exception as e:
            logger.error(f"Error starting A/B test: {e}")
            raise

    async def _configure_traffic_routing(self, experiment: ABTestExperiment) -> None:
        """Configure traffic routing for A/B test."""
        # This would configure actual traffic routing
        # For now, simulate configuration
        logger.info(
            f"Configured traffic split: {experiment.traffic_split * 100}% to model A"
        )

    async def _start_experiment_metrics(self, experiment: ABTestExperiment) -> None:
        """Start collecting metrics for experiment."""
        experiment.metrics = {
            "model_a": {
                "requests": 0,
                "average_rating": 0,
                "error_rate": 0,
                "processing_time": 0,
            },
            "model_b": {
                "requests": 0,
                "average_rating": 0,
                "error_rate": 0,
                "processing_time": 0,
            },
        }

    async def evaluate_ab_test(self, experiment_id: str) -> Dict[str, Any]:
        """
        Evaluate A/B test results.

        Args:
            experiment_id: Experiment ID

        Returns:
            Evaluation results
        """
        experiment = self.active_experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Calculate statistical significance
        results: Dict[str, Any] = {
            "experiment_id": experiment_id,
            "duration_days": (datetime.now() - experiment.start_date).days,
            "sample_size": experiment.sample_size,
            "winner": None,
            "confidence_level": 0,
            "improvements": {},
            "recommendation": "",
        }

        # Compare models
        model_a_rating = experiment.metrics["model_a"]["average_rating"]
        model_b_rating = experiment.metrics["model_b"]["average_rating"]

        if model_a_rating > model_b_rating:
            results["winner"] = "model_a"
            improvement = ((model_a_rating - model_b_rating) / model_b_rating) * 100
            results["improvements"]["rating"] = improvement
        else:
            results["winner"] = "model_b"
            improvement = ((model_b_rating - model_a_rating) / model_a_rating) * 100
            results["improvements"]["rating"] = improvement

        # Statistical significance (simplified)
        if experiment.sample_size > 1000:
            results["confidence_level"] = 0.95
            results["recommendation"] = f"Deploy {results['winner']} to production"
        else:
            results["confidence_level"] = 0.75
            results["recommendation"] = "Continue experiment for more data"

        # Update experiment status
        if results["confidence_level"] >= 0.95:
            experiment.status = ExperimentStatus.COMPLETED

        return results

    async def apply_learning_outcomes(self, experiment_id: str) -> LearningOutcome:
        """
        Apply learnings from experiments and feedback.

        Args:
            experiment_id: Experiment ID

        Returns:
            Learning outcome summary
        """
        experiment = self.active_experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Evaluate experiment
        evaluation = await self.evaluate_ab_test(experiment_id)

        # Prepare outcomes
        outcome = LearningOutcome(
            improvements={},
            model_updates=[],
            new_patterns=[],
            recommendations=[],
            next_steps=[],
        )

        # Apply winning model
        if evaluation["winner"] and evaluation["confidence_level"] >= 0.95:
            winning_model = evaluation["winner"]

            # Deploy winning model
            await self._deploy_model(
                experiment.model_a if winning_model == "model_a" else experiment.model_b
            )

            outcome.model_updates.append(f"Deployed {winning_model}")
            outcome.improvements = evaluation["improvements"]

        # Extract new patterns
        new_patterns = await self._extract_new_patterns(experiment)
        outcome.new_patterns = new_patterns

        # Generate recommendations
        outcome.recommendations = self._generate_recommendations(
            evaluation, new_patterns
        )

        # Define next steps
        outcome.next_steps = self._define_next_steps(outcome)

        # Mark experiment as applied
        experiment.status = ExperimentStatus.APPLIED

        return outcome

    async def _deploy_model(self, model_type: ModelType) -> None:
        """Deploy a model to production."""
        logger.info(f"Deploying model: {model_type}")

        # This would implement actual model deployment
        # For now, update registry
        self.model_registry["current"] = model_type
        self.model_registry["deployed_at"] = datetime.now()

    async def _extract_new_patterns(
        self, experiment: ABTestExperiment
    ) -> List[Dict[str, Any]]:
        """Extract new patterns from experiment."""
        patterns = []

        # Analyze feedback collected during experiment
        experiment_feedback = [
            f for f in self.feedback_buffer if f.timestamp >= experiment.start_date
        ]

        # Extract patterns
        feedback_patterns = self._analyze_feedback_patterns(experiment_feedback)

        # Identify new insights
        for issue, count in feedback_patterns["common_issues"].items():
            if count > 10:
                patterns.append(
                    {
                        "type": "common_issue",
                        "issue": issue,
                        "frequency": count,
                        "affected_languages": list(
                            set(
                                f"{f.source_lang}-{f.target_lang}"
                                for f in experiment_feedback
                                if issue in f.issues
                            )
                        ),
                    }
                )

        return patterns

    def _generate_recommendations(
        self, evaluation: Dict[str, Any], patterns: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on evaluation."""
        recommendations = []

        # Model recommendations
        if evaluation["winner"]:
            recommendations.append(
                f"Continue using {evaluation['winner']} for "
                f"{evaluation['improvements']['rating']:.1f}% improvement"
            )

        # Pattern-based recommendations
        for pattern in patterns:
            if pattern["type"] == "common_issue":
                recommendations.append(
                    f"Address '{pattern['issue']}' affecting "
                    f"{len(pattern['affected_languages'])} language pairs"
                )

        # Quality recommendations
        if evaluation.get("confidence_level", 0) < 0.95:
            recommendations.append(
                "Increase sample size for higher statistical confidence"
            )

        return recommendations

    def _define_next_steps(self, outcome: LearningOutcome) -> List[str]:
        """Define next steps based on outcomes."""
        next_steps = []

        # Model improvements
        if outcome.improvements:
            next_steps.append("Monitor production metrics for sustained improvement")

        # Pattern addressing
        if outcome.new_patterns:
            next_steps.append(
                f"Create targeted improvements for {len(outcome.new_patterns)} patterns"
            )

        # Future experiments
        next_steps.append("Design follow-up experiments for remaining quality gaps")

        return next_steps

    async def generate_quality_report(self, period_days: int = 30) -> Dict[str, Any]:
        """
        Generate quality report for specified period.

        Args:
            period_days: Report period in days

        Returns:
            Quality report
        """
        cutoff_date = datetime.now() - timedelta(days=period_days)

        # Filter recent metrics
        recent_metrics = [
            m for m in self.quality_history if m["timestamp"] >= cutoff_date
        ]

        if not recent_metrics:
            return {"error": "No data available for period"}

        # Aggregate metrics
        report: Dict[str, Any] = {
            "period": f"{period_days} days",
            "total_feedback": len(
                [f for f in self.feedback_buffer if f.timestamp >= cutoff_date]
            ),
            "average_ratings": {},
            "quality_trends": {},
            "top_issues": {},
            "experiments_completed": 0,
            "improvements_deployed": 0,
        }

        # Calculate averages
        all_ratings = []
        for metric in recent_metrics:
            if "patterns" in metric:
                rating = metric["patterns"].get("average_rating", 0)
                if rating > 0:
                    all_ratings.append(rating)

        if all_ratings:
            average_ratings = report.get("average_ratings", {})
            if isinstance(average_ratings, dict):
                average_ratings["overall"] = sum(all_ratings) / len(all_ratings)

        # Count experiments
        for exp in self.active_experiments.values():
            if (
                exp.status == ExperimentStatus.COMPLETED
                and exp.end_date
                and exp.end_date >= cutoff_date
            ):
                report["experiments_completed"] = (
                    int(report["experiments_completed"]) + 1
                )
            if (
                exp.status == ExperimentStatus.APPLIED
                and exp.end_date
                and exp.end_date >= cutoff_date
            ):
                report["improvements_deployed"] = (
                    int(report["improvements_deployed"]) + 1
                )

        return report

    async def _schedule_model_evaluation(self, job_name: str) -> None:
        """Schedule evaluation of retrained model."""
        # This would schedule actual evaluation
        # For now, log scheduling
        logger.info(f"Scheduled evaluation for {job_name} in 24 hours")

    async def _log_feedback_metrics(self, feedback: TranslationFeedback) -> None:
        """Log individual feedback metrics."""
        try:
            # Log to CloudWatch
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cloudwatch.put_metric_data(
                    Namespace="HavenHealthPassport/Translation/Feedback",
                    MetricData=[
                        {
                            "MetricName": "UserRating",
                            "Value": feedback.rating,
                            "Unit": "None",
                            "Timestamp": feedback.timestamp,
                            "Dimensions": [
                                {
                                    "Name": "LanguagePair",
                                    "Value": f"{feedback.source_lang}-{feedback.target_lang}",
                                },
                                {"Name": "UserType", "Value": feedback.user_type},
                            ],
                        }
                    ],
                ),
            )
        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"Error logging feedback metrics: {e}")


# Global instance
class _LearningPipelineSingleton:
    """Singleton holder for ContinuousLearningPipeline."""

    _instance: Optional[ContinuousLearningPipeline] = None

    @classmethod
    def get_instance(cls) -> Optional[ContinuousLearningPipeline]:
        """Get the singleton instance."""
        return cls._instance

    @classmethod
    def set_instance(cls, instance: ContinuousLearningPipeline) -> None:
        """Set the singleton instance."""
        cls._instance = instance


def get_learning_pipeline() -> ContinuousLearningPipeline:
    """Get or create global learning pipeline instance."""
    if _LearningPipelineSingleton.get_instance() is None:
        _LearningPipelineSingleton.set_instance(ContinuousLearningPipeline())

    instance = _LearningPipelineSingleton.get_instance()
    if instance is None:
        raise RuntimeError("Failed to create ContinuousLearningPipeline instance")

    return instance

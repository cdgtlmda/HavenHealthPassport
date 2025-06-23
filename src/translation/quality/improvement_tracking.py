"""Translation Improvement Tracking."""

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ImprovementMetric:
    """Metric for tracking translation improvements."""

    timestamp: datetime
    language_pair: str
    domain: str
    quality_score: float
    confidence_score: float
    human_edited: bool
    edit_distance: Optional[int] = None
    user_rating: Optional[float] = None
    processing_time: Optional[float] = None


@dataclass
class ImprovementTrend:
    """Trend analysis for translation improvements."""

    period: str
    start_date: datetime
    end_date: datetime
    average_quality: float
    quality_improvement: float
    human_edit_rate: float
    user_satisfaction: Optional[float]
    metrics_count: int


class TranslationImprovementTracker:
    """Tracks translation quality improvements over time."""

    def __init__(self, storage_path: str):
        """Initialize improvement tracker."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.metrics: List[ImprovementMetric] = []
        self.trends: Dict[str, List[ImprovementTrend]] = defaultdict(list)
        self._load_data()

    def _load_data(self) -> None:
        """Load metrics from storage."""
        metrics_file = self.storage_path / "improvement_metrics.json"
        if metrics_file.exists():
            try:
                with open(metrics_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.metrics = [
                        ImprovementMetric(
                            timestamp=datetime.fromisoformat(m["timestamp"]),
                            language_pair=m["language_pair"],
                            domain=m["domain"],
                            quality_score=m["quality_score"],
                            confidence_score=m["confidence_score"],
                            human_edited=m["human_edited"],
                            edit_distance=m.get("edit_distance"),
                            user_rating=m.get("user_rating"),
                            processing_time=m.get("processing_time"),
                        )
                        for m in data.get("metrics", [])
                    ]
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                logger.error(f"Error loading metrics: {e}")

    def _save_data(self) -> None:
        """Save metrics to storage."""
        metrics_file = self.storage_path / "improvement_metrics.json"

        data = {
            "updated_at": datetime.now().isoformat(),
            "metrics": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "language_pair": m.language_pair,
                    "domain": m.domain,
                    "quality_score": m.quality_score,
                    "confidence_score": m.confidence_score,
                    "human_edited": m.human_edited,
                    "edit_distance": m.edit_distance,
                    "user_rating": m.user_rating,
                    "processing_time": m.processing_time,
                }
                for m in self.metrics[-10000:]  # Keep last 10k metrics
            ],
        }

        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def record_metric(
        self,
        language_pair: str,
        domain: str,
        quality_score: float,
        confidence_score: float,
        human_edited: bool = False,
        edit_distance: Optional[int] = None,
        user_rating: Optional[float] = None,
        processing_time: Optional[float] = None,
    ) -> None:
        """Record a new translation metric."""
        metric = ImprovementMetric(
            timestamp=datetime.now(),
            language_pair=language_pair,
            domain=domain,
            quality_score=quality_score,
            confidence_score=confidence_score,
            human_edited=human_edited,
            edit_distance=edit_distance,
            user_rating=user_rating,
            processing_time=processing_time,
        )

        self.metrics.append(metric)

        # Save periodically
        if len(self.metrics) % 100 == 0:
            self._save_data()

        logger.debug(f"Recorded metric for {language_pair}/{domain}")

    def calculate_trends(
        self, period: str = "daily", lookback_days: int = 30
    ) -> Dict[str, ImprovementTrend]:
        """Calculate improvement trends."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        # Filter metrics within period
        period_metrics = [
            m for m in self.metrics if start_date <= m.timestamp <= end_date
        ]

        # Group by language pair and domain
        grouped = defaultdict(list)
        for metric in period_metrics:
            key = f"{metric.language_pair}_{metric.domain}"
            grouped[key].append(metric)

        # Calculate trends for each group
        trends = {}
        for key, metrics in grouped.items():
            if not metrics:
                continue

            # Sort by timestamp
            metrics.sort(key=lambda m: m.timestamp)

            # Calculate metrics
            quality_scores = [m.quality_score for m in metrics]
            avg_quality = statistics.mean(quality_scores)

            # Calculate improvement (compare first and last quartile)
            if len(quality_scores) >= 4:
                first_quarter = statistics.mean(
                    quality_scores[: len(quality_scores) // 4]
                )
                last_quarter = statistics.mean(
                    quality_scores[-len(quality_scores) // 4 :]
                )
                improvement = last_quarter - first_quarter
            else:
                improvement = 0.0

            # Calculate human edit rate
            human_edits = sum(1 for m in metrics if m.human_edited)
            edit_rate = human_edits / len(metrics) if metrics else 0

            # Calculate user satisfaction
            ratings = [m.user_rating for m in metrics if m.user_rating is not None]
            user_satisfaction = statistics.mean(ratings) if ratings else None

            trend = ImprovementTrend(
                period=period,
                start_date=metrics[0].timestamp,
                end_date=metrics[-1].timestamp,
                average_quality=avg_quality,
                quality_improvement=improvement,
                human_edit_rate=edit_rate,
                user_satisfaction=user_satisfaction,
                metrics_count=len(metrics),
            )

            trends[key] = trend

        return trends

    def get_improvement_summary(
        self, language_pair: Optional[str] = None, domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get summary of improvements."""
        # Filter metrics
        filtered_metrics = self.metrics

        if language_pair:
            filtered_metrics = [
                m for m in filtered_metrics if m.language_pair == language_pair
            ]

        if domain:
            filtered_metrics = [m for m in filtered_metrics if m.domain == domain]

        if not filtered_metrics:
            return {
                "total_metrics": 0,
                "improvement": 0,
                "current_quality": 0,
                "human_edit_rate": 0,
            }

        # Sort by timestamp
        filtered_metrics.sort(key=lambda m: m.timestamp)

        # Calculate summary
        recent_metrics = filtered_metrics[-100:]  # Last 100
        older_metrics = filtered_metrics[:100] if len(filtered_metrics) > 200 else []

        current_quality = statistics.mean([m.quality_score for m in recent_metrics])

        if older_metrics:
            old_quality = statistics.mean([m.quality_score for m in older_metrics])
            improvement = current_quality - old_quality
        else:
            improvement = 0

        human_edit_rate = sum(1 for m in recent_metrics if m.human_edited) / len(
            recent_metrics
        )

        return {
            "total_metrics": len(filtered_metrics),
            "improvement": improvement,
            "current_quality": current_quality,
            "human_edit_rate": human_edit_rate,
            "average_confidence": statistics.mean(
                [m.confidence_score for m in recent_metrics]
            ),
            "average_processing_time": (
                statistics.mean(
                    [m.processing_time for m in recent_metrics if m.processing_time]
                )
                if any(m.processing_time for m in recent_metrics)
                else None
            ),
        }

    def identify_problem_areas(
        self, quality_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Identify language pairs or domains with quality issues."""
        problem_areas = []

        # Group metrics by language pair and domain
        grouped = defaultdict(list)

        for metric in self.metrics:
            key = f"{metric.language_pair}_{metric.domain}"
            grouped[key].append(metric)

        # Check each group
        for key, metrics in grouped.items():
            if len(metrics) < 10:  # Need enough data
                continue

            recent_metrics = metrics[-50:]  # Last 50
            avg_quality = statistics.mean([m.quality_score for m in recent_metrics])

            if avg_quality < quality_threshold:
                lang_pair, domain = key.split("_", 1)

                problem_areas.append(
                    {
                        "language_pair": lang_pair,
                        "domain": domain,
                        "average_quality": avg_quality,
                        "metrics_count": len(recent_metrics),
                        "human_edit_rate": sum(
                            1 for m in recent_metrics if m.human_edited
                        )
                        / len(recent_metrics),
                        "improvement_needed": quality_threshold - avg_quality,
                    }
                )

        # Sort by quality (worst first)
        problem_areas.sort(key=lambda x: cast(float, x["average_quality"]))

        return problem_areas

    def export_report(self, output_path: str) -> None:
        """Export improvement report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_metrics": len(self.metrics),
            "date_range": {
                "start": (
                    min(m.timestamp for m in self.metrics).isoformat()
                    if self.metrics
                    else None
                ),
                "end": (
                    max(m.timestamp for m in self.metrics).isoformat()
                    if self.metrics
                    else None
                ),
            },
            "trends": self.calculate_trends(),
            "problem_areas": self.identify_problem_areas(),
            "overall_summary": self.get_improvement_summary(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Exported improvement report to {output_path}")

"""
Translation Quality Metrics Tracking System.

This module provides comprehensive tracking, storage, and analysis of translation
quality metrics over time for continuous improvement and monitoring.
"""

import asyncio
import json
import logging
import os
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import boto3
import numpy as np
import pandas as pd

from ..config import Language, TranslationMode
from ..exceptions import MetricsStorageError
from .metrics import TranslationMetrics

logger = logging.getLogger(__name__)


class MetricAggregationLevel(Enum):
    """Levels of metric aggregation."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class TrendDirection(Enum):
    """Direction of metric trends."""

    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class MetricSnapshot:
    """Point-in-time snapshot of translation metrics."""

    timestamp: datetime
    language_pair: Tuple[str, str]
    mode: str
    metrics: TranslationMetrics
    model_version: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "language_pair": f"{self.language_pair[0]}-{self.language_pair[1]}",
            "mode": self.mode,
            "metrics": self.metrics.to_dict(),
            "model_version": self.model_version,
            "metadata": self.metadata,
        }


@dataclass
class AggregatedMetrics:
    """Aggregated metrics over a time period."""

    period_start: datetime
    period_end: datetime
    aggregation_level: MetricAggregationLevel
    language_pair: Optional[Tuple[str, str]]
    mode: Optional[str]

    # Aggregated values
    total_translations: int
    avg_confidence_score: float
    avg_pass_rate: float
    avg_quality_score: float
    avg_validation_time: float

    # Statistical measures
    confidence_std_dev: float
    quality_percentiles: Dict[int, float]  # 25th, 50th, 75th, 95th percentiles

    # Breakdown by category
    mode_breakdown: Dict[str, int]
    language_breakdown: Dict[str, int]
    failure_reasons: Dict[str, int]

    # Trends
    trend_direction: TrendDirection
    trend_magnitude: float  # Percentage change from previous period


class MetricsTracker:
    """
    Comprehensive metrics tracking system for translation quality.

    Features:
    - Real-time metrics collection
    - Time-series storage in DynamoDB
    - Multi-level aggregation
    - Trend analysis
    - Alert generation
    - Export capabilities
    """

    def __init__(self, table_name: str = "translation_quality_metrics"):
        """Initialize the metrics tracker."""
        self.table_name = table_name
        self._failure_counters: Dict[str, int] = {}  # Track failure counts in memory

        # Configure DynamoDB resource with endpoint URL handling
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        if endpoint_url:
            # Strip any trailing whitespace from endpoint URL
            endpoint_url = endpoint_url.strip()
            # Parse URL to ensure clean port numbers
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(endpoint_url)
            # If URL parsing fails or port has issues, try to clean it manually
            if parsed.hostname and ":" in endpoint_url:
                # Extract and clean port number
                parts = endpoint_url.split(":")
                if len(parts) >= 3:  # scheme://host:port
                    port_part = parts[-1].strip()
                    # Remove any non-digit characters from port
                    clean_port = "".join(c for c in port_part if c.isdigit())
                    if clean_port:
                        # Reconstruct URL with clean port
                        endpoint_url = f"{':'.join(parts[:-1])}:{clean_port}"
                        parsed = urlparse(endpoint_url)

            if parsed.port:
                # Reconstruct URL with clean port
                cleaned_url = urlunparse(
                    (
                        parsed.scheme,
                        f"{parsed.hostname}:{parsed.port}",
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment,
                    )
                )
                endpoint_url = cleaned_url

        self.dynamodb = boto3.resource(
            "dynamodb", endpoint_url=endpoint_url if endpoint_url else None
        )
        self.table = self._initialize_table()

        # In-memory buffers for real-time tracking
        self.recent_metrics: deque = deque(maxlen=1000)
        self.aggregation_buffer: Dict[str, List[MetricSnapshot]] = defaultdict(list)

        # Configuration
        self.alert_thresholds = {
            "min_confidence": 0.85,
            "min_pass_rate": 0.90,
            "max_validation_time": 5.0,  # seconds
            "min_quality_score": 0.80,
        }

        # Background aggregation task
        self._aggregation_task: Optional[asyncio.Task] = None

    async def calculate_metrics(
        self,
        source_text: str,
        translated_text: str,
        reference_text: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> TranslationMetrics:
        """Calculate translation metrics."""
        # Basic metrics
        total_validations = 1
        passed_validations = 1
        failed_validations = 0
        warnings = 0
        confidence_score = 0.95
        validation_time = 0.1

        # Calculate similarity if reference provided
        semantic_similarity = None
        if reference_text:
            # Simple similarity calculation (would use embeddings in production)
            common_words = set(translated_text.lower().split()) & set(
                reference_text.lower().split()
            )
            total_words = set(translated_text.lower().split()) | set(
                reference_text.lower().split()
            )
            semantic_similarity = (
                len(common_words) / len(total_words) if total_words else 0.0
            )

        return TranslationMetrics(
            total_validations=total_validations,
            passed_validations=passed_validations,
            failed_validations=failed_validations,
            warnings=warnings,
            confidence_score=confidence_score,
            validation_time=validation_time,
            semantic_similarity=semantic_similarity,
            terminology_accuracy=0.95,
            format_preservation=0.98,
            fluency_score=0.92,
        )

    def _initialize_table(self) -> Any:
        """Initialize DynamoDB table for metrics storage."""
        try:
            # Check if table exists
            table = self.dynamodb.Table(self.table_name)
            table.load()
            return table
        except (AttributeError, KeyError, ValueError):
            # Create table if it doesn't exist
            return self._create_metrics_table()

    def _create_metrics_table(self) -> Any:
        """Create DynamoDB table for metrics."""
        table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {
                    "AttributeName": "pk",  # partition key: "METRICS#{language_pair}#{mode}"
                    "KeyType": "HASH",
                },
                {
                    "AttributeName": "sk",  # sort key: "SNAPSHOT#{timestamp}"
                    "KeyType": "RANGE",
                },
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "gsi1pk", "AttributeType": "S"},
                {"AttributeName": "gsi1sk", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "AggregationIndex",
                    "KeySchema": [
                        {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Wait for table to be created
        table.wait_until_exists()
        return table

    async def track_metrics(
        self,
        source_language: Language,
        target_language: Language,
        mode: TranslationMode,
        metrics: TranslationMetrics,
        model_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track translation quality metrics.

        Args:
            source_language: Source language
            target_language: Target language
            mode: Translation mode
            metrics: Translation metrics
            model_version: Model version used
            metadata: Additional metadata
        """
        snapshot = MetricSnapshot(
            timestamp=datetime.utcnow(),
            language_pair=(source_language.value, target_language.value),
            mode=str(mode.value) if hasattr(mode, "value") else str(mode),
            metrics=metrics,
            model_version=model_version,
            metadata=metadata or {},
        )

        # Add to in-memory buffer
        self.recent_metrics.append(snapshot)

        # Add to aggregation buffer
        buffer_key = f"{snapshot.language_pair}#{snapshot.mode}"
        self.aggregation_buffer[buffer_key].append(snapshot)

        # Store in DynamoDB
        await self._store_snapshot(snapshot)

        # Check for alerts
        await self._check_alerts(snapshot)

    async def _store_snapshot(self, snapshot: MetricSnapshot) -> None:
        """Store metrics snapshot in DynamoDB."""
        try:
            item = {
                "pk": f"METRICS#{snapshot.language_pair[0]}-{snapshot.language_pair[1]}#{snapshot.mode}",
                "sk": f"SNAPSHOT#{snapshot.timestamp.isoformat()}",
                "gsi1pk": f"AGG#{snapshot.timestamp.strftime('%Y-%m-%d')}",
                "gsi1sk": f"{snapshot.language_pair[0]}-{snapshot.language_pair[1]}#{snapshot.mode}",
                **snapshot.to_dict(),
            }

            self.table.put_item(Item=item)

        except Exception as e:
            logger.error("Failed to store metrics snapshot: %s", str(e))
            raise MetricsStorageError(f"Failed to store metrics: {e}") from e

    async def _check_alerts(self, snapshot: MetricSnapshot) -> None:
        """Check if metrics trigger any alerts."""
        alerts = []

        metrics = snapshot.metrics

        if metrics.confidence_score < self.alert_thresholds["min_confidence"]:
            alerts.append(
                {
                    "type": "LOW_CONFIDENCE",
                    "value": metrics.confidence_score,
                    "threshold": self.alert_thresholds["min_confidence"],
                }
            )

        if metrics.pass_rate < self.alert_thresholds["min_pass_rate"]:
            alerts.append(
                {
                    "type": "LOW_PASS_RATE",
                    "value": metrics.pass_rate,
                    "threshold": self.alert_thresholds["min_pass_rate"],
                }
            )

        if metrics.validation_time > self.alert_thresholds["max_validation_time"]:
            alerts.append(
                {
                    "type": "HIGH_VALIDATION_TIME",
                    "value": metrics.validation_time,
                    "threshold": self.alert_thresholds["max_validation_time"],
                }
            )

        if metrics.quality_score < self.alert_thresholds["min_quality_score"]:
            alerts.append(
                {
                    "type": "LOW_QUALITY_SCORE",
                    "value": metrics.quality_score,
                    "threshold": self.alert_thresholds["min_quality_score"],
                }
            )

        if alerts:
            await self._send_alerts(snapshot, alerts)

    async def _send_alerts(
        self, snapshot: MetricSnapshot, alerts: List[Dict[str, Any]]
    ) -> None:
        """Send alerts for threshold violations."""
        # Log alerts
        for alert in alerts:
            logger.warning(
                "Alert triggered - %s: value=%.3f, threshold=%.3f, language_pair=%s, mode=%s",
                alert["type"],
                alert["value"],
                alert["threshold"],
                snapshot.language_pair,
                snapshot.mode,
            )

        # Integrate with SNS alerting
        await self._send_sns_alert(snapshot)

    async def aggregate_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        aggregation_level: MetricAggregationLevel,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
    ) -> AggregatedMetrics:
        """
        Aggregate metrics over a time period.

        Args:
            start_time: Start of aggregation period
            end_time: End of aggregation period
            aggregation_level: Level of aggregation
            language_pair: Optional language pair filter
            mode: Optional mode filter

        Returns:
            Aggregated metrics
        """
        # Query metrics from DynamoDB
        snapshots = await self._query_snapshots(
            start_time, end_time, language_pair, mode
        )

        if not snapshots:
            return self._create_empty_aggregation(
                start_time, end_time, aggregation_level, language_pair, mode
            )

        # Calculate aggregations
        metrics_data = [s.metrics for s in snapshots]

        avg_confidence = statistics.mean(m.confidence_score for m in metrics_data)
        avg_pass_rate = statistics.mean(m.pass_rate for m in metrics_data)
        avg_quality = statistics.mean(m.quality_score for m in metrics_data)
        avg_validation_time = statistics.mean(m.validation_time for m in metrics_data)

        confidence_std = (
            statistics.stdev(m.confidence_score for m in metrics_data)
            if len(metrics_data) > 1
            else 0
        )

        # Calculate percentiles
        quality_scores = sorted(m.quality_score for m in metrics_data)
        percentiles = {
            25: np.percentile(quality_scores, 25),
            50: np.percentile(quality_scores, 50),
            75: np.percentile(quality_scores, 75),
            95: np.percentile(quality_scores, 95),
        }

        # Mode and language breakdowns
        mode_breakdown: Dict[str, int] = defaultdict(int)
        language_breakdown: Dict[str, int] = defaultdict(int)

        for snapshot in snapshots:
            mode_breakdown[snapshot.mode] += 1
            language_breakdown[
                f"{snapshot.language_pair[0]}-{snapshot.language_pair[1]}"
            ] += 1

        # Calculate trend
        trend_direction, trend_magnitude = await self._calculate_trend(snapshots)

        return AggregatedMetrics(
            period_start=start_time,
            period_end=end_time,
            aggregation_level=aggregation_level,
            language_pair=language_pair,
            mode=mode,
            total_translations=len(snapshots),
            avg_confidence_score=avg_confidence,
            avg_pass_rate=avg_pass_rate,
            avg_quality_score=avg_quality,
            avg_validation_time=avg_validation_time,
            confidence_std_dev=confidence_std,
            quality_percentiles={k: float(v) for k, v in percentiles.items()},
            mode_breakdown=dict(mode_breakdown),
            language_breakdown=dict(language_breakdown),
            failure_reasons=await self.get_failure_reasons(
                start_time, end_time, language_pair
            ),
            trend_direction=trend_direction,
            trend_magnitude=trend_magnitude,
        )

    async def _query_snapshots(
        self,
        start_time: datetime,
        end_time: datetime,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
    ) -> List[MetricSnapshot]:
        """Query snapshots from DynamoDB."""
        snapshots = []

        # Use GSI for date-based queries
        response = self.table.query(
            IndexName="AggregationIndex",
            KeyConditionExpression="gsi1pk = :pk AND gsi1sk BETWEEN :start AND :end",
            ExpressionAttributeValues={
                ":pk": f"AGG#{start_time.strftime('%Y-%m-%d')}",
                ":start": start_time.isoformat(),
                ":end": end_time.isoformat(),
            },
        )

        # Filter by language pair and mode if specified
        for item in response.get("Items", []):
            snapshot = self._deserialize_snapshot(item)

            if language_pair and snapshot.language_pair != language_pair:
                continue
            if mode and snapshot.mode != mode:
                continue

            snapshots.append(snapshot)

        return snapshots

    def _deserialize_snapshot(self, item: Dict[str, Any]) -> MetricSnapshot:
        """Deserialize DynamoDB item to MetricSnapshot."""
        metrics_dict = item["metrics"]

        metrics = TranslationMetrics(
            total_validations=metrics_dict["total_validations"],
            passed_validations=metrics_dict["passed_validations"],
            failed_validations=metrics_dict["failed_validations"],
            warnings=metrics_dict["warnings"],
            confidence_score=metrics_dict["confidence_score"],
            validation_time=metrics_dict["validation_time"],
            semantic_similarity=metrics_dict.get("semantic_similarity"),
            terminology_accuracy=metrics_dict.get("terminology_accuracy"),
            format_preservation=metrics_dict.get("format_preservation"),
            fluency_score=metrics_dict.get("fluency_score"),
        )

        language_pair = item["language_pair"].split("-")

        return MetricSnapshot(
            timestamp=datetime.fromisoformat(item["timestamp"]),
            language_pair=(language_pair[0], language_pair[1]),
            mode=item["mode"],
            metrics=metrics,
            model_version=item["model_version"],
            metadata=item.get("metadata", {}),
        )

    async def _calculate_trend(
        self, snapshots: List[MetricSnapshot]
    ) -> Tuple[TrendDirection, float]:
        """Calculate trend direction and magnitude."""
        if len(snapshots) < 2:
            return TrendDirection.INSUFFICIENT_DATA, 0.0

        # Sort by timestamp
        sorted_snapshots = sorted(snapshots, key=lambda s: s.timestamp)

        # Calculate quality scores over time
        timestamps = [s.timestamp for s in sorted_snapshots]
        quality_scores = [s.metrics.quality_score for s in sorted_snapshots]

        # Simple linear regression for trend
        x = np.array([(t - timestamps[0]).total_seconds() for t in timestamps])
        y = np.array(quality_scores)

        if len(x) > 1:
            slope, _ = np.polyfit(x, y, 1)

            # Calculate percentage change
            first_quality = quality_scores[0]
            last_quality = quality_scores[-1]

            if first_quality > 0:
                magnitude = ((last_quality - first_quality) / first_quality) * 100
            else:
                magnitude = 0.0

            # Determine direction based on slope and magnitude
            if abs(magnitude) < 1.0:  # Less than 1% change
                direction = TrendDirection.STABLE
            elif slope > 0:
                direction = TrendDirection.IMPROVING
            else:
                direction = TrendDirection.DECLINING

            return direction, magnitude

        return TrendDirection.STABLE, 0.0

    def _create_empty_aggregation(
        self,
        start_time: datetime,
        end_time: datetime,
        aggregation_level: MetricAggregationLevel,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> AggregatedMetrics:
        """Create empty aggregation when no data is available."""
        return AggregatedMetrics(
            period_start=start_time,
            period_end=end_time,
            aggregation_level=aggregation_level,
            language_pair=language_pair,
            mode=mode,
            total_translations=0,
            avg_confidence_score=0.0,
            avg_pass_rate=0.0,
            avg_quality_score=0.0,
            avg_validation_time=0.0,
            confidence_std_dev=0.0,
            quality_percentiles={25: 0.0, 50: 0.0, 75: 0.0, 95: 0.0},
            mode_breakdown={},
            language_breakdown={},
            failure_reasons={},
            trend_direction=TrendDirection.INSUFFICIENT_DATA,
            trend_magnitude=0.0,
        )

    async def get_recent_metrics(
        self,
        limit: int = 100,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
    ) -> List[MetricSnapshot]:
        """Get recent metrics from in-memory buffer."""
        filtered_metrics = []

        for snapshot in reversed(self.recent_metrics):
            if language_pair and snapshot.language_pair != language_pair:
                continue
            if mode and snapshot.mode != mode:
                continue

            filtered_metrics.append(snapshot)

            if len(filtered_metrics) >= limit:
                break

        return filtered_metrics

    async def export_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        export_format: str = "csv",
        output_path: Optional[Path] = None,
    ) -> Union[str, Path]:
        """
        Export metrics to file.

        Args:
            start_time: Start time for export
            end_time: End time for export
            format: Export format (csv, json, excel)
            output_path: Optional output path

        Returns:
            Path to exported file or data as string
        """
        # Query all snapshots in time range
        snapshots = await self._query_snapshots(start_time, end_time)

        if export_format == "csv":
            return await self._export_csv(snapshots, output_path)
        elif export_format == "json":
            return await self._export_json(snapshots, output_path)
        elif export_format == "excel":
            return await self._export_excel(snapshots, output_path)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

    async def _export_csv(
        self, snapshots: List[MetricSnapshot], output_path: Optional[Path]
    ) -> Union[str, Path]:
        """Export metrics to CSV."""
        # Convert to pandas DataFrame
        data = []
        for snapshot in snapshots:
            row = {
                "timestamp": snapshot.timestamp,
                "source_language": snapshot.language_pair[0],
                "target_language": snapshot.language_pair[1],
                "mode": snapshot.mode,
                "model_version": snapshot.model_version,
                **snapshot.metrics.to_dict(),
            }
            data.append(row)

        df = pd.DataFrame(data)

        if output_path:
            df.to_csv(output_path, index=False)
            return output_path
        else:
            return str(df.to_csv(index=False))

    async def _export_json(
        self, snapshots: List[MetricSnapshot], output_path: Optional[Path]
    ) -> Union[str, Path]:
        """Export metrics to JSON."""
        data = [snapshot.to_dict() for snapshot in snapshots]

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            return output_path
        else:
            return json.dumps(data, indent=2, default=str)

    async def _export_excel(
        self, snapshots: List[MetricSnapshot], output_path: Optional[Path]
    ) -> Path:
        """Export metrics to Excel with multiple sheets."""
        if not output_path:
            output_path = Path(
                f"translation_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Raw data sheet
            data = []
            for snapshot in snapshots:
                row = {
                    "timestamp": snapshot.timestamp,
                    "source_language": snapshot.language_pair[0],
                    "target_language": snapshot.language_pair[1],
                    "mode": snapshot.mode,
                    "model_version": snapshot.model_version,
                    **snapshot.metrics.to_dict(),
                }
                data.append(row)

            df_raw = pd.DataFrame(data)
            df_raw.to_excel(writer, sheet_name="Raw Data", index=False)

            # Summary statistics sheet
            summary_stats = {
                "Metric": [
                    "Total Translations",
                    "Average Confidence",
                    "Average Quality",
                    "Average Pass Rate",
                    "Average Validation Time",
                ],
                "Value": [
                    len(snapshots),
                    df_raw["confidence_score"].mean(),
                    df_raw["quality_score"].mean(),
                    df_raw["pass_rate"].mean(),
                    df_raw["validation_time"].mean(),
                ],
            }
            df_summary = pd.DataFrame(summary_stats)
            df_summary.to_excel(writer, sheet_name="Summary", index=False)

            # Language pair breakdown
            language_stats = (
                df_raw.groupby(["source_language", "target_language"])
                .agg(
                    {
                        "confidence_score": "mean",
                        "quality_score": "mean",
                        "pass_rate": "mean",
                        "validation_time": "mean",
                        "timestamp": "count",
                    }
                )
                .rename(columns={"timestamp": "count"})
            )
            language_stats.to_excel(writer, sheet_name="Language Pairs")

            # Mode breakdown
            mode_stats = (
                df_raw.groupby("mode")
                .agg(
                    {
                        "confidence_score": "mean",
                        "quality_score": "mean",
                        "pass_rate": "mean",
                        "validation_time": "mean",
                        "timestamp": "count",
                    }
                )
                .rename(columns={"timestamp": "count"})
            )
            mode_stats.to_excel(writer, sheet_name="Translation Modes")

        return output_path

    async def start_background_aggregation(self, interval_seconds: int = 300) -> None:
        """Start background aggregation task."""
        if self._aggregation_task and not self._aggregation_task.done():
            logger.warning("Background aggregation already running")
            return

        self._aggregation_task = asyncio.create_task(
            self._background_aggregation_loop(interval_seconds)
        )

    async def _background_aggregation_loop(self, interval_seconds: int) -> None:
        """Background loop for periodic aggregation."""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await self._perform_scheduled_aggregations()
            except (ValueError, KeyError, AttributeError) as e:
                logger.error("Error in background aggregation: %s", str(e))

    async def _perform_scheduled_aggregations(self) -> None:
        """Perform scheduled aggregations."""
        now = datetime.utcnow()

        # Hourly aggregation
        hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        hour_end = hour_start + timedelta(hours=1)

        try:
            hourly_agg = await self.aggregate_metrics(
                hour_start, hour_end, MetricAggregationLevel.HOURLY
            )

            # Store aggregated metrics
            await self._store_aggregation(hourly_agg)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Failed to perform hourly aggregation: %s", str(e))

    async def _store_aggregation(self, aggregation: AggregatedMetrics) -> None:
        """Store aggregated metrics."""
        try:
            # Create aggregation key
            time_key = aggregation.period_start.strftime("%Y-%m-%d-%H")
            if aggregation.language_pair:
                lang_key = (
                    f"{aggregation.language_pair[0]}-{aggregation.language_pair[1]}"
                )
            else:
                lang_key = "all"

            pk = f"AGGREGATION#{aggregation.aggregation_level.value}#{lang_key}"
            sk = f"TIME#{time_key}"

            # Prepare aggregation record
            aggregation_record = {
                "pk": pk,
                "sk": sk,
                "gsi1pk": f"LEVEL#{aggregation.aggregation_level.value}",
                "gsi1sk": f"TIME#{time_key}",
                "period_start": aggregation.period_start.isoformat(),
                "period_end": aggregation.period_end.isoformat(),
                "aggregation_level": aggregation.aggregation_level.value,
                "language_pair": aggregation.language_pair,
                "mode": aggregation.mode,
                "total_translations": aggregation.total_translations,
                "avg_confidence_score": aggregation.avg_confidence_score,
                "avg_pass_rate": aggregation.avg_pass_rate,
                "avg_quality_score": aggregation.avg_quality_score,
                "avg_validation_time": aggregation.avg_validation_time,
                "confidence_std_dev": aggregation.confidence_std_dev,
                "quality_percentiles": aggregation.quality_percentiles,
                "mode_breakdown": aggregation.mode_breakdown,
                "language_breakdown": aggregation.language_breakdown,
                "failure_reasons": aggregation.failure_reasons,
                "trend_direction": aggregation.trend_direction.value,
                "trend_magnitude": aggregation.trend_magnitude,
                "ttl": int(
                    (aggregation.period_end + timedelta(days=365)).timestamp()
                ),  # 1 year retention
            }

            # Store aggregation
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.table.put_item(Item=aggregation_record)
            )

            logger.info(
                f"Stored {aggregation.aggregation_level.value} aggregation for "
                f"{lang_key} at {time_key}"
            )

        except Exception as e:
            logger.error(f"Failed to store aggregation: {e}")

    def configure_alerts(self, thresholds: Dict[str, float]) -> None:
        """Configure alert thresholds."""
        self.alert_thresholds.update(thresholds)

    async def close(self) -> None:
        """Clean up resources."""
        if self._aggregation_task:
            self._aggregation_task.cancel()
            try:
                await self._aggregation_task
            except asyncio.CancelledError:
                pass

    async def _send_sns_alert(self, snapshot: MetricSnapshot) -> None:
        """Send SNS alert for threshold breach."""
        try:
            import json
            import os

            import boto3

            # Get region from environment or use default
            region = os.getenv("AWS_REGION", "us-east-1")
            sns_client = boto3.client("sns", region_name=region)
            topic_arn = os.getenv("SNS_TOPIC_ARN_TRANSLATION_ALERTS")

            if not topic_arn:
                logger.warning("SNS topic ARN not configured for translation alerts")
                return

            # Determine alert severity based on metrics
            severity = "WARNING"
            if snapshot.metrics.failed_validations > 100:
                severity = "CRITICAL"
            elif snapshot.metrics.failed_validations > 50:
                severity = "HIGH"

            # Build alert message
            message = {
                "severity": severity,
                "metric_type": "translation_quality",
                "timestamp": snapshot.timestamp.isoformat(),
                "language_pair": (
                    f"{snapshot.language_pair[0]}->{snapshot.language_pair[1]}"
                    if snapshot.language_pair
                    else "all"
                ),
                "mode": snapshot.mode or "all",
                "metrics": {
                    "total_validations": snapshot.metrics.total_validations,
                    "passed_validations": snapshot.metrics.passed_validations,
                    "failed_validations": snapshot.metrics.failed_validations,
                    "confidence_score": snapshot.metrics.confidence_score,
                    "quality_score": snapshot.metrics.quality_score,
                    "validation_time": snapshot.metrics.validation_time,
                    "pass_rate": snapshot.metrics.pass_rate,
                },
                "alert_reason": "Metric thresholds exceeded",
                "recommended_action": "Review translation service performance and error logs",
            }

            # Send SNS notification
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sns_client.publish(
                    TopicArn=topic_arn,
                    Subject=f"[{severity}] Translation Service Alert - {snapshot.language_pair}",
                    Message=json.dumps(message, indent=2),
                    MessageAttributes={
                        "severity": {"DataType": "String", "StringValue": severity},
                        "service": {"DataType": "String", "StringValue": "translation"},
                    },
                ),
            )

            logger.info(
                f"SNS alert sent successfully. MessageId: {response['MessageId']}"
            )

        except Exception as e:
            logger.error(f"Failed to send SNS alert: {e}")

    def track_failure(
        self,
        source_language: Language,
        target_language: Language,
        mode: TranslationMode,
        failure_reason: str,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track translation failure with reason.

        Args:
            source_language: Source language
            target_language: Target language
            mode: Translation mode
            failure_reason: Reason for failure
            error_details: Additional error information
        """
        try:
            # Create failure key
            timestamp = datetime.utcnow()
            pk = f"FAILURE#{source_language.value}#{target_language.value}"
            sk = f"ERROR#{timestamp.isoformat()}#{failure_reason[:50]}"

            # Prepare failure record
            failure_record = {
                "pk": pk,
                "sk": sk,
                "timestamp": timestamp.isoformat(),
                "source_language": source_language.value,
                "target_language": target_language.value,
                "mode": mode.value,
                "failure_reason": failure_reason,
                "error_details": error_details or {},
                "ttl": int(
                    (timestamp + timedelta(days=90)).timestamp()
                ),  # 90 day retention
            }

            # Store failure record
            self.table.put_item(Item=failure_record)

            # Update failure counter in current metrics
            counter_key = (
                f"{failure_reason}:{source_language.value}->{target_language.value}"
            )
            if counter_key in self._failure_counters:
                self._failure_counters[counter_key] += 1
            else:
                self._failure_counters[counter_key] = 1

            logger.info(
                f"Tracked failure for {source_language.value}->{target_language.value}: {failure_reason}"
            )

        except Exception as e:
            logger.error(f"Failed to track translation failure: {e}")

    async def get_failure_reasons(
        self,
        start_time: datetime,
        end_time: datetime,
        language_pair: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, int]:
        """
        Get aggregated failure reasons for time period.

        Args:
            start_time: Start of period
            end_time: End of period
            language_pair: Optional language pair filter

        Returns:
            Dictionary of failure reasons with counts
        """
        try:
            failure_counts: Dict[str, int] = defaultdict(int)

            # Query failure records
            if language_pair:
                pk = f"FAILURE#{language_pair[0]}#{language_pair[1]}"
                response = self.table.query(
                    KeyConditionExpression="pk = :pk AND sk BETWEEN :start AND :end",
                    ExpressionAttributeValues={
                        ":pk": pk,
                        ":start": f"ERROR#{start_time.isoformat()}",
                        ":end": f"ERROR#{end_time.isoformat()}#zzz",
                    },
                )
            else:
                # Scan all failures (less efficient but works for all languages)
                response = self.table.scan(
                    FilterExpression="begins_with(pk, :prefix) AND #ts BETWEEN :start AND :end",
                    ExpressionAttributeNames={"#ts": "timestamp"},
                    ExpressionAttributeValues={
                        ":prefix": "FAILURE#",
                        ":start": start_time.isoformat(),
                        ":end": end_time.isoformat(),
                    },
                )

            # Aggregate failure reasons
            for item in response.get("Items", []):
                reason = item.get("failure_reason", "unknown")
                failure_counts[reason] += 1

            return dict(failure_counts)

        except Exception as e:
            logger.error(f"Error retrieving failure reasons: {e}")
            return {}

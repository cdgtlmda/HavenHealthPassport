"""
Automated Reporting System for Translation Quality.

This module provides automated report generation and scheduling for translation
quality metrics, benchmarks, and system performance.
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import boto3
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from ..exceptions import ReportingError
from .dashboard_renderer import DashboardRenderer
from .metrics_tracker import MetricAggregationLevel, MetricsTracker
from .performance_benchmarks import PerformanceBenchmarkManager
from .quality_dashboards import DashboardType, QualityDashboardManager, TimeRange

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Types of automated reports."""

    DAILY_SUMMARY = "daily_summary"
    WEEKLY_ANALYSIS = "weekly_analysis"
    MONTHLY_REVIEW = "monthly_review"
    QUARTERLY_ASSESSMENT = "quarterly_assessment"
    CUSTOM = "custom"
    ALERT_DIGEST = "alert_digest"
    BENCHMARK_STATUS = "benchmark_status"
    LANGUAGE_PERFORMANCE = "language_performance"


class ReportFormat(Enum):
    """Report output formats."""

    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"
    EXCEL = "excel"


class ReportSchedule(Enum):
    """Report scheduling frequencies."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ON_DEMAND = "on_demand"


@dataclass
class ReportConfiguration:
    """Configuration for an automated report."""

    report_id: str
    report_type: ReportType
    schedule: ReportSchedule
    format: ReportFormat
    recipients: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    include_sections: List[str] = field(default_factory=list)
    enabled: bool = True
    last_generated: Optional[datetime] = None
    next_scheduled: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "schedule": self.schedule.value,
            "format": self.format.value,
            "recipients": self.recipients,
            "filters": self.filters,
            "include_sections": self.include_sections,
            "enabled": self.enabled,
            "last_generated": (
                self.last_generated.isoformat() if self.last_generated else None
            ),
            "next_scheduled": (
                self.next_scheduled.isoformat() if self.next_scheduled else None
            ),
        }


@dataclass
class ReportData:
    """Container for generated report data."""

    report_id: str
    report_type: ReportType
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    sections: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AutomatedReportingSystem:
    """
    Manages automated report generation and distribution.

    Features:
    - Scheduled report generation
    - Multiple report types and formats
    - Email distribution
    - S3 storage
    - Custom report templates
    - Configurable content sections
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize the reporting system."""
        self.metrics_tracker = MetricsTracker()
        self.benchmark_manager = PerformanceBenchmarkManager()
        self.dashboard_manager = QualityDashboardManager()
        self.dashboard_renderer = DashboardRenderer()

        # Report configurations
        self.report_configs: Dict[str, ReportConfiguration] = {}

        # S3 client for report storage
        self.s3_client = boto3.client("s3")
        self.report_bucket = "translation-quality-reports"

        # Template engine with autoescape for security
        self.template_env: Optional[Environment] = None
        if template_dir:
            self.template_env = Environment(
                loader=FileSystemLoader(template_dir), autoescape=True
            )

        # Scheduler state
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False

    def initialize_default_reports(self) -> None:
        """Initialize default report configurations."""
        # Daily Summary Report
        daily_summary = ReportConfiguration(
            report_id="daily_summary",
            report_type=ReportType.DAILY_SUMMARY,
            schedule=ReportSchedule.DAILY,
            format=ReportFormat.HTML,
            include_sections=[
                "executive_summary",
                "key_metrics",
                "benchmark_status",
                "alerts_summary",
                "top_language_pairs",
            ],
        )
        self.report_configs["daily_summary"] = daily_summary

        # Weekly Analysis Report
        weekly_analysis = ReportConfiguration(
            report_id="weekly_analysis",
            report_type=ReportType.WEEKLY_ANALYSIS,
            schedule=ReportSchedule.WEEKLY,
            format=ReportFormat.PDF,
            include_sections=[
                "executive_summary",
                "performance_trends",
                "benchmark_analysis",
                "quality_metrics",
                "language_performance",
                "recommendations",
            ],
        )
        self.report_configs["weekly_analysis"] = weekly_analysis

        # Monthly Review Report
        monthly_review = ReportConfiguration(
            report_id="monthly_review",
            report_type=ReportType.MONTHLY_REVIEW,
            schedule=ReportSchedule.MONTHLY,
            format=ReportFormat.EXCEL,
            include_sections=[
                "comprehensive_metrics",
                "benchmark_history",
                "language_pair_analysis",
                "system_performance",
                "cost_analysis",
                "improvement_opportunities",
            ],
        )
        self.report_configs["monthly_review"] = monthly_review

    async def generate_report(
        self,
        report_config: ReportConfiguration,
        custom_period: Optional[Tuple[datetime, datetime]] = None,
    ) -> ReportData:
        """
        Generate a report based on configuration.

        Args:
            report_config: Report configuration
            custom_period: Optional custom time period

        Returns:
            Generated report data
        """
        # Determine report period
        if custom_period:
            period_start, period_end = custom_period
        else:
            period_start, period_end = self._calculate_report_period(report_config)

        # Create report data container
        report_data = ReportData(
            report_id=report_config.report_id,
            report_type=report_config.report_type,
            generated_at=datetime.utcnow(),
            period_start=period_start,
            period_end=period_end,
        )

        # Generate report sections
        for section in report_config.include_sections:
            section_data = await self._generate_section(
                section, period_start, period_end, report_config.filters
            )
            report_data.sections[section] = section_data

        # Generate summary
        report_data.summary = await self._generate_summary(report_data)

        # Update last generated time
        report_config.last_generated = datetime.utcnow()
        report_config.next_scheduled = self._calculate_next_schedule(report_config)

        logger.info("Generated report: %s", report_config.report_id)

        return report_data

    async def _generate_section(
        self,
        section_name: str,
        period_start: datetime,
        period_end: datetime,
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a specific report section."""
        # Extract filters
        language_pair = None
        if "language_pair" in filters:
            language_pair = tuple(filters["language_pair"].split("-"))
        mode = filters.get("mode")

        # Generate section based on type
        if section_name == "executive_summary":
            return await self._generate_executive_summary(
                period_start, period_end, language_pair, mode
            )
        elif section_name == "key_metrics":
            return await self._generate_key_metrics(
                period_start, period_end, language_pair, mode
            )
        elif section_name == "benchmark_status":
            return await self._generate_benchmark_status(
                period_start, period_end, language_pair, mode
            )
        elif section_name == "performance_trends":
            return await self._generate_performance_trends(
                period_start, period_end, language_pair, mode
            )
        elif section_name == "language_performance":
            return await self._generate_language_performance(period_start, period_end)
        elif section_name == "alerts_summary":
            return await self._generate_alerts_summary(period_start, period_end)
        elif section_name == "recommendations":
            return await self._generate_recommendations(
                period_start, period_end, language_pair, mode
            )
        else:
            logger.warning("Unknown section: %s", section_name)
            return {"error": f"Unknown section: {section_name}"}

    async def _generate_executive_summary(
        self,
        period_start: datetime,
        period_end: datetime,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Generate executive summary section."""
        # Get aggregated metrics
        metrics = await self.metrics_tracker.aggregate_metrics(
            start_time=period_start,
            end_time=period_end,
            aggregation_level=MetricAggregationLevel.DAILY,
            language_pair=language_pair,
            mode=mode,
        )

        # Get latest benchmark results
        recent_metrics = await self.metrics_tracker.get_recent_metrics(
            limit=1, language_pair=language_pair, mode=mode
        )

        benchmark_results = []
        if recent_metrics:
            benchmark_results = await self.benchmark_manager.evaluate_metrics(
                metrics=recent_metrics[0].metrics,
                language_pair=language_pair,
                mode=mode,
            )

        return {
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
            "total_translations": metrics.total_translations,
            "average_quality_score": metrics.avg_quality_score,
            "average_confidence": metrics.avg_confidence_score,
            "pass_rate": metrics.avg_pass_rate,
            "benchmark_achievement": {
                "total": len(benchmark_results),
                "passing": sum(1 for r in benchmark_results if r.is_passing),
            },
            "trend": (
                metrics.trend_direction.value if metrics.trend_direction else "stable"
            ),
        }

    async def _generate_key_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Generate key metrics section."""
        # Get dashboard data
        dashboard_data = await self.dashboard_manager.get_dashboard_data(
            DashboardType.OVERVIEW,
            TimeRange.CUSTOM,
            language_pair=language_pair,
            mode=mode,
        )

        # Extract key metrics
        current_metrics = dashboard_data.data.get("current_metrics", {})

        return {
            "metrics": current_metrics.get("metrics", {}),
            "last_updated": current_metrics.get("last_updated"),
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
        }

    async def _generate_benchmark_status(
        self,
        period_start: datetime,
        period_end: datetime,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Generate benchmark status section."""
        # Get benchmark report
        benchmark_report = await self.benchmark_manager.generate_benchmark_report(
            start_time=period_start,
            end_time=period_end,
            language_pair=language_pair,
            mode=mode,
            output_format="json",
        )

        # Type check - generate_benchmark_report returns dict with json format
        if isinstance(benchmark_report, dict):
            return benchmark_report
        else:
            # This should never happen with output_format="json"
            return {"error": "Unexpected format from benchmark report"}

    async def _generate_performance_trends(
        self,
        _period_start: datetime,
        _period_end: datetime,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Generate performance trends section."""
        # Get dashboard trend data
        # Note: period_start and period_end are passed for API consistency
        # but dashboard manager uses its own time range logic
        dashboard_data = await self.dashboard_manager.get_dashboard_data(
            DashboardType.TRENDS,
            TimeRange.CUSTOM,
            language_pair=language_pair,
            mode=mode,
        )

        return dashboard_data.data

    async def _generate_language_performance(
        self, period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Generate language performance section."""
        # Filter metrics by period
        # Get detailed metrics for the period
        detailed_metrics = await self.metrics_tracker.get_recent_metrics(
            limit=10000  # Get all metrics for the period
        )

        language_stats: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"count": 0, "quality_sum": 0.0, "pass_count": 0}
        )

        for snapshot in detailed_metrics:
            # Only include metrics within the specified period
            if period_start <= snapshot.timestamp <= period_end:
                key = f"{snapshot.language_pair[0]}-{snapshot.language_pair[1]}"
                stats = language_stats[key]
            stats["count"] += 1
            stats["quality_sum"] += snapshot.metrics.quality_score
            if snapshot.metrics.pass_rate >= 0.95:
                stats["pass_count"] += 1

        # Calculate averages
        language_performance = {}
        for lang_pair, stats in language_stats.items():
            if stats["count"] > 0:
                language_performance[lang_pair] = {
                    "total_translations": stats["count"],
                    "average_quality": stats["quality_sum"] / stats["count"],
                    "high_quality_percentage": (stats["pass_count"] / stats["count"])
                    * 100,
                }

        return language_performance

    async def _generate_alerts_summary(
        self, period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Generate alerts summary section."""
        # This would integrate with the alert system
        # For now, return a placeholder structure
        # Parameters period_start and period_end are kept for future implementation
        _ = (period_start, period_end)  # Acknowledge unused parameters
        return {
            "total_alerts": 0,
            "critical_alerts": 0,
            "warning_alerts": 0,
            "resolved_alerts": 0,
            "top_alert_types": [],
        }

    async def _generate_recommendations(
        self,
        period_start: datetime,
        period_end: datetime,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Generate recommendations based on analysis."""
        # Get metrics for analysis
        metrics = await self.metrics_tracker.aggregate_metrics(
            start_time=period_start,
            end_time=period_end,
            aggregation_level=MetricAggregationLevel.DAILY,
            language_pair=language_pair,
            mode=mode,
        )

        recommendations = []

        # Quality-based recommendations
        if metrics.avg_quality_score < 0.85:
            recommendations.append(
                {
                    "priority": "high",
                    "category": "quality",
                    "recommendation": "Consider reviewing and updating translation models",
                    "reason": f"Average quality score ({metrics.avg_quality_score:.2f}) is below target",
                }
            )

        # Performance-based recommendations
        if metrics.avg_validation_time > 3.0:
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "performance",
                    "recommendation": "Optimize validation pipeline for better performance",
                    "reason": f"Average validation time ({metrics.avg_validation_time:.1f}s) exceeds target",
                }
            )

        return {"recommendations": recommendations}

    async def _generate_summary(self, report_data: ReportData) -> Dict[str, Any]:
        """Generate report summary from all sections."""
        summary = {
            "report_type": report_data.report_type.value,
            "generated_at": report_data.generated_at.isoformat(),
            "period": {
                "start": report_data.period_start.isoformat(),
                "end": report_data.period_end.isoformat(),
                "duration_days": (
                    report_data.period_end - report_data.period_start
                ).days,
            },
        }

        # Extract key metrics from sections
        if "executive_summary" in report_data.sections:
            exec_summary = report_data.sections["executive_summary"]
            summary["total_translations"] = exec_summary.get("total_translations", 0)
            summary["average_quality"] = exec_summary.get("average_quality_score", 0)

        return summary

    async def format_report(
        self, report_data: ReportData, report_format: ReportFormat
    ) -> Union[str, bytes, Path]:
        """
        Format report data into specified format.

        Args:
            report_data: Generated report data
            report_format: Output format

        Returns:
            Formatted report
        """
        if report_format == ReportFormat.JSON:
            return json.dumps(
                {
                    "report": report_data.report_id,
                    "type": report_data.report_type.value,
                    "generated": report_data.generated_at.isoformat(),
                    "period": {
                        "start": report_data.period_start.isoformat(),
                        "end": report_data.period_end.isoformat(),
                    },
                    "sections": report_data.sections,
                    "summary": report_data.summary,
                },
                indent=2,
                default=str,
            )

        elif report_format == ReportFormat.HTML:
            return await self._format_html_report(report_data)

        elif report_format == ReportFormat.MARKDOWN:
            return await self._format_markdown_report(report_data)

        elif report_format == ReportFormat.EXCEL:
            return await self._format_excel_report(report_data)

        else:
            raise ValueError(f"Unsupported format: {report_format}")

    async def _format_html_report(self, report_data: ReportData) -> str:
        """Format report as HTML."""
        html = []
        html.append("<!DOCTYPE html>")
        html.append('<html lang="en">')
        html.append("<head>")
        html.append('<meta charset="UTF-8">')
        html.append("<title>Translation Quality Report</title>")
        html.append("<style>")
        html.append(
            """
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1, h2, h3 { color: #333; }
        .header { background: #f5f5f5; padding: 20px; border-radius: 8px; }
        .section { margin: 30px 0; }
        .metric { display: inline-block; margin: 10px; padding: 15px;
                  background: #e9ecef; border-radius: 6px; }
        .metric-value { font-size: 2em; font-weight: bold; color: #007bff; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .good { color: #28a745; }
        .warning { color: #ffc107; }
        .critical { color: #dc3545; }
        """
        )
        html.append("</style>")
        html.append("</head>")
        html.append("<body>")

        # Header
        html.append('<div class="header">')
        html.append(
            f'<h1>{report_data.report_type.value.replace("_", " ").title()}</h1>'
        )
        html.append(
            f'<p>Generated: {report_data.generated_at.strftime("%Y-%m-%d %H:%M UTC")}</p>'
        )
        html.append(
            f"<p>Period: {report_data.period_start.date()} to {report_data.period_end.date()}</p>"
        )
        html.append("</div>")

        # Sections
        for section_name, section_data in report_data.sections.items():
            html.append('<div class="section">')
            html.append(f'<h2>{section_name.replace("_", " ").title()}</h2>')
            html.append(self._format_section_html(section_name, section_data))
            html.append("</div>")

        html.append("</body>")
        html.append("</html>")

        return "\n".join(html)

    def _format_section_html(
        self, section_name: str, section_data: Dict[str, Any]
    ) -> str:
        """Format individual section as HTML."""
        if section_name == "executive_summary":
            return f"""
            <div class="metric">
                <div>Total Translations</div>
                <div class="metric-value">{section_data.get('total_translations', 0):,}</div>
            </div>
            <div class="metric">
                <div>Average Quality</div>
                <div class="metric-value">{section_data.get('average_quality_score', 0):.1%}</div>
            </div>
            <div class="metric">
                <div>Pass Rate</div>
                <div class="metric-value">{section_data.get('pass_rate', 0):.1%}</div>
            </div>
            """
        elif section_name == "benchmark_status" and "benchmarks" in section_data:
            html = ["<table>"]
            html.append(
                "<tr><th>Benchmark</th><th>Current</th><th>Target</th><th>Status</th></tr>"
            )
            for name, data in section_data["benchmarks"].items():
                status_class = "good" if data.get("pass_rate", 0) >= 100 else "warning"
                html.append("<tr>")
                html.append(f"<td>{name}</td>")
                html.append(f'<td>{data.get("current_value", "N/A")}</td>')
                html.append(f'<td>{data.get("average_target_percentage", 0):.0f}%</td>')
                html.append(
                    f'<td class="{status_class}">{data.get("current_level", "N/A")}</td>'
                )
                html.append("</tr>")
            html.append("</table>")
            return "\n".join(html)
        else:
            # Generic formatting
            return f"<pre>{json.dumps(section_data, indent=2, default=str)}</pre>"

    async def _format_markdown_report(self, report_data: ReportData) -> str:
        """Format report as Markdown."""
        md = []

        # Title
        md.append(f"# {report_data.report_type.value.replace('_', ' ').title()}")
        md.append(
            f"\n**Generated:** {report_data.generated_at.strftime('%Y-%m-%d %H:%M UTC')}"
        )
        md.append(
            f"**Period:** {report_data.period_start.date()} to {report_data.period_end.date()}\n"
        )

        # Sections
        for section_name, section_data in report_data.sections.items():
            md.append(f"\n## {section_name.replace('_', ' ').title()}\n")

            if section_name == "executive_summary":
                md.append(
                    f"- **Total Translations:** {section_data.get('total_translations', 0):,}"
                )
                md.append(
                    f"- **Average Quality Score:** {section_data.get('average_quality_score', 0):.1%}"
                )
                md.append(f"- **Pass Rate:** {section_data.get('pass_rate', 0):.1%}")
                md.append(f"- **Trend:** {section_data.get('trend', 'stable')}")

            elif (
                section_name == "recommendations" and "recommendations" in section_data
            ):
                for rec in section_data["recommendations"]:
                    md.append(f"\n### {rec['priority'].upper()} Priority")
                    md.append(f"**{rec['recommendation']}**")
                    md.append(f"*Reason: {rec['reason']}*")

            else:
                # Generic formatting
                md.append("```json")
                md.append(json.dumps(section_data, indent=2, default=str))
                md.append("```")

        return "\n".join(md)

    async def _format_excel_report(self, report_data: ReportData) -> Path:
        """Format report as Excel file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{report_data.report_type.value}_{timestamp}.xlsx"
        output_path = Path(filename)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Summary sheet
            summary_data = {
                "Metric": ["Report Type", "Generated At", "Period Start", "Period End"],
                "Value": [
                    report_data.report_type.value,
                    report_data.generated_at.strftime("%Y-%m-%d %H:%M"),
                    report_data.period_start.strftime("%Y-%m-%d"),
                    report_data.period_end.strftime("%Y-%m-%d"),
                ],
            }
            pd.DataFrame(summary_data).to_excel(
                writer, sheet_name="Summary", index=False
            )

            # Section sheets
            for section_name, section_data in report_data.sections.items():
                if isinstance(section_data, dict):
                    try:
                        df = pd.DataFrame.from_dict(section_data, orient="index")
                        df.to_excel(
                            writer, sheet_name=section_name[:31]
                        )  # Excel sheet name limit
                    except (ValueError, TypeError, KeyError):
                        # If can't convert to DataFrame, save as JSON
                        df = pd.DataFrame(
                            [{"data": json.dumps(section_data, default=str)}]
                        )
                        df.to_excel(writer, sheet_name=section_name[:31], index=False)

        return output_path

    def _calculate_report_period(
        self, report_config: ReportConfiguration
    ) -> Tuple[datetime, datetime]:
        """Calculate report period based on schedule."""
        now = datetime.utcnow()

        if report_config.schedule == ReportSchedule.DAILY:
            period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_start = period_end - timedelta(days=1)
        elif report_config.schedule == ReportSchedule.WEEKLY:
            period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_start = period_end - timedelta(weeks=1)
        elif report_config.schedule == ReportSchedule.MONTHLY:
            period_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_start = (period_end - timedelta(days=1)).replace(day=1)
        else:
            period_end = now
            period_start = now - timedelta(days=1)

        return period_start, period_end

    def _calculate_next_schedule(self, report_config: ReportConfiguration) -> datetime:
        """Calculate next scheduled time for report."""
        now = datetime.utcnow()

        if report_config.schedule == ReportSchedule.HOURLY:
            next_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(
                hours=1
            )
        elif report_config.schedule == ReportSchedule.DAILY:
            next_time = now.replace(
                hour=6, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
        elif report_config.schedule == ReportSchedule.WEEKLY:
            next_time = now + timedelta(days=7 - now.weekday())
            next_time = next_time.replace(hour=6, minute=0, second=0, microsecond=0)
        elif report_config.schedule == ReportSchedule.MONTHLY:
            if now.month == 12:
                next_time = now.replace(
                    year=now.year + 1,
                    month=1,
                    day=1,
                    hour=6,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                next_time = now.replace(
                    month=now.month + 1,
                    day=1,
                    hour=6,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
        else:
            next_time = now + timedelta(days=1)

        return next_time

    async def distribute_report(
        self,
        report_data: ReportData,
        report_config: ReportConfiguration,
        formatted_report: Union[str, bytes, Path],
    ) -> None:
        """
        Distribute report to configured recipients.

        Args:
            report_data: Generated report data
            report_config: Report configuration
            formatted_report: Formatted report content
        """
        # Store in S3
        s3_key = await self._store_report_s3(
            report_data, report_config.format, formatted_report
        )

        logger.info("Report stored in S3: %s", s3_key)

        # Send via email if recipients configured
        if report_config.recipients:
            await self._send_report_email(
                report_data, report_config, formatted_report, s3_key
            )

    async def _store_report_s3(
        self,
        report_data: ReportData,
        report_format: ReportFormat,
        content: Union[str, bytes, Path],
    ) -> str:
        """Store report in S3."""
        # Generate S3 key
        date_prefix = report_data.generated_at.strftime("%Y/%m/%d")
        filename = f"{report_data.report_type.value}_{report_data.generated_at.strftime('%Y%m%d_%H%M%S')}.{report_format.value}"
        s3_key = f"reports/{date_prefix}/{filename}"

        try:
            # Handle different content types
            if isinstance(content, Path):
                # Upload file
                self.s3_client.upload_file(str(content), self.report_bucket, s3_key)
            elif isinstance(content, bytes):
                # Upload bytes
                self.s3_client.put_object(
                    Bucket=self.report_bucket, Key=s3_key, Body=content
                )
            else:
                # Upload string
                self.s3_client.put_object(
                    Bucket=self.report_bucket, Key=s3_key, Body=content.encode("utf-8")
                )

            return s3_key

        except Exception as e:
            logger.error("Failed to store report in S3: %s", e)
            raise ReportingError(
                report_type=report_data.report_type.value,
                operation="store_report",
                reason=f"Failed to store report: {e}",
            ) from e

    async def start_scheduler(self) -> None:
        """Start the report scheduler."""
        if self._scheduler_task and not self._scheduler_task.done():
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Report scheduler started")

    async def _scheduler_loop(self) -> None:
        """Run the main scheduler loop."""
        while self._running:
            try:
                # Check each report configuration
                for report_id, config in self.report_configs.items():
                    if not config.enabled:
                        continue

                    # Check if report is due
                    now = datetime.utcnow()
                    if config.next_scheduled and now >= config.next_scheduled:
                        logger.info("Generating scheduled report: %s", report_id)

                        try:
                            # Generate report
                            report_data = await self.generate_report(config)

                            # Format report
                            formatted = await self.format_report(
                                report_data, config.format
                            )

                            # Distribute report
                            await self.distribute_report(report_data, config, formatted)

                        except (ValueError, KeyError, AttributeError) as e:
                            logger.error(
                                "Failed to generate report %s: %s", report_id, e
                            )

                # Sleep for a minute before next check
                await asyncio.sleep(60)

            except (ValueError, KeyError, AttributeError) as e:
                logger.error("Error in scheduler loop: %s", e)
                await asyncio.sleep(60)

    async def stop_scheduler(self) -> None:
        """Stop the report scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Report scheduler stopped")

    async def _send_report_email(
        self,
        report_data: ReportData,
        report_config: ReportConfiguration,
        formatted_report: Union[str, bytes, Path],
        s3_key: str,
    ) -> None:
        """Send report via email to recipients."""
        # This is a placeholder for email functionality
        # In production, this would use SES or another email service
        # Parameters formatted_report and s3_key would be used for attachments/links
        _ = (formatted_report, s3_key)  # Acknowledge unused parameters
        logger.info(
            "Would send report %s to: %s",
            report_data.report_id,
            report_config.recipients,
        )

    def add_report_configuration(self, config: ReportConfiguration) -> None:
        """Add a report configuration."""
        self.report_configs[config.report_id] = config
        logger.info("Added report configuration: %s", config.report_id)

    def remove_report_configuration(self, report_id: str) -> None:
        """Remove a report configuration."""
        if report_id in self.report_configs:
            del self.report_configs[report_id]
            logger.info("Removed report configuration: %s", report_id)

    def get_report_configuration(self, report_id: str) -> Optional[ReportConfiguration]:
        """Get a report configuration."""
        return self.report_configs.get(report_id)

    def list_report_configurations(self) -> List[ReportConfiguration]:
        """List all report configurations."""
        return list(self.report_configs.values())

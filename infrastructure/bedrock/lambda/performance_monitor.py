"""
Bedrock Performance Monitor
Analyzes model performance metrics and generates insights
"""

import json
import logging
import os
import statistics
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
cloudwatch = boto3.client("cloudwatch")
s3 = boto3.client("s3")
sns = boto3.client("sns")

# Environment variables
METRICS_CONFIG = json.loads(os.environ["METRICS_CONFIG_JSON"])
THRESHOLD_CONFIG = json.loads(os.environ["THRESHOLD_CONFIG_JSON"])
ANALYSIS_BUCKET = os.environ["ANALYSIS_BUCKET"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
ENVIRONMENT = os.environ["ENVIRONMENT"]


class PerformanceMonitor:
    """Monitors and analyzes Bedrock model performance"""

    def __init__(self):
        self.metrics_config = METRICS_CONFIG
        self.thresholds = THRESHOLD_CONFIG
        self.analysis_window = 3600  # 1 hour window

    def analyze_performance(self) -> Dict[str, Any]:
        """Perform comprehensive performance analysis"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(seconds=self.analysis_window)

        analysis = {
            "timestamp": end_time.isoformat(),
            "environment": ENVIRONMENT,
            "latency_analysis": self.analyze_latency(start_time, end_time),
            "quality_analysis": self.analyze_quality(start_time, end_time),
            "cost_analysis": self.analyze_costs(start_time, end_time),
            "reliability_analysis": self.analyze_reliability(start_time, end_time),
            "recommendations": [],
        }

        # Generate recommendations based on analysis
        analysis["recommendations"] = self.generate_recommendations(analysis)

        # Check for alerts
        alerts = self.check_alert_conditions(analysis)
        if alerts:
            self.send_alerts(alerts, analysis)

        # Store analysis
        self.store_analysis(analysis)

        return analysis

    def analyze_latency(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Analyze latency metrics"""
        metrics = self.get_metrics(
            "ModelInvocationTime", start_time, end_time, ["Average", "Maximum", "p99"]
        )

        analysis = {
            "average_ms": metrics.get("Average", 0),
            "max_ms": metrics.get("Maximum", 0),
            "p99_ms": metrics.get("p99", 0),
            "trend": self.calculate_trend("ModelInvocationTime", start_time, end_time),
        }

        # Analyze by model
        model_latencies = self.get_metrics_by_dimension(
            "ModelInvocationTime", "ModelKey", start_time, end_time, "Average"
        )
        analysis["by_model"] = model_latencies

        return analysis

    def analyze_quality(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Analyze quality metrics"""
        quality_score = self.get_metrics(
            "ResponseQualityScore", start_time, end_time, ["Average", "Minimum"]
        )
        translation_accuracy = self.get_metrics(
            "TranslationAccuracy", start_time, end_time, ["Average"]
        )

        return {
            "quality_score": {
                "average": quality_score.get("Average", 0),
                "minimum": quality_score.get("Minimum", 0),
            },
            "translation_accuracy": translation_accuracy.get("Average", 0),
            "below_threshold_count": self.count_below_threshold(
                "ResponseQualityScore",
                self.thresholds["warning"]["quality_score_min"],
                start_time,
                end_time,
            ),
        }

    def analyze_costs(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Analyze cost metrics"""
        total_cost = self.get_metrics("CostPerRequest", start_time, end_time, ["Sum"])

        cost_by_model = self.get_metrics_by_dimension(
            "CostPerRequest", "ModelKey", start_time, end_time, "Sum"
        )

        # Calculate cost trend
        previous_window_cost = self.get_metrics(
            "CostPerRequest",
            start_time - timedelta(seconds=self.analysis_window),
            start_time,
            ["Sum"],
        )

        cost_increase = 0
        if previous_window_cost.get("Sum", 0) > 0:
            cost_increase = (
                total_cost.get("Sum", 0) / previous_window_cost["Sum"] - 1
            ) * 100
        return {
            "total_cost": total_cost.get("Sum", 0),
            "cost_by_model": cost_by_model,
            "cost_increase_percent": cost_increase,
            "cost_spike": cost_increase
            > (self.thresholds["warning"]["cost_spike_factor"] - 1) * 100,
        }

    def analyze_reliability(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Analyze reliability metrics"""
        error_rate = self.get_metrics(
            "ErrorRate", start_time, end_time, ["Average", "Maximum"]
        )

        fallback_rate = self.get_metrics(
            "FallbackRate", start_time, end_time, ["Average"]
        )

        circuit_trips = self.get_metrics(
            "CircuitBreakerTrips", start_time, end_time, ["Sum"]
        )

        return {
            "error_rate": {
                "average": error_rate.get("Average", 0),
                "maximum": error_rate.get("Maximum", 0),
            },
            "fallback_rate": fallback_rate.get("Average", 0),
            "circuit_breaker_trips": circuit_trips.get("Sum", 0),
            "availability": 100 - error_rate.get("Average", 0),
        }

    def get_metrics(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        statistics: List[str],
    ) -> Dict[str, float]:
        """Get CloudWatch metrics"""
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace="HavenHealthPassport/Bedrock",
                MetricName=metric_name,
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=statistics,
            )

            result = {}
            for stat in statistics:
                datapoints = [p[stat] for p in response["Datapoints"] if stat in p]
                if datapoints:
                    result[stat] = statistics.mean(datapoints)

            return result

        except Exception as e:
            logger.error(f"Failed to get metrics: {str(e)}")
            return {}

    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []

        # Latency recommendations
        if (
            analysis["latency_analysis"]["p99_ms"]
            > self.thresholds["warning"]["latency_p99_ms"]
        ):
            recommendations.append(
                f"High P99 latency ({analysis['latency_analysis']['p99_ms']}ms). "
                "Consider using simpler models or enabling caching."
            )

        # Quality recommendations
        if (
            analysis["quality_analysis"]["quality_score"]["minimum"]
            < self.thresholds["warning"]["quality_score_min"]
        ):
            recommendations.append(
                "Quality scores below threshold. Review model selection and parameters."
            )

        # Cost recommendations
        if analysis["cost_analysis"]["cost_spike"]:
            recommendations.append(
                f"Cost spike detected ({analysis['cost_analysis']['cost_increase_percent']:.1f}% increase). "
                "Review usage patterns and consider optimization."
            )

        # Reliability recommendations
        if (
            analysis["reliability_analysis"]["error_rate"]["average"]
            > self.thresholds["warning"]["error_rate_percent"]
        ):
            recommendations.append(
                f"High error rate ({analysis['reliability_analysis']['error_rate']['average']:.1f}%). "
                "Check model health and fallback configurations."
            )

        return recommendations

    def check_alert_conditions(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check if any alert conditions are met"""
        alerts = []

        # Critical latency alert
        if (
            analysis["latency_analysis"]["p99_ms"]
            > self.thresholds["critical"]["latency_p99_ms"]
        ):
            alerts.append(
                {
                    "severity": "CRITICAL",
                    "type": "LATENCY",
                    "message": f"Critical P99 latency: {analysis['latency_analysis']['p99_ms']}ms",
                }
            )

        # Critical error rate alert
        if (
            analysis["reliability_analysis"]["error_rate"]["average"]
            > self.thresholds["critical"]["error_rate_percent"]
        ):
            alerts.append(
                {
                    "severity": "CRITICAL",
                    "type": "ERROR_RATE",
                    "message": f"Critical error rate: {analysis['reliability_analysis']['error_rate']['average']:.1f}%",
                }
            )

        return alerts

    def send_alerts(self, alerts: List[Dict[str, Any]], analysis: Dict[str, Any]):
        """Send alerts via SNS"""
        try:
            message = self.format_alert_message(alerts, analysis)

            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"[{alerts[0]['severity']}] Bedrock Performance Alert - {ENVIRONMENT}",
                Message=message,
            )

        except Exception as e:
            logger.error(f"Failed to send alert: {str(e)}")

    def store_analysis(self, analysis: Dict[str, Any]):
        """Store analysis results in S3"""
        try:
            key = f"analysis/{ENVIRONMENT}/{datetime.utcnow().strftime('%Y/%m/%d')}/{int(time.time())}.json"

            s3.put_object(
                Bucket=ANALYSIS_BUCKET,
                Key=key,
                Body=json.dumps(analysis, indent=2),
                ContentType="application/json",
            )

        except Exception as e:
            logger.error(f"Failed to store analysis: {str(e)}")

    def format_alert_message(
        self, alerts: List[Dict[str, Any]], analysis: Dict[str, Any]
    ) -> str:
        """Format alert message"""
        lines = [
            f"Environment: {ENVIRONMENT}",
            f"Time: {analysis['timestamp']}",
            "",
            "ALERTS:",
        ]

        for alert in alerts:
            lines.append(f"- [{alert['severity']}] {alert['message']}")

        lines.extend(
            [
                "",
                "SUMMARY:",
                f"- Availability: {analysis['reliability_analysis']['availability']:.1f}%",
                f"- P99 Latency: {analysis['latency_analysis']['p99_ms']}ms",
                f"- Error Rate: {analysis['reliability_analysis']['error_rate']['average']:.1f}%",
                "",
                "RECOMMENDATIONS:",
            ]
        )

        for rec in analysis["recommendations"]:
            lines.append(f"- {rec}")

        return "\n".join(lines)


def handler(event, context):
    """Lambda handler for performance monitoring"""
    try:
        # Initialize monitor
        monitor = PerformanceMonitor()

        # Perform analysis
        analysis = monitor.analyze_performance()

        logger.info(
            f"Performance analysis completed: {len(analysis['recommendations'])} recommendations"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(analysis),
            "headers": {"Content-Type": "application/json"},
        }

    except Exception as e:
        logger.error(f"Performance monitoring error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }

    def get_metrics_by_dimension(
        self,
        metric_name: str,
        dimension_name: str,
        start_time: datetime,
        end_time: datetime,
        statistic: str,
    ) -> Dict[str, float]:
        """Get metrics grouped by dimension"""
        # Simplified implementation - would query with dimension filters
        return {}

    def calculate_trend(
        self, metric_name: str, start_time: datetime, end_time: datetime
    ) -> str:
        """Calculate metric trend"""
        # Simplified - would calculate actual trend
        return "stable"

    def count_below_threshold(
        self,
        metric_name: str,
        threshold: float,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Count datapoints below threshold"""
        # Simplified - would count actual violations
        return 0

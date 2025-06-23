"""AWS-specific Callback Handler for LangChain.

Integrates with CloudWatch, X-Ray, and other AWS services
"""

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

try:
    from aws_lambda_powertools import Metrics, Tracer
    from aws_lambda_powertools.metrics import MetricUnit

    HAS_POWERTOOLS = True
except ImportError:
    # Mock implementation for when powertools is not installed
    HAS_POWERTOOLS = False

    class Tracer:  # type: ignore[no-redef]
        """Stub for X-Ray tracer."""

        def capture_method(self, func: Any) -> Any:
            """Capture method for tracing."""
            return func

        def put_annotation(self, key: str, value: Any) -> None:
            """Put annotation for tracing."""

    class Metrics:  # type: ignore[no-redef]
        """Metrics collection for AWS X-Ray."""

        def add_metric(self, name: str, unit: str, value: Any) -> None:
            """Add a metric to the collection.

            Args:
                name: Metric name
                unit: Metric unit
                value: Metric value
            """

    class MetricUnit:  # type: ignore[no-redef]
        """Metric unit constants for AWS X-Ray."""

        Count = "Count"
        Seconds = "Seconds"

    tracer = Tracer()
    metrics = Metrics()
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

if HAS_POWERTOOLS:
    tracer = Tracer()
    metrics = Metrics()
else:
    tracer = None
    metrics = None


# Create a decorator that works with or without tracer
def capture_method(func: Any) -> Any:
    """Use tracer.capture_method if available as a decorator."""
    if tracer and hasattr(tracer, "capture_method"):
        return tracer.capture_method(func)
    return func


class AWSCallbackHandler(BaseCallbackHandler):
    """Callback handler for AWS integration."""

    def __init__(
        self,
        cloudwatch_client: Optional[Any] = None,
        log_group_name: str = "/aws/langchain/haven-health-passport",
        enable_xray: bool = True,
        enable_metrics: bool = True,
    ):
        """Initialize AWS callback handler.

        Args:
            cloudwatch_client: Optional CloudWatch client
            log_group_name: CloudWatch log group name
            enable_xray: Enable X-Ray tracing
            enable_metrics: Enable CloudWatch metrics
        """
        self.cloudwatch = cloudwatch_client or boto3.client("cloudwatch")
        self.log_group_name = log_group_name
        self.enable_xray = enable_xray
        self.enable_metrics = enable_metrics
        self.run_metrics: Dict[str, Any] = {}

    @capture_method
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM starts running."""
        run_id_str = str(run_id)
        self.run_metrics[run_id_str] = {
            "start_time": time.time(),
            "model": serialized.get("id", ["unknown"])[0],
            "prompts_count": len(prompts),
            "tags": tags or [],
        }

        if self.enable_xray:
            tracer.put_annotation(
                key="model", value=self.run_metrics[run_id_str]["model"]
            )
            tracer.put_annotation(key="run_id", value=run_id_str)

        logger.info("LLM run started: %s", run_id_str)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM ends running."""
        run_id_str = str(run_id)

        if run_id_str in self.run_metrics:
            duration = time.time() - self.run_metrics[run_id_str]["start_time"]

            # Extract token usage if available
            token_usage = {}
            if response.llm_output:
                token_usage = response.llm_output.get("usage", {})
            # Log metrics to CloudWatch
            if self.enable_metrics:
                self._log_metrics(
                    model=self.run_metrics[run_id_str]["model"],
                    duration=duration,
                    token_usage=token_usage,
                    tags=self.run_metrics[run_id_str]["tags"],
                )

            # Clean up
            del self.run_metrics[run_id_str]

        logger.info("LLM run completed: %s, duration: %.2fs", run_id_str, duration)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM errors."""
        run_id_str = str(run_id)
        logger.error("LLM error in run %s: %s", run_id_str, str(error))

        if self.enable_metrics and metrics:
            metrics.add_metric(name="LLMErrors", unit=MetricUnit.Count, value=1)

        # Clean up
        if run_id_str in self.run_metrics:
            del self.run_metrics[run_id_str]

    def _log_metrics(
        self, model: str, duration: float, token_usage: Dict[str, int], tags: List[str]
    ) -> None:
        """Log metrics to CloudWatch."""
        _ = tags  # Mark as intentionally unused
        try:
            metric_data = [
                {
                    "MetricName": "LLMInvocationDuration",
                    "Value": duration,
                    "Unit": "Seconds",
                    "Dimensions": [
                        {"Name": "Model", "Value": model},
                        {"Name": "Environment", "Value": "production"},
                    ],
                },
                {
                    "MetricName": "LLMInvocationCount",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Model", "Value": model}],
                },
            ]

            # Add token usage metrics if available
            if token_usage:
                if "total_tokens" in token_usage:
                    metric_data.append(
                        {
                            "MetricName": "TokensUsed",
                            "Value": token_usage["total_tokens"],
                            "Unit": "Count",
                            "Dimensions": [{"Name": "Model", "Value": model}],
                        }
                    )

            self.cloudwatch.put_metric_data(
                Namespace="HavenHealthPassport/LangChain", MetricData=metric_data
            )

        except ClientError as e:
            logger.error("Failed to log metrics: %s", str(e))

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when chain starts running."""
        logger.debug("Chain started: %s", run_id)

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when chain ends running."""
        logger.debug("Chain ended: %s", run_id)

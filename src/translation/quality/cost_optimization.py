"""Translation Cost Optimization - Optimizes translation costs across providers."""

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TranslationCost:
    """Cost data for a translation request."""

    timestamp: datetime
    provider: str  # 'bedrock', 'openai', 'google', 'cache'
    model_id: str
    language_pair: str
    input_tokens: int
    output_tokens: int
    cost: float  # USD
    cached: bool = False
    quality_score: Optional[float] = None


@dataclass
class CostOptimizationStrategy:
    """Strategy for optimizing translation costs."""

    name: str
    description: str
    rules: List[Dict[str, Any]]
    priority: int = 0
    enabled: bool = True


class TranslationCostOptimizer:
    """Optimizes translation costs while maintaining quality."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize cost optimizer."""
        self.config = self._load_config(config_path)
        self.cost_history: List[TranslationCost] = []
        self.provider_costs = self.config["provider_costs"]
        self.strategies = self._initialize_strategies()
        self.cache_stats: Dict[str, int] = defaultdict(int)
        self._load_cost_history()

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load cost optimization configuration."""
        if config_path and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                return data

        # Default configuration
        return {
            "provider_costs": {
                "bedrock": {
                    "claude-3-haiku": {
                        "input": 0.00025,
                        "output": 0.00125,
                    },  # per 1k tokens
                    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
                    "claude-3-opus": {"input": 0.015, "output": 0.075},
                },
                "openai": {
                    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
                    "gpt-4": {"input": 0.03, "output": 0.06},
                },
            },
            "quality_thresholds": {"medical": 0.9, "legal": 0.85, "general": 0.7},
            "cache_ttl_hours": 168,  # 1 week
            "budget_limits": {"daily": 100.0, "monthly": 2000.0},
        }

    def _initialize_strategies(self) -> List[CostOptimizationStrategy]:
        """Initialize cost optimization strategies."""
        return [
            CostOptimizationStrategy(
                name="cache_first",
                description="Use cached translations when available",
                rules=[{"type": "cache_lookup", "similarity_threshold": 0.95}],
                priority=1,
            ),
            CostOptimizationStrategy(
                name="model_selection",
                description="Select appropriate model based on domain",
                rules=[
                    {"domain": "medical", "preferred_model": "claude-3-sonnet"},
                    {"domain": "general", "preferred_model": "claude-3-haiku"},
                    {"length": "<100", "preferred_model": "gpt-3.5-turbo"},
                ],
                priority=2,
            ),
        ]

    def _load_cost_history(self) -> None:
        """Load cost history from storage."""
        history_file = Path("translation_costs.json")
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cost_history = [
                        TranslationCost(
                            timestamp=datetime.fromisoformat(c["timestamp"]),
                            provider=c["provider"],
                            model_id=c["model_id"],
                            language_pair=c["language_pair"],
                            input_tokens=c["input_tokens"],
                            output_tokens=c["output_tokens"],
                            cost=c["cost"],
                            cached=c.get("cached", False),
                            quality_score=c.get("quality_score"),
                        )
                        for c in data.get("costs", [])
                    ]
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                logger.error(f"Error loading cost history: {e}")

    def select_optimal_provider(
        self,
        text: str,
        source_language: str,
        target_language: str,
        domain: str,
        required_quality: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Select optimal provider/model for translation."""
        language_pair = f"{source_language}-{target_language}"
        text_length = len(text.split())

        # Check cache first
        if self._check_cache(text, language_pair):
            return {
                "provider": "cache",
                "model_id": "cached",
                "estimated_cost": 0.0,
                "reason": "Found in cache",
            }

        # Get quality threshold
        quality_threshold = required_quality or self.config["quality_thresholds"].get(
            domain, 0.7
        )

        # Evaluate strategies
        candidates = []

        for provider, models in self.provider_costs.items():
            for model_id, costs in models.items():
                # Estimate tokens (rough approximation)
                estimated_tokens = text_length * 1.5

                # Calculate cost
                input_cost = (estimated_tokens / 1000) * costs["input"]
                output_cost = (estimated_tokens / 1000) * costs["output"]
                total_cost = input_cost + output_cost

                # Check if model meets quality requirements
                if self._meets_quality_requirements(
                    model_id, domain, quality_threshold
                ):
                    candidates.append(
                        {
                            "provider": provider,
                            "model_id": model_id,
                            "estimated_cost": total_cost,
                            "quality_score": self._estimate_quality(model_id, domain),
                        }
                    )

        # Sort by cost (ascending) and quality (descending)
        candidates.sort(key=lambda x: (x["estimated_cost"], -x["quality_score"]))

        if candidates:
            selected = candidates[0]
            selected["reason"] = f"Best cost-quality balance for {domain}"
            return selected

        # Fallback to default
        return {
            "provider": "bedrock",
            "model_id": "claude-3-haiku",
            "estimated_cost": 0.001,
            "reason": "Default fallback",
        }

    def _check_cache(self, _text: str, _language_pair: str) -> bool:
        """Check if translation exists in cache."""
        # Simplified cache check - in production would use actual cache
        return False  # Placeholder

    def _meets_quality_requirements(
        self, model_id: str, domain: str, threshold: float
    ) -> bool:
        """Check if model meets quality requirements."""
        # Model quality estimates (simplified)
        model_quality = {
            "claude-3-opus": 0.95,
            "claude-3-sonnet": 0.9,
            "claude-3-haiku": 0.85,
            "gpt-4": 0.93,
            "gpt-3.5-turbo": 0.8,
        }

        base_quality = model_quality.get(model_id, 0.7)

        # Adjust for domain
        if domain == "medical" and "claude" in model_id:
            base_quality += 0.05  # Claude models better for medical

        return base_quality >= threshold

    def _estimate_quality(self, model_id: str, domain: str) -> float:
        """Estimate quality score for model/domain combination."""
        base_scores = {
            "claude-3-opus": 0.95,
            "claude-3-sonnet": 0.9,
            "claude-3-haiku": 0.85,
            "gpt-4": 0.93,
            "gpt-3.5-turbo": 0.8,
        }

        score = base_scores.get(model_id, 0.7)

        # Domain adjustments
        if domain == "medical":
            if "claude" in model_id:
                score += 0.05
            else:
                score -= 0.05

        return min(score, 1.0)

    def record_cost(
        self,
        provider: str,
        model_id: str,
        language_pair: str,
        input_tokens: int,
        output_tokens: int,
        cached: bool = False,
        quality_score: Optional[float] = None,
    ) -> None:
        """Record actual translation cost."""
        # Calculate cost
        if cached:
            cost = 0.0
        else:
            model_costs = self.provider_costs.get(provider, {}).get(model_id, {})
            input_cost = (input_tokens / 1000) * model_costs.get("input", 0)
            output_cost = (output_tokens / 1000) * model_costs.get("output", 0)
            cost = input_cost + output_cost

        # Record cost
        cost_record = TranslationCost(
            timestamp=datetime.now(),
            provider=provider,
            model_id=model_id,
            language_pair=language_pair,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            cached=cached,
            quality_score=quality_score,
        )

        self.cost_history.append(cost_record)

        # Update cache stats
        if cached:
            self.cache_stats["hits"] += 1
        else:
            self.cache_stats["misses"] += 1

        # Check budget limits
        self._check_budget_limits()

    def _check_budget_limits(self) -> None:
        """Check if budget limits are exceeded."""
        now = datetime.now()

        # Daily limit
        daily_costs = sum(
            c.cost for c in self.cost_history if c.timestamp.date() == now.date()
        )

        if daily_costs > self.config["budget_limits"]["daily"]:
            logger.warning(f"Daily budget limit exceeded: ${daily_costs:.2f}")

        # Monthly limit
        monthly_costs = sum(
            c.cost
            for c in self.cost_history
            if c.timestamp.month == now.month and c.timestamp.year == now.year
        )

        if monthly_costs > self.config["budget_limits"]["monthly"]:
            logger.warning(f"Monthly budget limit exceeded: ${monthly_costs:.2f}")

    def get_cost_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get cost summary for period."""
        cutoff = datetime.now() - timedelta(days=days)
        recent_costs = [c for c in self.cost_history if c.timestamp >= cutoff]

        if not recent_costs:
            return {"total_cost": 0, "translations": 0}

        # Calculate summary
        summary: Dict[str, Any] = {
            "total_cost": sum(c.cost for c in recent_costs),
            "translations": len(recent_costs),
            "cache_hit_rate": self.cache_stats["hits"]
            / max(self.cache_stats["hits"] + self.cache_stats["misses"], 1),
            "by_provider": defaultdict(float),
            "by_language_pair": defaultdict(float),
            "average_cost_per_translation": 0,
        }

        # Group by provider
        for cost in recent_costs:
            summary["by_provider"][f"{cost.provider}/{cost.model_id}"] += cost.cost
            summary["by_language_pair"][cost.language_pair] += cost.cost

        summary["average_cost_per_translation"] = summary["total_cost"] / len(
            recent_costs
        )

        return dict(summary)

    def optimize_strategies(self) -> None:
        """Optimize strategies based on historical data."""
        # Analyze cost-quality tradeoffs
        recent_costs = [
            c
            for c in self.cost_history
            if c.quality_score is not None
            and c.timestamp >= datetime.now() - timedelta(days=7)
        ]

        if len(recent_costs) < 10:
            return  # Not enough data

        # Group by model
        model_performance = defaultdict(list)
        for cost in recent_costs:
            key = f"{cost.provider}/{cost.model_id}"
            model_performance[key].append(
                {"cost": cost.cost, "quality": cost.quality_score}
            )

        # Calculate cost-quality ratios
        model_scores = {}
        for model, performance in model_performance.items():
            avg_cost = sum(
                p["cost"] for p in performance if p["cost"] is not None
            ) / len(performance)
            avg_quality = sum(
                p["quality"] for p in performance if p["quality"] is not None
            ) / len(performance)

            # Higher score is better (high quality, low cost)
            model_scores[model] = avg_quality / max(avg_cost, 0.001)

        # Update strategy rules based on scores
        logger.info(f"Model performance scores: {model_scores}")

    def export_cost_report(self, output_path: str) -> None:
        """Export detailed cost report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": self.get_cost_summary(days=30),
            "daily_costs": self._calculate_daily_costs(days=30),
            "model_usage": self._calculate_model_usage(),
            "optimization_recommendations": self._generate_recommendations(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Exported cost report to {output_path}")

    def _calculate_daily_costs(self, days: int) -> List[Dict[str, Any]]:
        """Calculate costs by day."""
        daily_costs: Dict[str, float] = defaultdict(float)

        cutoff = datetime.now() - timedelta(days=days)
        for cost in self.cost_history:
            if cost.timestamp >= cutoff:
                date_key = cost.timestamp.date().isoformat()
                daily_costs[date_key] += cost.cost

        return [
            {"date": date, "cost": cost} for date, cost in sorted(daily_costs.items())
        ]

    def _calculate_model_usage(self) -> Dict[str, int]:
        """Calculate usage by model."""
        usage: Dict[str, int] = defaultdict(int)

        for cost in self.cost_history:
            key = f"{cost.provider}/{cost.model_id}"
            usage[key] += 1

        return dict(usage)

    def _generate_recommendations(self) -> List[str]:
        """Generate cost optimization recommendations."""
        recommendations = []

        # Check cache hit rate
        if self.cache_stats["hits"] + self.cache_stats["misses"] > 0:
            hit_rate = self.cache_stats["hits"] / (
                self.cache_stats["hits"] + self.cache_stats["misses"]
            )
            if hit_rate < 0.3:
                recommendations.append(
                    "Consider implementing more aggressive caching to improve hit rate"
                )

        # Check cost trends
        recent_avg = self.get_cost_summary(days=7).get(
            "average_cost_per_translation", 0
        )
        if recent_avg > 0.01:  # $0.01 per translation
            recommendations.append(
                "Average cost per translation is high. Consider using lower-cost models for non-critical content"
            )

        return recommendations

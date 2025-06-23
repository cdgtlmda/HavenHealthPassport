"""
Demo script for Alert Mechanisms Configuration

This script demonstrates the functionality of the alert mechanisms
for translation quality monitoring.
"""

import asyncio
from datetime import datetime, timedelta

from src.ai.translation.validation.alert_mechanisms import (
    AlertChannel,
    AlertMechanismManager,
    AlertPriority,
    AlertRule,
    SlackChannelConfig,
)
from src.ai.translation.validation.threshold_alerts import (
    AlertType,
    ThresholdDefinition,
)


async def demo_alert_mechanisms():
    """Demonstrate alert mechanisms functionality."""

    print("🚨 Initializing Alert Mechanisms...")
    alert_manager = AlertMechanismManager()

    # Show default alert rules
    print("\n📋 Default Alert Rules:")
    for rule_id, rule in alert_manager.alert_rules.items():
        print(f"   - {rule.name} ({rule.priority.value})")
        print(f"     Metric: {rule.threshold.metric_name} {rule.threshold.operator} {rule.threshold.value}")
        print(f"     Channels: {[c.value for c in rule.channels]}")

    # Demo 1: Process metrics that trigger alerts
    print("\n⚠️  Simulating Quality Drop...")

    critical_metrics = {
        "quality_score": 0.65,      # Below critical threshold (0.70)
        "pass_rate": 0.75,          # Below high threshold (0.80)
        "validation_time": 6.0,     # Above performance threshold (5.0)
        "terminology_accuracy": 0.92 # Below accuracy threshold (0.95)
    }

    alerts = await alert_manager.process_metrics(critical_metrics)

    print(f"\n🔔 {len(alerts)} alerts triggered:")    for alert in alerts:
        print(f"   - [{alert['priority']}] {alert['rule_name']}")
        print(f"     {alert['description']}")

    # Demo 2: Add custom alert rule
    print("\n🔧 Adding Custom Alert Rule...")

    custom_rule = AlertRule(
        rule_id="language_pair_quality",
        name="Spanish Translation Quality Alert",
        description="Alert when Spanish translations drop below threshold",
        alert_type=AlertType.THRESHOLD_BREACH,
        priority=AlertPriority.P2_HIGH,
        channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
        threshold=ThresholdDefinition(
            alert_type=AlertType.THRESHOLD_BREACH,
            metric_name="quality_score",
            value=0.85,
            operator="<",
            window_minutes=15
        ),
        cooldown_minutes=60,
        filters={"language_pair": "en-es"}
    )

    alert_manager.add_alert_rule(custom_rule)
    print(f"✅ Added custom rule: {custom_rule.name}")

    # Demo 3: Configure Slack channel
    print("\n💬 Configuring Slack Channel...")

    slack_config = SlackChannelConfig(
        webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
        channel="#critical-alerts",
        username="Translation Bot",
        icon_emoji=":warning:"
    )

    alert_manager.configure_channel(slack_config)
    print("✅ Slack channel configured")

    # Demo 4: Get alert summary
    print("\n📊 Alert Summary (Last 24 Hours):")
    summary = alert_manager.get_alert_summary(timedelta(hours=24))

    print(f"   Total Alerts: {summary['total_alerts']}")
    print(f"   By Priority:")
    for priority, count in summary['by_priority'].items():
        print(f"     - {priority}: {count}")

    # Demo 5: Show alert history
    print("\n📜 Recent Alert History:")
    history = alert_manager.get_alert_history(limit=5)

    for alert in history[:3]:  # Show first 3
        print(f"   - [{alert['priority']}] {alert['rule_id']}")
        print(f"     Time: {alert['timestamp']}")
        print(f"     Metric: {alert['metric']} = {alert['value']:.3f}")

    print("\n✅ Alert Mechanisms Demo Complete!")
    print("\nThe system provides:")
    print("   - Automatic alert triggering based on metric thresholds")
    print("   - Multiple alert channels (Email, Slack, SNS, CloudWatch)")
    print("   - Priority-based routing (P1-P5)")
    print("   - Cooldown periods to prevent alert fatigue")
    print("   - Language pair and mode-specific alerts")
    print("   - Alert history and summary reporting")


if __name__ == "__main__":
    asyncio.run(demo_alert_mechanisms())

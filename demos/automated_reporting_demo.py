"""
Demo script for Automated Reporting System

This script demonstrates the functionality of the automated reporting system
for translation quality monitoring.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from src.ai.translation.validation.automated_reporting import (
    AutomatedReportingSystem,
    ReportConfiguration,
    ReportFormat,
    ReportSchedule,
    ReportType,
)


async def demo_automated_reporting():
    """Demonstrate automated reporting functionality."""

    print("📊 Initializing Automated Reporting System...")
    reporting_system = AutomatedReportingSystem()

    # Initialize default reports
    reporting_system.initialize_default_reports()
    print("✅ Default reports configured")

    # List configured reports
    print("\n📋 Configured Reports:")
    for config in reporting_system.list_report_configurations():
        print(f"   - {config.report_id}: {config.report_type.value} ({config.schedule.value})")

    # Demo 1: Generate Daily Summary Report
    print("\n📈 Generating Daily Summary Report...")
    daily_config = reporting_system.get_report_configuration("daily_summary")

    if daily_config:
        # Generate report
        report_data = await reporting_system.generate_report(
            daily_config,
            custom_period=(
                datetime.utcnow() - timedelta(days=1),
                datetime.utcnow()
            )
        )

        print(f"✅ Report generated: {report_data.report_id}")        print(f"   Period: {report_data.period_start.date()} to {report_data.period_end.date()}")
        print(f"   Sections: {list(report_data.sections.keys())}")

        # Format as HTML
        html_report = await reporting_system.format_report(
            report_data,
            ReportFormat.HTML
        )

        # Save to file
        html_path = Path("daily_summary_report.html")
        with open(html_path, 'w') as f:
            f.write(html_report)

        print(f"✅ HTML report saved to: {html_path}")

    # Demo 2: Create Custom Report Configuration
    print("\n🔧 Creating Custom Report Configuration...")

    custom_config = ReportConfiguration(
        report_id="language_pair_analysis",
        report_type=ReportType.CUSTOM,
        schedule=ReportSchedule.WEEKLY,
        format=ReportFormat.MARKDOWN,
        recipients=["quality-team@example.com"],
        filters={"language_pair": "en-es"},
        include_sections=[
            "executive_summary",
            "benchmark_status",
            "performance_trends",
            "recommendations"
        ]
    )

    reporting_system.add_report_configuration(custom_config)
    print("✅ Custom report configuration added")

    # Generate custom report
    print("\n📊 Generating Custom Report...")
    custom_report_data = await reporting_system.generate_report(custom_config)

    # Format as Markdown
    md_report = await reporting_system.format_report(
        custom_report_data,
        ReportFormat.MARKDOWN
    )

    # Save to file
    md_path = Path("custom_language_analysis.md")
    with open(md_path, 'w') as f:
        f.write(md_report)

    print(f"✅ Markdown report saved to: {md_path}")
    # Demo 3: Schedule Information
    print("\n⏰ Report Scheduling Information:")
    for config in reporting_system.list_report_configurations():
        next_scheduled = reporting_system._calculate_next_schedule(config)
        print(f"   - {config.report_id}: Next run at {next_scheduled.strftime('%Y-%m-%d %H:%M UTC')}")

    print("\n✅ Automated Reporting Demo Complete!")
    print("\nThe system provides:")
    print("   - Scheduled report generation (hourly, daily, weekly, monthly)")
    print("   - Multiple output formats (HTML, PDF, Excel, Markdown, JSON)")
    print("   - Customizable report sections")
    print("   - Email distribution to recipients")
    print("   - S3 storage for archival")
    print("   - Flexible filtering by language pair and mode")


if __name__ == "__main__":
    asyncio.run(demo_automated_reporting())

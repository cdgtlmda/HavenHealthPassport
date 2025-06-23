"""
Demo script for Quality Dashboards System

This script demonstrates the functionality of the quality dashboards system
for visualizing translation quality metrics and benchmarks.
"""

import asyncio
from datetime import datetime
from pathlib import Path

from src.ai.translation.validation import (
    DashboardRenderer,
    DashboardType,
    QualityDashboardManager,
    TimeRange,
)


async def demo_dashboards():
    """Demonstrate quality dashboards functionality."""

    print("📊 Initializing Quality Dashboards System...")
    dashboard_manager = QualityDashboardManager()
    renderer = DashboardRenderer()

    # Demo 1: Overview Dashboard
    print("\n📈 Generating Overview Dashboard...")
    overview_data = await dashboard_manager.get_dashboard_data(
        DashboardType.OVERVIEW, TimeRange.LAST_24_HOURS
    )

    print(f"✅ Dashboard generated at: {overview_data.generated_at}")
    print(f"   Dashboard Type: {overview_data.dashboard_type.value}")
    print(f"   Time Range: {overview_data.time_range.value}")
    print(f"   Widgets: {len(overview_data.data)}")

    # Demo 2: Performance Dashboard
    print("\n⚡ Generating Performance Dashboard...")
    performance_data = await dashboard_manager.get_dashboard_data(
        DashboardType.PERFORMANCE, TimeRange.LAST_7_DAYS, language_pair=("en", "es")
    )

    print(f"✅ Performance dashboard generated")
    print(f"   Filtered by language pair: en->es")
    # Demo 3: Benchmarks Dashboard
    print("\n🎯 Generating Benchmarks Dashboard...")
    benchmarks_data = await dashboard_manager.get_dashboard_data(
        DashboardType.BENCHMARKS, TimeRange.LAST_30_DAYS
    )

    print(f"✅ Benchmarks dashboard generated")

    # Demo 4: Export Dashboard Data
    print("\n💾 Exporting Dashboard Data...")

    # Export as JSON
    json_path = await dashboard_manager.export_dashboard_data(
        DashboardType.OVERVIEW,
        format="json",
        output_path=Path("dashboard_overview.json"),
    )
    print(f"✅ Exported to JSON: {json_path}")

    # Export as CSV
    csv_path = await dashboard_manager.export_dashboard_data(
        DashboardType.BENCHMARKS,
        format="csv",
        output_path=Path("dashboard_benchmarks.csv"),
    )
    print(f"✅ Exported to CSV: {csv_path}")

    # Demo 5: Render HTML Dashboard
    print("\n🌐 Rendering HTML Dashboard...")
    html = renderer.render_html(overview_data)

    # Save HTML to file
    html_path = Path("dashboard_overview.html")
    with open(html_path, "w") as f:
        f.write(html)

    print(f"✅ HTML dashboard saved to: {html_path}")
    print(f"   Open in browser to view interactive dashboard")

    # Display sample widget data
    print("\n📊 Sample Widget Data:")
    for widget_id, widget_data in overview_data.data.items():
        print(f"\n   Widget: {widget_id}")
        if isinstance(widget_data, dict):
            for key, value in list(widget_data.items())[:3]:  # Show first 3 items
                print(f"     - {key}: {value}")

    print("\n✅ Quality Dashboards Demo Complete!")
    print("   The dashboards provide real-time visualization of:")
    print("   - Current performance metrics")
    print("   - Quality trends over time")
    print("   - Benchmark achievement status")
    print("   - Language pair performance heatmaps")
    print("   - Performance comparisons and alerts")


if __name__ == "__main__":
    asyncio.run(demo_dashboards())

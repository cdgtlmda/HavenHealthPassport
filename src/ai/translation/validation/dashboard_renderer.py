"""
Dashboard Renderer for Quality Dashboards.

This module provides HTML rendering capabilities for the quality dashboards.
"""

import json
from typing import Any, Dict

from .quality_dashboards import DashboardData


class DashboardRenderer:
    """Renders dashboard data as HTML."""

    def render_html(self, dashboard_data: DashboardData) -> str:
        """Render dashboard data as HTML."""
        html = []
        html.append("<!DOCTYPE html>")
        html.append('<html lang="en">')
        html.append("<head>")
        html.append('<meta charset="UTF-8">')
        html.append(
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        )
        html.append(
            f"<title>Translation Quality Dashboard - {dashboard_data.dashboard_type.value}</title>"
        )
        html.append("<style>")
        html.append(self._get_styles())
        html.append("</style>")
        html.append('<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>')
        html.append("</head>")
        html.append("<body>")

        # Header
        html.append('<div class="header">')
        html.append("<h1>Translation Quality Dashboard</h1>")
        html.append(
            f'<p class="subtitle">{dashboard_data.dashboard_type.value.title()} View</p>'
        )
        html.append(
            f'<p class="timestamp">Generated: {dashboard_data.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</p>'
        )
        html.append("</div>")

        # Content
        html.append('<div class="dashboard-content">')

        for widget_id, widget_data in dashboard_data.data.items():
            html.append(self._render_widget(widget_id, widget_data))

        html.append("</div>")
        html.append("</body>")
        html.append("</html>")

        return "\n".join(html)

    def _get_styles(self) -> str:
        """Get CSS styles for the dashboard."""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
        }
        .header {
            background: #1a1a1a;
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2em;
        }
        .subtitle {
            margin: 10px 0 0 0;
            opacity: 0.8;
        }
        .timestamp {
            margin: 5px 0 0 0;
            font-size: 0.9em;
            opacity: 0.6;
        }
        .dashboard-content {
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .widget {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .widget h3 {
            margin: 0 0 20px 0;
            color: #333;
        }        .metric-card {
            padding: 15px;
            border-radius: 6px;
            background: #f8f9fa;
            margin-bottom: 10px;
        }
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        .metric-label {
            color: #666;
            font-size: 0.9em;
        }
        .status-excellent { color: #28a745; }
        .status-good { color: #17a2b8; }
        .status-warning { color: #ffc107; }
        .status-critical { color: #dc3545; }
        .chart-container {
            position: relative;
            height: 300px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #f8f9fa;
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
        }
        .badge-success {
            background: #d4edda;
            color: #155724;
        }
        .badge-danger {
            background: #f8d7da;
            color: #721c24;
        }
        """

    def _render_widget(self, widget_id: str, widget_data: Dict[str, Any]) -> str:
        """Render individual widget based on its type."""
        if widget_id == "current_metrics":
            return self._render_metric_cards(widget_data)
        elif widget_id == "quality_trend":
            return self._render_line_chart(widget_id, widget_data)
        elif widget_id == "benchmark_summary":
            return self._render_gauge(widget_data)
        elif widget_id == "benchmark_grid":
            return self._render_benchmark_table(widget_data)
        elif widget_id == "language_heatmap":
            return self._render_heatmap(widget_data)
        else:
            return self._render_generic_widget(widget_id, widget_data)

    def _render_metric_cards(self, data: Dict[str, Any]) -> str:
        """Render metric cards widget."""
        html = ['<div class="widget">']
        html.append("<h3>Current Performance Metrics</h3>")

        if "metrics" in data:
            for metric_name, metric_data in data["metrics"].items():
                if isinstance(metric_data, dict):
                    value = metric_data.get("value", 0)
                    status = metric_data.get("status", "good")
                    trend = metric_data.get("trend", "stable")

                    # Format value
                    if metric_name == "validation_time":
                        formatted_value = f"{value:.2f}s"
                    elif "rate" in metric_name or "score" in metric_name:
                        formatted_value = f"{value:.1%}"
                    else:
                        formatted_value = f"{value:.3f}"

                    html.append('<div class="metric-card">')
                    html.append(
                        f'<div class="metric-label">{metric_name.replace("_", " ").title()}</div>'
                    )
                    html.append(
                        f'<div class="metric-value status-{status}">{formatted_value}</div>'
                    )
                    html.append(f'<div class="trend">Trend: {trend}</div>')
                    html.append("</div>")

        html.append("</div>")
        return "\n".join(html)

    def _render_line_chart(self, widget_id: str, data: Dict[str, Any]) -> str:
        """Render line chart widget."""
        html = ['<div class="widget">']
        html.append("<h3>Quality Trend</h3>")
        html.append('<div class="chart-container">')
        html.append(f'<canvas id="{widget_id}_chart"></canvas>')
        html.append("</div>")

        # Add chart script
        if "data" in data and data["data"]:
            html.append("<script>")
            html.append(
                f"""
            (function() {{
                const ctx = document.getElementById('{widget_id}_chart').getContext('2d');
                const chartData = {json.dumps(data)};

                new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: chartData.data.map(d => d.timestamp),
                        datasets: chartData.series.map(series => ({{
                            label: series.name,
                            data: chartData.data.map(d => d[series.key]),
                            borderColor: series.key === 'quality_score' ? '#3B82F6' :
                                       series.key === 'confidence_score' ? '#10B981' : '#F59E0B',
                            tension: 0.1
                        }}))
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                max: 1
                            }}
                        }}
                    }}
                }});
            }})();
            """
            )
            html.append("</script>")

        html.append("</div>")
        return "\n".join(html)

    def _render_gauge(self, data: Dict[str, Any]) -> str:
        """Render gauge widget for benchmark achievement."""
        html = ['<div class="widget">']
        html.append("<h3>Benchmark Achievement</h3>")

        achievement = data.get("achievement", 0)
        status = data.get("status", "good")

        html.append('<div style="text-align: center;">')
        html.append(
            f'<div class="metric-value status-{status}" style="font-size: 4em;">{achievement:.0f}%</div>'
        )
        html.append('<div class="metric-label">Overall Achievement</div>')

        # Details
        html.append('<div style="margin-top: 20px;">')
        html.append(f"<p>Total Benchmarks: {data.get('total_benchmarks', 0)}</p>")
        html.append(f"<p>Passing: {data.get('passing', 0)}</p>")
        html.append(f"<p>Exceeding Target: {data.get('exceeding', 0)}</p>")
        html.append("</div>")

        html.append("</div>")
        html.append("</div>")
        return "\n".join(html)

    def _render_benchmark_table(self, data: Dict[str, Any]) -> str:
        """Render benchmark status table."""
        html = ['<div class="widget">']
        html.append("<h3>Benchmark Status</h3>")

        if "benchmarks" in data and data["benchmarks"]:
            html.append("<table>")
            html.append("<thead>")
            html.append("<tr>")
            html.append("<th>Benchmark</th>")
            html.append("<th>Value</th>")
            html.append("<th>Level</th>")
            html.append("<th>Target %</th>")
            html.append("<th>Status</th>")
            html.append("</tr>")
            html.append("</thead>")
            html.append("<tbody>")

            for benchmark in data["benchmarks"]:
                status_class = (
                    "badge-success" if benchmark.get("is_passing") else "badge-danger"
                )
                status_text = "PASSING" if benchmark.get("is_passing") else "FAILING"

                html.append("<tr>")
                html.append(
                    f'<td>{benchmark.get("name", "").replace("_", " ").title()}</td>'
                )
                html.append(f'<td>{benchmark.get("value", 0):.3f}</td>')
                html.append(f'<td>{benchmark.get("level", "")}</td>')
                html.append(f'<td>{benchmark.get("target_percentage", 0):.0f}%</td>')
                html.append(
                    f'<td><span class="badge {status_class}">{status_text}</span></td>'
                )
                html.append("</tr>")

            html.append("</tbody>")
            html.append("</table>")

        html.append("</div>")
        return "\n".join(html)

    def _render_heatmap(self, data: Dict[str, Any]) -> str:
        """Render language pair heatmap."""
        html = ['<div class="widget">']
        html.append("<h3>Language Pair Performance</h3>")

        if "data" in data and data["data"]:
            html.append('<div style="text-align: center; padding: 20px;">')
            html.append("<p>Heatmap visualization would be rendered here</p>")
            html.append(
                '<p style="font-size: 0.9em; color: #666;">Average quality scores by language pair</p>'
            )
            html.append("</div>")

        html.append("</div>")
        return "\n".join(html)

    def _render_generic_widget(self, widget_id: str, data: Dict[str, Any]) -> str:
        """Render generic widget for unknown types."""
        html = ['<div class="widget">']
        html.append(f'<h3>{widget_id.replace("_", " ").title()}</h3>')
        html.append('<pre style="overflow: auto; max-height: 300px;">')
        html.append(json.dumps(data, indent=2, default=str))
        html.append("</pre>")
        html.append("</div>")
        return "\n".join(html)

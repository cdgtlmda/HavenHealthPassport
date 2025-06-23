"""Compliance dashboard for real-time certification monitoring.

Security Note: This module processes PHI data. All compliance data must be:
- Encrypted at rest using AES-256 encryption
- Subject to role-based access control (RBAC) for PHI protection
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from aiohttp import web

from ..evidence import EvidenceCollector, EvidencePackage, EvidenceValidator
from .report_config import ReportConfiguration
from .report_generator import CertificationReportGenerator

logger = logging.getLogger(__name__)


class ComplianceDashboard:
    """Web-based compliance dashboard for certification monitoring."""

    def __init__(self, config: ReportConfiguration, project_root: Path):
        """Initialize compliance dashboard.

        Args:
            config: Report configuration
            project_root: Root directory of the project
        """
        self.config = config
        self.project_root = project_root
        self.evidence_collector = EvidenceCollector(project_root)
        self.evidence_validator = EvidenceValidator()
        self.report_generator = CertificationReportGenerator(config, project_root)
        self.app = web.Application()
        self._setup_routes()
        self._cached_data: Dict[str, Any] = {}
        self._last_update = datetime.utcnow()

    def _setup_routes(self) -> None:
        """Set up web application routes."""
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/api/status", self.handle_status)
        self.app.router.add_get("/api/compliance", self.handle_compliance)
        self.app.router.add_get("/api/evidence", self.handle_evidence)
        self.app.router.add_get("/api/requirements", self.handle_requirements)
        self.app.router.add_get("/api/metrics", self.handle_metrics)
        self.app.router.add_get("/api/trends", self.handle_trends)
        self.app.router.add_post("/api/refresh", self.handle_refresh)

        # Only add static route if the directory exists
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            self.app.router.add_static("/static", static_dir)

    async def start(self) -> None:
        """Start the compliance dashboard."""
        if not self.config.dashboard_enabled:
            logger.info("Compliance dashboard is disabled")
            return

        # Initial data refresh
        await self.refresh_data()

        # Start periodic refresh
        asyncio.create_task(self._periodic_refresh())

        # Start web server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", self.config.dashboard_port)
        await site.start()

        logger.info(
            f"Compliance dashboard started on http://localhost:{self.config.dashboard_port}"
        )

    async def _periodic_refresh(self) -> None:
        """Periodically refresh dashboard data."""
        while True:
            await asyncio.sleep(self.config.dashboard_refresh_interval)
            await self.refresh_data()

    async def refresh_data(self) -> None:
        """Refresh cached dashboard data."""
        try:
            logger.debug("Refreshing dashboard data")

            # Collect current evidence
            package = self.evidence_collector.collect_all_evidence()

            # Add requirements for configured standards
            self._add_standard_requirements(package)

            # Validate package
            validation_report = self.evidence_validator.validate_evidence_package(
                package
            )

            # Calculate metrics
            self._cached_data = {
                "last_update": datetime.utcnow().isoformat(),
                "compliance_status": self._calculate_compliance_status(
                    package, validation_report
                ),
                "evidence_summary": self._summarize_evidence(package),
                "requirements_summary": self._summarize_requirements(package),
                "validation_summary": validation_report["summary"],
                "critical_issues": validation_report["critical_issues"],
                "warnings": validation_report["warnings"],
                "metrics": self._calculate_metrics(package, validation_report),
                "trends": self._calculate_trends(),
            }

            self._last_update = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error refreshing dashboard data: {e}")

    # Web request handlers

    async def handle_index(self, request: web.Request) -> web.Response:
        """Handle index page request."""
        html_content = self._generate_dashboard_html()
        return web.Response(text=html_content, content_type="text/html")

    async def handle_status(self, request: web.Request) -> web.Response:
        """Handle status API request."""
        status = {
            "dashboard_version": "1.0.0",
            "last_update": self._last_update.isoformat(),
            "update_interval": self.config.dashboard_refresh_interval,
            "certification_standards": [
                cs.value for cs in self.config.certification_standards
            ],
            "overall_status": self._cached_data.get("compliance_status", {}).get(
                "overall_status", "Unknown"
            ),
        }
        return web.json_response(status)

    async def handle_compliance(self, request: web.Request) -> web.Response:
        """Handle compliance status API request."""
        compliance_data = self._cached_data.get("compliance_status", {})
        return web.json_response(compliance_data)

    async def handle_evidence(self, request: web.Request) -> web.Response:
        """Handle evidence summary API request."""
        evidence_data = self._cached_data.get("evidence_summary", {})
        return web.json_response(evidence_data)

    async def handle_requirements(self, request: web.Request) -> web.Response:
        """Handle requirements summary API request."""
        requirements_data = self._cached_data.get("requirements_summary", {})
        return web.json_response(requirements_data)

    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Handle metrics API request."""
        metrics_data = self._cached_data.get("metrics", {})
        return web.json_response(metrics_data)

    async def handle_trends(self, request: web.Request) -> web.Response:
        """Handle trends API request."""
        trends_data = self._cached_data.get("trends", {})
        return web.json_response(trends_data)

    async def handle_refresh(self, request: web.Request) -> web.Response:
        """Handle manual refresh request."""
        await self.refresh_data()
        return web.json_response(
            {"status": "refreshed", "timestamp": self._last_update.isoformat()}
        )

    # Helper methods

    def _calculate_compliance_status(
        self, package: EvidencePackage, validation_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate overall compliance status."""
        completeness = package.calculate_completeness()

        # Determine status level
        if validation_report["overall_valid"] and completeness == 100:
            status = "Ready"
            color = "green"
        elif completeness >= 80:
            status = "Nearly Ready"
            color = "yellow"
        elif completeness >= 50:
            status = "In Progress"
            color = "orange"
        else:
            status = "Early Stage"
            color = "red"

        return {
            "overall_status": status,
            "status_color": color,
            "completeness_percentage": completeness,
            "is_valid": validation_report["overall_valid"],
            "standards_status": self._calculate_standards_status(package),
            "blocking_issues_count": len(validation_report["critical_issues"]),
            "warnings_count": len(validation_report["warnings"]),
        }

    def _calculate_standards_status(self, package: EvidencePackage) -> Dict[str, Any]:
        """Calculate status for each certification standard."""
        standards_status = {}

        for standard in self.config.certification_standards:
            requirements = package.get_requirements_by_standard(standard)
            if requirements:
                satisfied = sum(1 for r in requirements if r.satisfied)
                total = len(requirements)
                percentage = (satisfied / total * 100) if total > 0 else 0

                standards_status[standard.value] = {
                    "total_requirements": total,
                    "satisfied_requirements": satisfied,
                    "percentage_complete": percentage,
                    "status": "Complete" if percentage == 100 else "In Progress",
                }

        return standards_status

    def _summarize_evidence(self, package: EvidencePackage) -> Dict[str, Any]:
        """Summarize evidence collection."""
        evidence_by_type: Dict[str, int] = {}
        recent_evidence = []

        for evidence in package.evidence_items.values():
            # Count by type
            type_key = evidence.type.value
            evidence_by_type[type_key] = evidence_by_type.get(type_key, 0) + 1

            # Track recent evidence
            if (datetime.utcnow() - evidence.created_at).days <= 7:
                recent_evidence.append(
                    {
                        "id": evidence.id,
                        "type": evidence.type.value,
                        "title": evidence.title,
                        "created_at": evidence.created_at.isoformat(),
                    }
                )

        return {
            "total_evidence_items": len(package.evidence_items),
            "evidence_by_type": evidence_by_type,
            "recent_evidence": sorted(
                recent_evidence, key=lambda x: x["created_at"], reverse=True
            )[:10],
            "evidence_with_files": sum(
                1 for e in package.evidence_items.values() if e.file_path
            ),
        }

    def _summarize_requirements(self, package: EvidencePackage) -> Dict[str, Any]:
        """Summarize requirements status."""
        return {
            "total_requirements": len(package.requirements),
            "satisfied_requirements": sum(
                1 for r in package.requirements.values() if r.satisfied
            ),
            "mandatory_unsatisfied": sum(
                1
                for r in package.requirements.values()
                if r.mandatory and not r.satisfied
            ),
            "optional_unsatisfied": sum(
                1
                for r in package.requirements.values()
                if not r.mandatory and not r.satisfied
            ),
            "requirements_by_standard": {
                standard.value: len(package.get_requirements_by_standard(standard))
                for standard in self.config.certification_standards
            },
        }

    def _calculate_metrics(
        self, package: EvidencePackage, validation_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate dashboard metrics."""
        return {
            "evidence_growth_rate": self._calculate_evidence_growth_rate(package),
            "validation_pass_rate": self._calculate_validation_pass_rate(
                validation_report
            ),
            "requirement_satisfaction_rate": self._calculate_requirement_satisfaction_rate(
                package
            ),
            "average_evidence_age_days": self._calculate_average_evidence_age(package),
            "compliance_score": self._calculate_compliance_score(
                package, validation_report
            ),
        }

    def _calculate_evidence_growth_rate(self, package: EvidencePackage) -> float:
        """Calculate evidence collection growth rate."""
        # Count evidence created in last 30 days
        recent_count = sum(
            1
            for e in package.evidence_items.values()
            if (datetime.utcnow() - e.created_at).days <= 30
        )

        # Simple growth rate calculation
        if len(package.evidence_items) > 0:
            return (recent_count / len(package.evidence_items)) * 100
        return 0.0

    def _calculate_validation_pass_rate(
        self, validation_report: Dict[str, Any]
    ) -> float:
        """Calculate validation pass rate."""
        summary = validation_report.get("summary", {})
        total = summary.get("total_evidence_items", 0)
        valid = summary.get("valid_evidence_items", 0)

        if total > 0:
            return float((valid / total) * 100)
        return 100.0

    def _calculate_requirement_satisfaction_rate(
        self, package: EvidencePackage
    ) -> float:
        """Calculate requirement satisfaction rate."""
        if not package.requirements:
            return 100.0

        satisfied = sum(1 for r in package.requirements.values() if r.satisfied)
        return (satisfied / len(package.requirements)) * 100

    def _calculate_average_evidence_age(self, package: EvidencePackage) -> float:
        """Calculate average age of evidence in days."""
        if not package.evidence_items:
            return 0.0

        total_age = sum(
            (datetime.utcnow() - e.created_at).days
            for e in package.evidence_items.values()
        )

        return total_age / len(package.evidence_items)

    def _calculate_compliance_score(
        self, package: EvidencePackage, validation_report: Dict[str, Any]
    ) -> float:
        """Calculate overall compliance score (0-100)."""
        # Weighted scoring
        completeness_weight = 0.4
        validation_weight = 0.3
        requirements_weight = 0.3

        completeness_score = package.calculate_completeness()
        validation_score = self._calculate_validation_pass_rate(validation_report)
        requirements_score = self._calculate_requirement_satisfaction_rate(package)

        return (
            completeness_score * completeness_weight
            + validation_score * validation_weight
            + requirements_score * requirements_weight
        )

    def _calculate_trends(self) -> Dict[str, Any]:
        """Calculate trend data for visualization."""
        # In a real implementation, this would query historical data
        return {
            "compliance_trend": [
                {"date": "2024-01-01", "score": 45},
                {"date": "2024-02-01", "score": 58},
                {"date": "2024-03-01", "score": 72},
                {"date": "2024-04-01", "score": 85},
            ],
            "evidence_trend": [
                {"date": "2024-01-01", "count": 25},
                {"date": "2024-02-01", "count": 45},
                {"date": "2024-03-01", "count": 78},
                {"date": "2024-04-01", "count": 95},
            ],
        }

    def _add_standard_requirements(self, package: EvidencePackage) -> None:
        """Add requirements for configured standards."""
        # This would typically load from a requirements database
        # For now, using a placeholder
        pass

    def _generate_dashboard_html(self) -> str:
        """Generate dashboard HTML."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Haven Health Passport - Compliance Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #f5f7fa;
            color: #333;
        }

        .header {
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .header h1 {
            font-size: 24px;
            font-weight: 500;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .metric-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }

        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }

        .metric-value {
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }

        .metric-label {
            color: #7f8c8d;
            font-size: 14px;
        }

        .status-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
        }

        .status-green { background-color: #27ae60; color: white; }
        .status-yellow { background-color: #f39c12; color: white; }
        .status-orange { background-color: #e67e22; color: white; }
        .status-red { background-color: #e74c3c; color: white; }

        .dashboard-section {
            background: white;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .section-title {
            font-size: 20px;
            margin-bottom: 20px;
            color: #2c3e50;
        }

        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #ecf0f1;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }

        .progress-fill {
            height: 100%;
            background-color: #3498db;
            transition: width 0.3s ease;
        }

        .progress-text {
            position: absolute;
            width: 100%;
            text-align: center;
            line-height: 20px;
            font-size: 12px;
            font-weight: 500;
        }

        .standards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .standard-card {
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 15px;
        }

        .refresh-button {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.2s;
        }

        .refresh-button:hover {
            background-color: #2980b9;
        }

        .chart-container {
            height: 300px;
            margin-top: 20px;
        }

        .issues-list {
            list-style: none;
            margin-top: 10px;
        }

        .issues-list li {
            padding: 8px;
            margin-bottom: 5px;
            background-color: #fee;
            border-left: 4px solid #e74c3c;
            border-radius: 3px;
        }

        .last-update {
            color: #7f8c8d;
            font-size: 12px;
            margin-top: 10px;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>Haven Health Passport - Compliance Dashboard</h1>
        </div>
    </div>

    <div class="container">
        <!-- Metrics Grid -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Overall Status</div>
                <div id="overall-status" class="metric-value">
                    <span class="status-badge">Loading...</span>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Compliance Score</div>
                <div id="compliance-score" class="metric-value">--</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Evidence Items</div>
                <div id="evidence-count" class="metric-value">--</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Requirements Met</div>
                <div id="requirements-met" class="metric-value">--</div>
            </div>
        </div>

        <!-- Compliance Progress -->
        <div class="dashboard-section">
            <h2 class="section-title">Compliance Progress</h2>
            <div class="progress-bar">
                <div id="progress-fill" class="progress-fill" style="width: 0%"></div>
                <div id="progress-text" class="progress-text">0%</div>
            </div>
            <div class="last-update">Last updated: <span id="last-update">Never</span></div>
            <button class="refresh-button" onclick="refreshDashboard()">Refresh Now</button>
        </div>

        <!-- Standards Status -->
        <div class="dashboard-section">
            <h2 class="section-title">Certification Standards</h2>
            <div id="standards-grid" class="standards-grid">
                <!-- Standards will be populated here -->
            </div>
        </div>

        <!-- Trends Chart -->
        <div class="dashboard-section">
            <h2 class="section-title">Compliance Trends</h2>
            <div class="chart-container">
                <canvas id="trends-chart"></canvas>
            </div>
        </div>

        <!-- Critical Issues -->
        <div class="dashboard-section">
            <h2 class="section-title">Critical Issues</h2>
            <ul id="issues-list" class="issues-list">
                <!-- Issues will be populated here -->
            </ul>
        </div>
    </div>

    <script>
        let trendsChart = null;

        async function fetchData(endpoint) {
            try {
                const response = await fetch(`/api/${endpoint}`);
                return await response.json();
            } catch (error) {
                console.error(`Error fetching ${endpoint}:`, error);
                return null;
            }
        }

        async function updateDashboard() {
            // Fetch all data
            const [status, compliance, metrics, trends] = await Promise.all([
                fetchData('status'),
                fetchData('compliance'),
                fetchData('metrics'),
                fetchData('trends')
            ]);

            // Update overall status
            if (status) {
                const statusBadge = document.getElementById('overall-status');
                const statusClass = `status-${compliance?.status_color || 'red'}`;
                statusBadge.innerHTML = `<span class="status-badge ${statusClass}">${status.overall_status}</span>`;

                document.getElementById('last-update').textContent = new Date(status.last_update).toLocaleString();
            }

            // Update metrics
            if (metrics) {
                document.getElementById('compliance-score').textContent =
                    Math.round(metrics.compliance_score || 0) + '%';
            }

            if (compliance) {
                // Update progress bar
                const progress = compliance.completeness_percentage || 0;
                document.getElementById('progress-fill').style.width = progress + '%';
                document.getElementById('progress-text').textContent = Math.round(progress) + '%';

                // Update evidence count
                document.getElementById('evidence-count').textContent =
                    compliance.evidence_summary?.total_evidence_items || '0';

                // Update requirements
                const reqSummary = compliance.requirements_summary;
                if (reqSummary) {
                    const percentage = (reqSummary.satisfied_requirements / reqSummary.total_requirements * 100) || 0;
                    document.getElementById('requirements-met').textContent =
                        Math.round(percentage) + '%';
                }

                // Update standards grid
                updateStandardsGrid(compliance.standards_status);

                // Update issues list
                updateIssuesList(compliance);
            }

            // Update trends chart
            if (trends) {
                updateTrendsChart(trends);
            }
        }

        function updateStandardsGrid(standardsStatus) {
            const grid = document.getElementById('standards-grid');
            grid.innerHTML = '';

            for (const [standard, status] of Object.entries(standardsStatus || {})) {
                const card = document.createElement('div');
                card.className = 'standard-card';
                card.innerHTML = `
                    <h3>${standard}</h3>
                    <div class="progress-bar" style="margin: 10px 0;">
                        <div class="progress-fill" style="width: ${status.percentage_complete}%"></div>
                        <div class="progress-text">${Math.round(status.percentage_complete)}%</div>
                    </div>
                    <p style="font-size: 14px; color: #666;">
                        ${status.satisfied_requirements} of ${status.total_requirements} requirements met
                    </p>
                `;
                grid.appendChild(card);
            }
        }

        function updateIssuesList(compliance) {
            const list = document.getElementById('issues-list');
            list.innerHTML = '';

            const issues = compliance.critical_issues || [];
            if (issues.length === 0) {
                list.innerHTML = '<li style="background: #e8f5e9; border-color: #4caf50;">No critical issues found</li>';
            } else {
                issues.slice(0, 5).forEach(issue => {
                    const li = document.createElement('li');
                    li.textContent = issue.message || 'Unknown issue';
                    list.appendChild(li);
                });
            }
        }

        function updateTrendsChart(trends) {
            const ctx = document.getElementById('trends-chart').getContext('2d');

            if (trendsChart) {
                trendsChart.destroy();
            }

            trendsChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: trends.compliance_trend?.map(d => d.date) || [],
                    datasets: [{
                        label: 'Compliance Score',
                        data: trends.compliance_trend?.map(d => d.score) || [],
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });
        }

        async function refreshDashboard() {
            await fetch('/api/refresh', { method: 'POST' });
            await updateDashboard();
        }

        // Initial load
        updateDashboard();

        // Auto-refresh every 30 seconds
        setInterval(updateDashboard, 30000);
    </script>
</body>
</html>
        """

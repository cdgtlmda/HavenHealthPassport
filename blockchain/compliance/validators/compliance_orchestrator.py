#!/usr/bin/env python3
"""
Comprehensive Compliance Orchestrator
Runs all compliance validators and generates overall compliance status
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import validators
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from gdpr_validator import GDPRValidator
from hipaa_validator import HIPAAValidator


class ComplianceOrchestrator:
    """Orchestrates all compliance validations"""

    def __init__(self, network_id: str, member_id: str):
        self.network_id = network_id
        self.member_id = member_id
        self.validation_timestamp = datetime.now()
        self.compliance_reports = {}

    def run_hipaa_validation(self) -> Dict:
        """Run HIPAA compliance validation"""
        logger.info("Running HIPAA compliance validation...")
        validator = HIPAAValidator(self.network_id, self.member_id)
        validator.run_all_checks()
        report = validator.generate_report()
        self.compliance_reports["HIPAA"] = report
        return report

    def run_gdpr_validation(self) -> Dict:
        """Run GDPR compliance validation"""
        logger.info("Running GDPR compliance validation...")
        validator = GDPRValidator(self.network_id, self.member_id)
        validator.run_all_checks()
        report = validator.generate_report()
        self.compliance_reports["GDPR"] = report
        return report

    def run_all_validations(self) -> Dict:
        """Run all compliance validations"""
        logger.info("Starting comprehensive compliance validation...")

        # Run all validators
        validations = [
            ("HIPAA", self.run_hipaa_validation),
            ("GDPR", self.run_gdpr_validation),
            # Additional validators would be added here:
            # ('ISO27001', self.run_iso27001_validation),
            # ('FHIR', self.run_fhir_validation),
            # ('UNHCR', self.run_unhcr_validation),
            # ('WCAG', self.run_wcag_validation)
        ]

        results = {}
        for standard, validator_func in validations:
            try:
                results[standard] = validator_func()
            except Exception as e:
                logger.error(f"Error running {standard} validation: {str(e)}")
                results[standard] = {
                    "standard": standard,
                    "error": str(e),
                    "overall_compliance": False,
                }

        return results

    def generate_overall_report(self) -> Dict:
        """Generate comprehensive compliance report"""
        all_compliant = all(
            report.get("overall_compliance", False)
            for report in self.compliance_reports.values()
        )

        total_checks = sum(
            report.get("summary", {}).get("total_checks", 0)
            for report in self.compliance_reports.values()
        )

        compliant_checks = sum(
            report.get("summary", {}).get("compliant", 0)
            for report in self.compliance_reports.values()
        )
        return {
            "validation_timestamp": self.validation_timestamp.isoformat(),
            "network_id": self.network_id,
            "member_id": self.member_id,
            "overall_compliance": all_compliant,
            "compliance_percentage": (
                (compliant_checks / total_checks * 100) if total_checks > 0 else 0
            ),
            "summary": {
                "standards_evaluated": len(self.compliance_reports),
                "standards_compliant": sum(
                    1
                    for r in self.compliance_reports.values()
                    if r.get("overall_compliance", False)
                ),
                "total_checks": total_checks,
                "compliant_checks": compliant_checks,
            },
            "standards": self.compliance_reports,
            "critical_findings": self._get_critical_findings(),
            "recommendations": self._get_recommendations(),
        }

    def _get_critical_findings(self) -> List[Dict]:
        """Extract critical findings from all reports"""
        findings = []
        for standard, report in self.compliance_reports.items():
            for check in report.get("checks", []):
                if (
                    check.get("severity") == "HIGH"
                    and check.get("status") != "COMPLIANT"
                ):
                    findings.append(
                        {
                            "standard": standard,
                            "check_id": check.get("check_id"),
                            "description": check.get("description"),
                            "remediation": check.get("remediation"),
                        }
                    )
        return findings

    def _get_recommendations(self) -> List[str]:
        """Generate prioritized recommendations"""
        recommendations = []

        if not self.compliance_reports.get("HIPAA", {}).get("overall_compliance"):
            recommendations.append(
                "Priority 1: Address HIPAA compliance gaps immediately"
            )

        if not self.compliance_reports.get("GDPR", {}).get("overall_compliance"):
            recommendations.append("Priority 2: Implement GDPR data subject rights")

        if recommendations:
            recommendations.append("Schedule quarterly compliance reviews")
        else:
            recommendations.append("Maintain compliance with monthly reviews")

        return recommendations


def main():
    """Main execution function"""
    # Check environment variables
    network_id = os.getenv("AMB_NETWORK_ID")
    member_id = os.getenv("AMB_MEMBER_ID")

    if not network_id or not member_id:
        logger.error("AMB_NETWORK_ID and AMB_MEMBER_ID must be set")
        sys.exit(1)

    # Create orchestrator
    orchestrator = ComplianceOrchestrator(network_id, member_id)

    # Run all validations
    orchestrator.run_all_validations()

    # Generate overall report
    report = orchestrator.generate_overall_report()

    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"../reports/blockchain_compliance_report_{timestamp}.json"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)

    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("Blockchain Compliance Validation Summary")
    print("=" * 60)
    print(f"Overall Compliance: {'PASS' if report['overall_compliance'] else 'FAIL'}")
    print(f"Compliance Percentage: {report['compliance_percentage']:.1f}%")
    print(f"\nStandards Evaluated: {report['summary']['standards_evaluated']}")
    print(f"Standards Compliant: {report['summary']['standards_compliant']}")

    if report["critical_findings"]:
        print(f"\nCritical Findings: {len(report['critical_findings'])}")
        for finding in report["critical_findings"][:3]:  # Show top 3
            print(f"  - [{finding['standard']}] {finding['description']}")

    print("\nRecommendations:")
    for rec in report["recommendations"]:
        print(f"  • {rec}")

    print(f"\nDetailed report saved to: {report_file}")

    # Exit with appropriate code
    sys.exit(0 if report["overall_compliance"] else 1)


if __name__ == "__main__":
    main()

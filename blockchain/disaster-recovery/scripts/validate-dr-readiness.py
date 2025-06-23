#!/usr/bin/env python3
"""
Automated Disaster Recovery Validation
Performs regular validation of DR capabilities without disrupting production
"""

import json
import logging
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional, Tuple

import boto3

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DRValidator:
    """Validates disaster recovery readiness"""

    def __init__(self):
        self.network_id = os.getenv("AMB_NETWORK_ID")
        self.member_id = os.getenv("AMB_MEMBER_ID")
        self.amb_client = boto3.client("managedblockchain")
        self.s3_client = boto3.client("s3")
        self.cloudwatch = boto3.client("cloudwatch")
        self.validation_results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "PENDING",
        }

    def validate_backup_freshness(self) -> Tuple[bool, str]:
        """Check if backups are recent enough"""
        try:
            # Check S3 backup bucket
            bucket_name = "haven-health-dr-backups"
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name, Prefix=f"blockchain/{self.network_id}/", MaxKeys=1
            )
            if "Contents" in response and response["Contents"]:
                latest_backup = response["Contents"][0]
                backup_time = latest_backup["LastModified"]
                age_hours = (
                    datetime.now(backup_time.tzinfo) - backup_time
                ).total_seconds() / 3600

                if age_hours <= 24:
                    return True, f"Latest backup is {age_hours:.1f} hours old"
                else:
                    return False, f"Latest backup is {age_hours:.1f} hours old (>24h)"
            else:
                return False, "No backups found"

        except Exception as e:
            return False, f"Backup validation error: {str(e)}"

    def validate_node_health(self) -> Tuple[bool, str]:
        """Check health of all blockchain nodes"""
        try:
            response = self.amb_client.list_nodes(
                NetworkId=self.network_id, MemberId=self.member_id
            )

            nodes = response.get("Nodes", [])
            if not nodes:
                return False, "No nodes found"

            unhealthy_nodes = [n for n in nodes if n["Status"] != "AVAILABLE"]

            if unhealthy_nodes:
                return False, f"{len(unhealthy_nodes)} unhealthy nodes found"
            else:
                return True, f"All {len(nodes)} nodes are healthy"

        except Exception as e:
            return False, f"Node health check error: {str(e)}"

    def validate_monitoring_alerts(self) -> Tuple[bool, str]:
        """Check if monitoring and alerting is configured"""
        try:
            # Check for critical alarms
            response = self.cloudwatch.describe_alarms(AlarmNamePrefix="blockchain-dr-")
            alarms = response.get("MetricAlarms", [])
            required_alarms = [
                "blockchain-dr-node-failure",
                "blockchain-dr-network-partition",
                "blockchain-dr-backup-failure",
            ]

            configured_alarms = [a["AlarmName"] for a in alarms]
            missing_alarms = [a for a in required_alarms if a not in configured_alarms]

            if missing_alarms:
                return False, f"Missing alarms: {', '.join(missing_alarms)}"
            else:
                return True, f"{len(alarms)} DR alarms configured"

        except Exception as e:
            return False, f"Monitoring validation error: {str(e)}"

    def validate_recovery_scripts(self) -> Tuple[bool, str]:
        """Check if recovery scripts exist and are executable"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            required_scripts = ["run-dr-node-001.sh", "run-all-dr-tests.sh"]

            missing_scripts = []
            for script in required_scripts:
                script_path = os.path.join(script_dir, script)
                if not os.path.exists(script_path):
                    missing_scripts.append(script)
                elif not os.access(script_path, os.X_OK):
                    missing_scripts.append(f"{script} (not executable)")

            if missing_scripts:
                return False, f"Missing scripts: {', '.join(missing_scripts)}"
            else:
                return True, "All recovery scripts present and executable"

        except Exception as e:
            return False, f"Script validation error: {str(e)}"

    def run_validations(self) -> Dict:
        """Run all DR validation checks"""
        logger.info("Starting DR readiness validation...")

        # Run all validation checks
        checks = [
            ("backup_freshness", self.validate_backup_freshness),
            ("node_health", self.validate_node_health),
            ("monitoring_alerts", self.validate_monitoring_alerts),
            ("recovery_scripts", self.validate_recovery_scripts),
        ]

        all_passed = True

        for check_name, check_func in checks:
            logger.info(f"Running {check_name} validation...")
            passed, message = check_func()
            self.validation_results["checks"][check_name] = {
                "passed": passed,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }
            if not passed:
                all_passed = False
                logger.error(f"{check_name}: FAILED - {message}")
            else:
                logger.info(f"{check_name}: PASSED - {message}")

        self.validation_results["overall_status"] = (
            "READY" if all_passed else "NOT_READY"
        )
        return self.validation_results

    def send_alert(self, results: Dict):
        """Send email alert if validation fails"""
        if results["overall_status"] == "READY":
            return

        # In production, configure with actual SMTP settings
        logger.warning("DR validation failed - alert would be sent in production")

    def save_results(self, results: Dict):
        """Save validation results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dr_validation_{timestamp}.json"

        with open(filename, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Validation results saved to {filename}")


def main():
    """Main execution function"""
    # Check environment variables
    if not os.getenv("AMB_NETWORK_ID") or not os.getenv("AMB_MEMBER_ID"):
        logger.error("AMB_NETWORK_ID and AMB_MEMBER_ID must be set")
        sys.exit(1)

    # Create validator instance
    validator = DRValidator()

    # Run validations
    results = validator.run_validations()

    # Save results
    validator.save_results(results)

    # Send alert if needed
    validator.send_alert(results)

    # Print summary
    print("\n" + "=" * 50)
    print("DR Readiness Validation Summary")
    print("=" * 50)
    print(f"Overall Status: {results['overall_status']}")
    print("\nCheck Results:")
    for check_name, check_result in results["checks"].items():
        status = "PASSED" if check_result["passed"] else "FAILED"
        print(f"  {check_name}: {status}")
        print(f"    → {check_result['message']}")

    # Exit with appropriate code
    exit_code = 0 if results["overall_status"] == "READY" else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

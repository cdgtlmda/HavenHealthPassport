"""Initialize all AWS services and database infrastructure for Haven Health Passport."""

import sys
from typing import Any, Dict

from src.infrastructure.database_setup import db_infrastructure
from src.integration.aws_services import aws_services
from src.utils.logging import get_logger

logger = get_logger(__name__)


def initialize_infrastructure() -> Dict[str, Any]:
    """Initialize complete infrastructure for Haven Health Passport."""
    logger.info("Starting Haven Health Passport infrastructure initialization...")

    infra_results: Dict[str, Any] = {
        "aws_services": {},
        "database_infrastructure": {},
        "summary": {},
    }

    try:
        # Initialize AWS services
        logger.info("Initializing AWS services...")
        aws_results = aws_services.initialize_all_services()
        infra_results["aws_services"] = aws_results

        # Initialize database infrastructure
        logger.info("Initializing database infrastructure...")
        db_results = db_infrastructure.initialize_complete_infrastructure()
        infra_results["database_infrastructure"] = db_results

        # Calculate summary
        aws_success = sum(1 for v in aws_results.values() if v)
        aws_total = len(aws_results)

        db_success = sum(
            1
            for k, v in db_results.items()
            if (
                k.endswith("_setup")
                or k.endswith("_created")
                or k
                in [
                    "automated_backups",
                    "point_in_time_recovery",
                    "ssl_tls",
                    "monitoring_alerts",
                ]
            )
            and v
        )
        db_total = 7

        total_success = aws_success + db_success
        total_items = aws_total + db_total

        infra_results["summary"] = {
            "aws_services": f"{aws_success}/{aws_total}",
            "database_infrastructure": f"{db_success}/{db_total}",
            "overall": f"{total_success}/{total_items}",
            "success_rate": f"{(total_success/total_items)*100:.1f}%",
        }

        # Print summary
        print("\n" + "=" * 60)
        print("INFRASTRUCTURE INITIALIZATION SUMMARY")
        print("=" * 60)
        print(f"AWS Services: {infra_results['summary']['aws_services']}")
        print(
            f"Database Infrastructure: {infra_results['summary']['database_infrastructure']}"
        )
        print(
            f"Overall: {infra_results['summary']['overall']} ({infra_results['summary']['success_rate']})"
        )
        print("=" * 60)

        # Print details if there were failures
        if total_success < total_items:
            print("\nFAILED COMPONENTS:")

            # AWS service failures
            for service, success in aws_results.items():
                if not success:
                    print(f"  - AWS: {service}")

            # Database infrastructure failures
            for component, success in db_results.items():
                if component.endswith("_setup") or component.endswith("_created"):
                    if not success:
                        print(f"  - Database: {component}")

        print("\nInfrastructure initialization complete!")

    except Exception as e:
        logger.error("Infrastructure initialization failed", exc_info=True)
        infra_results["error"] = {
            "message": "Initialization failed",
            "exception": str(e),
        }
        raise

    return infra_results


if __name__ == "__main__":
    try:
        results = initialize_infrastructure()

        # Exit with appropriate code
        if (
            results["summary"]["overall"].split("/")[0]
            == results["summary"]["overall"].split("/")[1]
        ):
            sys.exit(0)  # All successful
        else:
            sys.exit(1)  # Some failures

    except (ValueError, OSError, KeyError) as e:
        logger.error("Fatal error during initialization: %s", str(e), exc_info=True)
        sys.exit(2)

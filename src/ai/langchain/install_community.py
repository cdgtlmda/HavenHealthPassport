#!/usr/bin/env python3
"""
Install LangChain Community packages for Haven Health Passport.

This script manages the installation of community integrations with proper error handling.
"""

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CommunityPackageInstaller:
    """Manages installation of LangChain community packages."""

    def __init__(self) -> None:
        """Initialize the community package installer."""
        self.script_dir = Path(__file__).parent
        self.requirements_file = self.script_dir / "requirements-community.txt"
        self.log_file = (
            self.script_dir
            / f"community_install_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        self.failed_packages: List[str] = []
        self.optional_packages = [
            "biopython",
            "SimpleITK",
            "radiomics",
            "clinicalbert",  # May require special installation
            "biobert-embeddings",  # May require special installation
        ]

    def check_python_version(self) -> bool:
        """Ensure Python 3.11+ is being used."""
        version = sys.version_info
        if version.major == 3 and version.minor >= 11:
            logger.info(
                "Python version %s.%s.%s detected ✓",
                version.major,
                version.minor,
                version.micro,
            )
            return True
        else:
            logger.error(
                "Python 3.11+ required, found %s.%s.%s",
                version.major,
                version.minor,
                version.micro,
            )
            return False

    def create_virtual_env(self) -> bool:
        """Ensure we're in a virtual environment."""
        if sys.prefix == sys.base_prefix:
            logger.warning("Not in a virtual environment. Creating one...")
            try:
                subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
                logger.info(
                    "Virtual environment created. Please activate it and run this script again."
                )
                return False
            except subprocess.CalledProcessError as e:
                logger.error("Failed to create virtual environment: %s", e)
                return False
        logger.info("Virtual environment detected ✓")
        return True

    def upgrade_pip(self) -> bool:
        """Upgrade pip to latest version."""
        logger.info("Upgrading pip...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("pip upgraded successfully ✓")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Failed to upgrade pip: %s", e)
            return False

    def install_package_group(self, packages: List[str], group_name: str) -> List[str]:
        """Install a group of packages with error handling."""
        logger.info("Installing %s packages...", group_name)
        failed = []

        for package in packages:
            package_name = package.split(">=")[0].split("==")[0].strip()

            # Skip optional packages that might fail
            if any(opt in package_name for opt in self.optional_packages):
                logger.info("Skipping optional package: %s", package_name)
                continue
            try:
                logger.info("  Installing %s...", package_name)
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout per package
                    check=False,  # We handle return codes manually
                )

                if result.returncode == 0:
                    logger.info("  ✓ %s installed successfully", package_name)
                else:
                    logger.error("  ✗ %s failed: %s", package_name, result.stderr)
                    failed.append(package_name)

            except subprocess.TimeoutExpired:
                logger.error("  ✗ %s installation timed out", package_name)
                failed.append(package_name)
            except (subprocess.CalledProcessError, OSError, ValueError) as e:
                logger.error("  ✗ %s failed with error: %s", package_name, e)
                failed.append(package_name)

        return failed

    def read_requirements(self) -> dict:
        """Read and categorize requirements."""
        if not self.requirements_file.exists():
            logger.error("Requirements file not found: %s", self.requirements_file)
            return {}

        categories: dict = {
            "core": [],
            "vector_stores": [],
            "document_loaders": [],
            "medical": [],
            "embeddings": [],
            "language": [],
            "text_processing": [],
            "audio": [],
            "image": [],
            "database": [],
            "api": [],
            "monitoring": [],
            "performance": [],
            "medical_nlp": [],
            "data_validation": [],
            "testing": [],
            "async": [],
            "security": [],
            "dev_tools": [],
        }
        current_category = "core"

        with open(self.requirements_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    if "Vector Store" in line:
                        current_category = "vector_stores"
                    elif "Document Loader" in line:
                        current_category = "document_loaders"
                    elif "Medical-specific" in line:
                        current_category = "medical"
                    elif "Embedding Model" in line:
                        current_category = "embeddings"
                    elif "Language Detection" in line:
                        current_category = "language"
                    elif "Text Processing" in line:
                        current_category = "text_processing"
                    elif "Audio Processing" in line:
                        current_category = "audio"
                    elif "Image Processing" in line:
                        current_category = "image"
                    elif "Database Connector" in line:
                        current_category = "database"
                    elif "API Integration" in line:
                        current_category = "api"
                    elif "Monitoring" in line:
                        current_category = "monitoring"
                    elif "Caching and Performance" in line:
                        current_category = "performance"
                    elif "Medical NLP" in line:
                        current_category = "medical_nlp"
                    elif "Data Validation" in line:
                        current_category = "data_validation"
                    elif "Testing" in line:
                        current_category = "testing"
                    elif "Async Support" in line:
                        current_category = "async"
                    elif "Security" in line:
                        current_category = "security"
                    elif "Development Tool" in line:
                        current_category = "dev_tools"
                    continue

                if current_category in categories:
                    categories[current_category].append(line)

        return categories

    def install_all(self) -> bool:
        """Install all community packages by category."""
        if not self.check_python_version():
            return False

        if not self.create_virtual_env():
            return False

        if not self.upgrade_pip():
            return False

        categories = self.read_requirements()
        if not categories:
            return False

        # Install in dependency order
        install_order = [
            ("core", "Core"),
            ("data_validation", "Data Validation"),  # Required by many packages
            ("security", "Security"),  # Base security packages
            ("vector_stores", "Vector Store"),
            ("document_loaders", "Document Loader"),
            ("embeddings", "Embedding Model"),
            ("text_processing", "Text Processing"),
            ("language", "Language Detection"),
            ("medical", "Medical Integration"),
            ("medical_nlp", "Medical NLP"),
            ("audio", "Audio Processing"),
            ("image", "Image Processing"),
            ("database", "Database Connector"),
            ("api", "API Integration"),
            ("async", "Async Support"),
            ("performance", "Performance"),
            ("monitoring", "Monitoring"),
            ("dev_tools", "Development Tool"),
            ("testing", "Testing"),
        ]

        all_failed = []

        for category_key, category_name in install_order:
            if category_key in categories and categories[category_key]:
                failed = self.install_package_group(
                    categories[category_key], category_name
                )
                all_failed.extend(failed)
        # Log summary
        logger.info("%s", "\n" + "=" * 60)
        logger.info("INSTALLATION SUMMARY")
        logger.info("%s", "=" * 60)

        if all_failed:
            logger.warning("Failed packages (%s):", len(all_failed))
            for pkg in all_failed:
                logger.warning("  - %s", pkg)
            logger.info("\nTo retry failed packages individually:")
            logger.info("  pip install <package_name>")
        else:
            logger.info("All packages installed successfully! ✓")

        # Save log
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(f"Installation completed at {datetime.now()}\n")
            f.write(f"Failed packages: {all_failed}\n")

        logger.info("\nInstallation log saved to: %s", self.log_file)

        return len(all_failed) == 0


def main() -> None:
    """Execute main entry point."""
    installer = CommunityPackageInstaller()

    print("\n" + "=" * 60)
    print("Haven Health Passport - LangChain Community Package Installer")
    print("=" * 60 + "\n")

    success = installer.install_all()

    if success:
        print("\n✅ Installation completed successfully!")
        print("\nNext steps:")
        print("1. Run verify_community_installation.py to test the installation")
        print("2. Configure memory systems (next item in checklist)")
    else:
        print("\n⚠️  Some packages failed to install.")
        print("Check the log file for details and retry failed packages manually.")
        sys.exit(1)


if __name__ == "__main__":
    main()

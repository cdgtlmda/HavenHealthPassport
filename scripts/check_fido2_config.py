#!/usr/bin/env python3
"""FIDO2 Configuration Check Script.

This script verifies FIDO2 configuration and setup for Haven Health Passport.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.fido2_settings import get_fido2_settings
from src.config.webauthn_settings import get_webauthn_settings


def check_fido2_configuration():
    """Check and display FIDO2 configuration."""
    print("=" * 60)
    print("FIDO2 Configuration Check")
    print("=" * 60)

    # Load settings
    try:
        fido2_settings = get_fido2_settings()
        print("✓ FIDO2 settings loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load FIDO2 settings: {e}")
        return False

    # Display configuration
    print("\nWebAuthn Base Configuration:")
    print(f"  RP Name: {fido2_settings.rp_name}")
    print(f"  RP ID: {fido2_settings.rp_id}")
    print(f"  Origins: {', '.join(fido2_settings.rp_origins)}")

    print("\nFIDO2 Requirements:")
    print(
        f"  Min Certification Level: {fido2_settings.fido2_requirements.min_aaguid_certification_level}"
    )
    print(
        f"  Require User Verification: {fido2_settings.fido2_requirements.require_user_verification}"
    )
    print(
        f"  Require Resident Key: {fido2_settings.fido2_requirements.require_resident_key_capable}"
    )
    print(
        f"  Allowed Transports: {', '.join(fido2_settings.fido2_requirements.allowed_transports)}"
    )

    print("\nSecurity Settings:")
    print(f"  Attestation: {fido2_settings.fido2_attestation_preference}")
    print(f"  Enterprise Attestation: {fido2_settings.support_enterprise_attestation}")
    print(f"  Use MDS: {fido2_settings.use_mds}")
    print(f"  Require PIN: {fido2_settings.require_pin}")
    print(f"  Min PIN Length: {fido2_settings.min_pin_length}")

    print("\nKey Lifecycle:")
    print(f"  Max Key Age: {fido2_settings.max_key_age_days} days")
    print(f"  Require Rotation: {fido2_settings.require_key_rotation}")

    # Check environment
    print("\nEnvironment Check:")
    required_vars = ["WEBAUTHN_RP_NAME", "WEBAUTHN_RP_ID", "WEBAUTHN_RP_ORIGINS"]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"  ⚠ Missing environment variables: {', '.join(missing_vars)}")
        print("  Using default values")
    else:
        print("  ✓ All required environment variables set")

    # Check recommended authenticators
    print("\nRecommended Authenticators:")
    for auth in fido2_settings.get_recommended_authenticators():
        print(f"  • {auth['name']} ({auth['vendor']}) - {auth['certification']}")

    print("\n" + "=" * 60)
    return True


def check_dependencies():
    """Check required dependencies."""
    print("\nDependency Check:")

    dependencies = {
        "fido2": "FIDO2 library",
        "cryptography": "Cryptography library",
        "sqlalchemy": "Database ORM",
        "fastapi": "Web framework",
        "redis": "Cache backend",
    }

    missing = []
    for module, name in dependencies.items():
        try:
            __import__(module)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} (missing)")
            missing.append(module)

    if missing:
        print(f"\nInstall missing dependencies: pip install {' '.join(missing)}")
        return False

    return True


def main():
    """Main function."""
    print("Haven Health Passport - FIDO2 Configuration Check\n")

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check configuration
    if not check_fido2_configuration():
        sys.exit(1)

    print("\n✓ FIDO2 configuration check completed successfully!")


if __name__ == "__main__":
    main()

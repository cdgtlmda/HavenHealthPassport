#!/usr/bin/env python3
"""Example implementation of ISO 27001 Access Management configuration.

This script demonstrates how to configure and use the ISO 27001-compliant
access management system for the Haven Health Passport.
"""

import json
from datetime import datetime

from src.healthcare.regulatory.iso27001.access_management import (
    AccessLevel,
    AuthenticationMethod,
    ResourceType,
)
from src.healthcare.regulatory.iso27001_implementation import (
    ISO27001ImplementationManager,
)


def main():
    """Main implementation function."""
    print("Haven Health Passport - ISO 27001 Access Management Configuration")
    print("=" * 65)

    # Initialize the implementation manager
    impl_manager = ISO27001ImplementationManager()

    # Configuration for access management
    access_config = {
        "security_settings": {
            "min_password_length": 14,  # Enhanced from default
            "password_complexity": True,
            "password_history": 24,  # Remember last 24 passwords
            "max_password_age_days": 60,  # More frequent changes
            "account_lockout_threshold": 3,  # Stricter lockout
            "account_lockout_duration_minutes": 60,  # Longer lockout
            "session_timeout_minutes": 20,  # Shorter sessions
            "require_mfa_for_privileged": True,
            "access_review_frequency_days": 90,
            "privileged_access_max_duration_hours": 4,  # Shorter privileged sessions
            "enforce_separation_of_duties": True,
            "enforce_least_privilege": True,
            "require_approval_for_sensitive_data": True,
            "log_all_access_attempts": True,
        },
        "initial_users": [
            {
                "user_id": "ADMIN-001",
                "username": "admin",
                "email": "admin@havenhealthpassport.org",
                "full_name": "System Administrator",
                "department": "IT Security",
                "role_ids": ["ROLE-SYS-ADMIN"],
                "auth_methods": ["password", "multi_factor"],
            },
            {
                "user_id": "COMPLIANCE-001",
                "username": "compliance_officer",
                "email": "compliance@havenhealthpassport.org",
                "full_name": "Chief Compliance Officer",
                "department": "Compliance",
                "role_ids": ["ROLE-COMPLIANCE"],
                "auth_methods": ["password", "multi_factor", "certificate"],
            },
            {
                "user_id": "PROVIDER-001",
                "username": "dr_smith",
                "email": "dr.smith@havenhealthpassport.org",
                "full_name": "Dr. Jane Smith",
                "department": "Primary Care",
                "role_ids": ["ROLE-HC-PROVIDER"],
                "auth_methods": ["password", "multi_factor"],
            },
        ],
    }

    # Configure access management
    print("\n1. Configuring Access Management System...")
    result = impl_manager.configure_access_management(
        organization_id="ORG-HAVEN-001",
        configuration=access_config,
        configured_by="SYSTEM-INIT",
    )

    print(f"   ✓ Configuration ID: {result['configuration_id']}")
    print(f"   ✓ Default roles created: {result['components']['default_roles']}")
    print(f"   ✓ Access policies created: {result['components']['access_policies']}")
    print(f"   ✓ Initial users created: {result['components']['users_created']}")

    # Display security settings
    print("\n2. Security Settings Applied:")
    for setting, value in result["security_settings"].items():
        print(f"   • {setting}: {value}")

    # Show updated controls
    print("\n3. ISO 27001 Controls Updated:")
    for control_id in result["controls_updated"]:
        control = impl_manager.framework.controls.get(control_id)
        if control:
            print(f"   • {control_id}: {control.name} - Status: {control.status.value}")

    # Display next steps
    print("\n4. Next Steps:")
    for idx, step in enumerate(result["next_steps"], 1):
        print(f"   {idx}. {step}")
    # Generate compliance report
    print("\n5. Generating Compliance Report...")
    compliance_report = impl_manager.framework.generate_compliance_report()

    print(f"   • Total controls: {compliance_report['statistics']['total_controls']}")
    print(f"   • Implemented: {compliance_report['statistics']['implemented']}")
    print(f"   • In progress: {compliance_report['statistics']['in_progress']}")
    print(f"   • Not implemented: {compliance_report['statistics']['not_implemented']}")
    print(f"   • Compliance score: {compliance_report['compliance_score']:.1f}%")

    # Save configuration for documentation
    config_doc = {
        "implementation_date": datetime.now().isoformat(),
        "organization": "Haven Health Passport",
        "standard": "ISO 27001:2022",
        "component": "Access Management (A.8)",
        "configuration": result,
        "compliance_status": {
            "score": compliance_report["compliance_score"],
            "controls_implemented": compliance_report["statistics"]["implemented"],
        },
    }

    with open("iso27001_access_management_config.json", "w") as f:
        json.dump(config_doc, f, indent=2, default=str)

    print("\n✅ Access Management Configuration Complete!")
    print(f"   Configuration saved to: iso27001_access_management_config.json")

    # Display summary
    print("\n" + "=" * 65)
    print("SUMMARY: ISO 27001 Access Management Implementation")
    print("=" * 65)
    print(f"✓ Access control system configured with enhanced security settings")
    print(f"✓ Role-based access control (RBAC) implemented")
    print(f"✓ Separation of duties enforced")
    print(f"✓ Privileged access management enabled")
    print(f"✓ Multi-factor authentication required for privileged users")
    print(f"✓ Audit logging configured for all access attempts")
    print(f"✓ Periodic access review process established (90-day cycle)")
    print("\nThe access management system is now ready for production use.")


if __name__ == "__main__":
    main()

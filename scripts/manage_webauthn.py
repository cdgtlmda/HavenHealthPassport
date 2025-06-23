#!/usr/bin/env python3
"""
WebAuthn credential management utility.

This script provides administrative functions for managing WebAuthn credentials
in the Haven Health Passport system.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.database import DATABASE_URL
from src.models.auth import UserAuth, WebAuthnCredential


def get_db_session():
    """Create database session."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()


def list_user_credentials(user_email: str) -> List[WebAuthnCredential]:
    """List all WebAuthn credentials for a user.

    Args:
        user_email: Email of the user

    Returns:
        List of credentials
    """
    session = get_db_session()

    try:
        user = session.query(UserAuth).filter(UserAuth.email == user_email).first()

        if not user:
            print(f"User not found: {user_email}")
            return []

        credentials = (
            session.query(WebAuthnCredential)
            .filter(WebAuthnCredential.user_id == user.id)
            .all()
        )

        return credentials

    finally:
        session.close()


def revoke_credential(credential_id: str, reason: str = "admin_revoked") -> bool:
    """Revoke a WebAuthn credential.

    Args:
        credential_id: Credential ID to revoke
        reason: Revocation reason

    Returns:
        True if successful
    """
    session = get_db_session()

    try:
        credential = (
            session.query(WebAuthnCredential)
            .filter(WebAuthnCredential.credential_id == credential_id)
            .first()
        )

        if not credential:
            print(f"Credential not found: {credential_id}")
            return False

        credential.is_active = False
        credential.revoked_at = datetime.utcnow()
        credential.revocation_reason = reason

        session.commit()
        print(f"Credential revoked: {credential_id}")
        return True

    except Exception as e:
        session.rollback()
        print(f"Error revoking credential: {e}")
        return False

    finally:
        session.close()


def cleanup_inactive_credentials(days: int = 365) -> int:
    """Clean up credentials that haven't been used in specified days.

    Args:
        days: Number of days of inactivity

    Returns:
        Number of credentials cleaned up
    """
    session = get_db_session()

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        credentials = (
            session.query(WebAuthnCredential)
            .filter(
                WebAuthnCredential.is_active == True,
                (WebAuthnCredential.last_used_at < cutoff_date)
                | (WebAuthnCredential.last_used_at == None),
            )
            .all()
        )

        count = 0
        for credential in credentials:
            # Only deactivate if created before cutoff and never used
            if credential.created_at < cutoff_date:
                credential.is_active = False
                credential.revoked_at = datetime.utcnow()
                credential.revocation_reason = f"inactive_{days}_days"
                count += 1

        session.commit()
        print(f"Deactivated {count} inactive credentials")
        return count

    except Exception as e:
        session.rollback()
        print(f"Error cleaning up credentials: {e}")
        return 0

    finally:
        session.close()


def generate_usage_report() -> None:
    """Generate WebAuthn usage report."""
    session = get_db_session()

    try:
        # Total credentials
        total = session.query(WebAuthnCredential).count()
        active = (
            session.query(WebAuthnCredential)
            .filter(WebAuthnCredential.is_active == True)
            .count()
        )

        # Usage statistics
        used_last_30_days = (
            session.query(WebAuthnCredential)
            .filter(
                WebAuthnCredential.is_active == True,
                WebAuthnCredential.last_used_at
                >= datetime.utcnow() - timedelta(days=30),
            )
            .count()
        )

        # Device types
        platform_count = (
            session.query(WebAuthnCredential)
            .filter(WebAuthnCredential.authenticator_attachment == "platform")
            .count()
        )

        cross_platform_count = (
            session.query(WebAuthnCredential)
            .filter(WebAuthnCredential.authenticator_attachment == "cross-platform")
            .count()
        )

        print("\n=== WebAuthn Usage Report ===")
        print(f"Total credentials: {total}")
        print(f"Active credentials: {active}")
        print(f"Used in last 30 days: {used_last_30_days}")
        print(f"\nDevice Types:")
        print(f"  Platform authenticators: {platform_count}")
        print(f"  Cross-platform authenticators: {cross_platform_count}")
        print(f"  Unspecified: {total - platform_count - cross_platform_count}")

    finally:
        session.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WebAuthn credential management utility"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List credentials command
    list_parser = subparsers.add_parser("list", help="List user credentials")
    list_parser.add_argument("email", help="User email address")

    # Revoke credential command
    revoke_parser = subparsers.add_parser("revoke", help="Revoke a credential")
    revoke_parser.add_argument("credential_id", help="Credential ID to revoke")
    revoke_parser.add_argument(
        "--reason", default="admin_revoked", help="Revocation reason"
    )

    # Cleanup command
    cleanup_parser = subparsers.add_parser(
        "cleanup", help="Clean up inactive credentials"
    )
    cleanup_parser.add_argument(
        "--days", type=int, default=365, help="Days of inactivity"
    )

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate usage report")

    args = parser.parse_args()

    if args.command == "list":
        credentials = list_user_credentials(args.email)
        if credentials:
            print(f"\nCredentials for {args.email}:")
            for cred in credentials:
                status = "Active" if cred.is_active else "Revoked"
                last_used = cred.last_used_at or "Never"
                print(
                    f"  - {cred.credential_id[:20]}... ({cred.device_name}) "
                    f"[{status}] Last used: {last_used}"
                )
        else:
            print("No credentials found")

    elif args.command == "revoke":
        revoke_credential(args.credential_id, args.reason)

    elif args.command == "cleanup":
        cleanup_inactive_credentials(args.days)

    elif args.command == "report":
        generate_usage_report()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

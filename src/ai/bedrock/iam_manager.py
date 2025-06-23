"""IAM role management for Bedrock access.

This module handles the application-level integration with AWS IAM roles
created by Terraform for secure Bedrock access.
"""

import os
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

from src.utils.logging import get_logger

logger = get_logger(__name__)


class IAMRoleManager:
    """Manages IAM roles for Bedrock access."""

    def __init__(self) -> None:
        """Initialize IAM manager."""
        self.iam_client = boto3.client("iam")
        self.sts_client = boto3.client("sts")

        # Get role names from environment or use defaults
        self.bedrock_role_name = os.getenv(
            "BEDROCK_IAM_ROLE_NAME",
            f'haven-health-passport-bedrock-role-{os.getenv("ENVIRONMENT", "development")}',
        )

    def get_role_arn(self, role_name: Optional[str] = None) -> Optional[str]:
        """Get the ARN of an IAM role."""
        role_name = role_name or self.bedrock_role_name

        try:
            response = self.iam_client.get_role(RoleName=role_name)
            return str(response["Role"]["Arn"])
        except ClientError as e:
            logger.error(f"Failed to get role ARN for {role_name}: {e}")
            return None

    def assume_bedrock_role(
        self, session_name: str = "bedrock-session"
    ) -> Optional[Dict]:
        """Assume the Bedrock IAM role for temporary credentials."""
        role_arn = self.get_role_arn()
        if not role_arn:
            return None

        try:
            response = self.sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name,
                DurationSeconds=3600,  # 1 hour
            )

            return {
                "access_key": response["Credentials"]["AccessKeyId"],
                "secret_key": response["Credentials"]["SecretAccessKey"],
                "session_token": response["Credentials"]["SessionToken"],
                "expiration": response["Credentials"]["Expiration"],
            }
        except ClientError as e:
            logger.error(f"Failed to assume role {role_arn}: {e}")
            return None

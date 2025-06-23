"""Production Blockchain Verification Service.

This module provides real blockchain verification for healthcare records
using AWS Managed Blockchain for HIPAA-compliant distributed ledger.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from src.config import get_settings
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class VerificationStatus(Enum):
    """Verification status types."""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    TAMPERED = "tampered"
    EXPIRED = "expired"


@dataclass
class VerificationResult:
    """Result of blockchain verification."""

    verified: bool
    status: VerificationStatus
    transaction_id: Optional[str]
    timestamp: datetime
    block_number: Optional[int]
    hash: str
    details: Dict[str, Any]


class BlockchainVerifier:
    """Production blockchain verification service using AWS Managed Blockchain."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize blockchain verifier with configuration."""
        self.settings = get_settings()
        self.config = config or self._get_default_config()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-blockchain"
        )

        # Initialize AWS clients for Managed Blockchain
        self.blockchain_client = boto3.client(
            "managedblockchain", region_name=self.settings.AWS_REGION or "us-east-1"
        )
        self.lambda_client = boto3.client(
            "lambda", region_name=self.settings.AWS_REGION or "us-east-1"
        )

        # Network configuration
        self.network_id = self.settings.MANAGED_BLOCKCHAIN_NETWORK_ID
        self.member_id = self.settings.MANAGED_BLOCKCHAIN_MEMBER_ID

        # Connection pool for performance
        self.connection_pool: List[Any] = []
        self.max_connections = 10

        # Initialize connection - will be done on first use
        self._initialized = False

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default AWS Managed Blockchain configuration."""
        return {
            "channel_name": self.settings.BLOCKCHAIN_CHANNEL or "healthcare-channel",
            "chaincode_name": self.settings.BLOCKCHAIN_CHAINCODE or "health-records",
            "timeout": 30,
            "retry_attempts": 3,
        }

    async def _initialize_connection(self) -> None:
        """Initialize connection to AWS Managed Blockchain network."""
        try:
            # Verify network exists and is accessible
            if self.network_id and self.member_id:
                response = self.blockchain_client.get_network(NetworkId=self.network_id)
                network_status = response["Network"]["Status"]

                if network_status != "AVAILABLE":
                    logger.warning(f"Blockchain network status: {network_status}")
                else:
                    logger.info(
                        "Successfully connected to AWS Managed Blockchain network"
                    )
            else:
                logger.warning("Blockchain network ID or member ID not configured")

        except ClientError as e:
            logger.error(f"Failed to connect to blockchain: {e}")
            # In production, would implement fallback or queue mechanism
        except (AttributeError, ValueError, RuntimeError) as e:
            logger.error(f"Unexpected error connecting to blockchain: {e}")

    async def verify_record(
        self, record_data: Dict[str, Any], record_type: str = "health_record"
    ) -> VerificationResult:
        """
        Verify a healthcare record on the blockchain.

        Args:
            record_data: Record data to verify
            record_type: Type of record

        Returns:
            VerificationResult with verification details
        """
        start_time = time.time()

        try:
            # Generate record hash
            record_hash = self._generate_record_hash(record_data)

            # Prepare chaincode arguments
            args = [
                record_data.get("id", ""),
                record_hash,
                record_type,
                json.dumps(record_data.get("metadata", {})),
            ]

            # Submit transaction with retry logic
            for attempt in range(self.config["retry_attempts"]):
                try:
                    # Query existing record
                    record_id = record_data.get("id")
                    if not record_id:
                        raise ValueError("Record ID is required")
                    existing = await self._query_record(record_id)

                    if existing:
                        # Verify hash matches
                        if existing.get("hash") == record_hash:
                            return VerificationResult(
                                verified=True,
                                status=VerificationStatus.VERIFIED,
                                transaction_id=existing.get("transaction_id"),
                                timestamp=datetime.utcnow(),
                                block_number=existing.get("block_number"),
                                hash=record_hash,
                                details={
                                    "existing_record": True,
                                    "verification_time": time.time() - start_time,
                                },
                            )
                        else:
                            return VerificationResult(
                                verified=False,
                                status=VerificationStatus.TAMPERED,
                                transaction_id=None,
                                timestamp=datetime.utcnow(),
                                block_number=None,
                                hash=record_hash,
                                details={
                                    "expected_hash": existing.get("hash"),
                                    "actual_hash": record_hash,
                                    "message": "Record hash mismatch - possible tampering",
                                },
                            )
                    else:
                        # Submit new record
                        result = await self._submit_record(args)

                        return VerificationResult(
                            verified=True,
                            status=VerificationStatus.VERIFIED,
                            transaction_id=result.get("transaction_id"),
                            timestamp=datetime.utcnow(),
                            block_number=result.get("block_number"),
                            hash=record_hash,
                            details={
                                "new_record": True,
                                "verification_time": time.time() - start_time,
                            },
                        )

                except asyncio.TimeoutError:
                    if attempt < self.config["retry_attempts"] - 1:
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                        continue
                    raise

            # If we get here, all retries failed without exception
            return VerificationResult(
                verified=False,
                status=VerificationStatus.FAILED,
                transaction_id=None,
                timestamp=datetime.utcnow(),
                block_number=None,
                hash=record_hash if "record_hash" in locals() else "",
                details={
                    "error": "All retry attempts exhausted",
                    "verification_time": time.time() - start_time,
                },
            )

        except (ClientError, RuntimeError, ValueError, KeyError) as e:
            logger.error(f"Blockchain verification failed: {e}")
            return VerificationResult(
                verified=False,
                status=VerificationStatus.FAILED,
                transaction_id=None,
                timestamp=datetime.utcnow(),
                block_number=None,
                hash=record_hash if "record_hash" in locals() else "",
                details={
                    "error": str(e),
                    "verification_time": time.time() - start_time,
                },
            )

    async def _query_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Query existing record from blockchain using Lambda."""
        try:
            # Use Lambda function to query blockchain
            payload = {
                "action": "query",
                "recordId": record_id,
                "networkId": self.network_id,
                "memberId": self.member_id,
                "channelName": self.config["channel_name"],
                "chaincodeName": self.config["chaincode_name"],
            }

            result = await self._invoke_blockchain_lambda(
                f"haven-health-blockchain-query-{self.settings.environment}", payload
            )

            if result and result.get("success"):
                return result.get("data")
            return None

        except (ClientError, RuntimeError, ValueError, KeyError) as e:
            logger.error(f"Failed to query record: {e}")
            return None

    async def _submit_record(self, args: List[str]) -> Dict[str, Any]:
        """Submit new record to blockchain using Lambda."""
        try:
            # Use Lambda function to submit to blockchain
            payload = {
                "action": "submit",
                "args": args,
                "networkId": self.network_id,
                "memberId": self.member_id,
                "channelName": self.config["channel_name"],
                "chaincodeName": self.config["chaincode_name"],
            }

            result = await self._invoke_blockchain_lambda(
                f"haven-health-blockchain-submit-{self.settings.environment}", payload
            )

            if result and result.get("success"):
                data: Dict[str, Any] = result.get("data", {})
                return data
            else:
                raise ValueError(
                    f"Blockchain submission failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            logger.error(f"Failed to submit record: {e}")
            raise

    async def _invoke_blockchain_lambda(
        self, function_name: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke Lambda function for blockchain operations."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType="RequestResponse",
                    Payload=json.dumps(payload),
                ),
            )

            result: Dict[str, Any] = json.loads(response["Payload"].read())
            return result
        except Exception as e:
            logger.error(f"Error invoking blockchain Lambda: {e}")
            raise

    def _generate_record_hash(self, record_data: Dict[str, Any]) -> str:
        """Generate deterministic hash for record data."""
        # Remove non-deterministic fields
        data_to_hash = record_data.copy()
        for field in ["timestamp", "created_at", "updated_at"]:
            data_to_hash.pop(field, None)

        # Sort keys for deterministic ordering
        sorted_data = json.dumps(data_to_hash, sort_keys=True)

        # Generate SHA-256 hash
        return hashlib.sha256(sorted_data.encode()).hexdigest()

    async def verify_bulk_records(
        self, records: List[Dict[str, Any]], batch_size: int = 100
    ) -> List[VerificationResult]:
        """Verify multiple records in batches for performance."""
        results = []

        # Process in batches
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]

            # Verify batch concurrently
            batch_results = await asyncio.gather(
                *[self.verify_record(record) for record in batch],
                return_exceptions=True,
            )

            # Handle results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch verification error: {result}")
                    # Create failed result
                    results.append(
                        VerificationResult(
                            verified=False,
                            status=VerificationStatus.FAILED,
                            transaction_id=None,
                            timestamp=datetime.utcnow(),
                            block_number=None,
                            hash="",
                            details={"error": str(result)},
                        )
                    )
                else:
                    if isinstance(result, VerificationResult):
                        results.append(result)

        return results

    async def get_record_history(self, record_id: str) -> List[Dict[str, Any]]:
        """Get complete history of a record from blockchain."""
        if not self._initialized:
            await self._initialize_connection()

        try:
            # Use Lambda function to get record history
            payload = {
                "action": "getHistory",
                "recordId": record_id,
                "networkId": self.network_id,
                "memberId": self.member_id,
                "channelName": self.config["channel_name"],
                "chaincodeName": self.config["chaincode_name"],
            }

            result = await self._invoke_blockchain_lambda(
                f"haven-health-blockchain-history-{self.settings.environment}", payload
            )

            if result and result.get("success"):
                history: List[Dict[str, Any]] = result.get("data", [])
                return history
            return []

        except (ClientError, RuntimeError, ValueError, KeyError) as e:
            logger.error(f"Failed to get record history: {e}")
            return []

    async def close(self) -> None:
        """Close blockchain connections."""
        # AWS clients don't need explicit closing


# Global instance
blockchain_verifier = BlockchainVerifier()

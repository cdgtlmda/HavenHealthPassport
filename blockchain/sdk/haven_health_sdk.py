"""
Haven Health Passport Blockchain SDK Integration
Python SDK for interacting with the blockchain network
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from hfc.fabric import Client
from hfc.fabric.orderer import Orderer
from hfc.fabric.peer import Peer
from hfc.fabric.transaction.tx_context import TXContext
from hfc.fabric.transaction.tx_proposal_request import TXProposalRequest
from hfc.fabric.user import User
from hfc.util.crypto.crypto import ecies

logger = logging.getLogger(__name__)


class HavenHealthBlockchainSDK:
    """
    Main SDK class for interacting with Haven Health Passport blockchain
    """

    def __init__(self, config_path: str = "./connection-profile.yaml"):
        """
        Initialize the SDK with connection profile

        Args:
            config_path: Path to connection profile YAML file
        """
        self.client = Client(net_profile=config_path)
        self.channel_name = "healthcare-channel"
        self.chaincode_name = "health-records-chaincode"
        self.org_name = None
        self.user = None
        self._event_hub = None

    async def initialize(self, org_name: str, user_name: str, user_pwd: str):
        """
        Initialize the SDK with organization and user credentials

        Args:
            org_name: Organization MSP ID
            user_name: Username for authentication
            user_pwd: Password for authentication
        """
        try:
            # Set organization
            self.org_name = org_name
            self.client.new_channel(self.channel_name)

            # Enroll user
            enrollment = await self.client.enroll_user(
                org_name=org_name, user_name=user_name, user_pwd=user_pwd
            )

            # Create user context
            self.user = self.client.get_user(org_name, user_name)

            logger.info(f"SDK initialized for {org_name} with user {user_name}")

        except Exception as e:
            logger.error(f"Failed to initialize SDK: {str(e)}")
            raise

    async def create_health_record(self, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new health record on the blockchain

        Args:
            record_data: Dictionary containing health record information

        Returns:
            Transaction response
        """
        try:
            # Prepare the transaction
            args = [json.dumps(record_data)]

            # Invoke chaincode
            response = await self.client.chaincode_invoke(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=self._get_endorsing_peers(),
                fcn="CreateRecord",
                args=args,
                cc_name=self.chaincode_name,
                wait_for_event=True,
            )

            return {
                "success": True,
                "transaction_id": response["tx_id"],
                "record_id": record_data.get("recordId"),
            }

        except Exception as e:
            logger.error(f"Failed to create health record: {str(e)}")
            return {"success": False, "error": str(e)}

    async def update_health_record(
        self, record_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing health record

        Args:
            record_id: ID of the record to update
            updates: Dictionary of fields to update

        Returns:
            Transaction response
        """
        try:
            args = [record_id, json.dumps(updates)]

            response = await self.client.chaincode_invoke(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=self._get_endorsing_peers(),
                fcn="UpdateRecord",
                args=args,
                cc_name=self.chaincode_name,
                wait_for_event=True,
            )

            return {
                "success": True,
                "transaction_id": response["tx_id"],
                "record_id": record_id,
            }

        except Exception as e:
            logger.error(f"Failed to update health record: {str(e)}")
            return {"success": False, "error": str(e)}

    async def read_health_record(self, record_id: str) -> Dict[str, Any]:
        """
        Read a health record from the blockchain

        Args:
            record_id: ID of the record to read

        Returns:
            Health record data or error
        """
        try:
            args = [record_id]

            response = await self.client.chaincode_query(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=self._get_query_peers(),
                fcn="ReadRecord",
                args=args,
                cc_name=self.chaincode_name,
            )

            # Parse response
            record = json.loads(response)

            return {"success": True, "record": record}

        except Exception as e:
            logger.error(f"Failed to read health record: {str(e)}")
            return {"success": False, "error": str(e)}

    async def query_records_by_patient(self, patient_id: str) -> Dict[str, Any]:
        """
        Query all records for a specific patient

        Args:
            patient_id: Patient identifier

        Returns:
            List of health records or error
        """
        try:
            args = [patient_id]

            response = await self.client.chaincode_query(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=self._get_query_peers(),
                fcn="QueryRecordsByPatient",
                args=args,
                cc_name=self.chaincode_name,
            )

            records = json.loads(response)

            return {"success": True, "records": records, "count": len(records)}

        except Exception as e:
            logger.error(f"Failed to query patient records: {str(e)}")
            return {"success": False, "error": str(e)}

    async def grant_access(self, grant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Grant access to a health record

        Args:
            grant_data: Access grant information

        Returns:
            Transaction response
        """
        try:
            args = [json.dumps(grant_data)]

            response = await self.client.chaincode_invoke(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=self._get_endorsing_peers(),
                fcn="GrantAccess",
                args=args,
                cc_name=self.chaincode_name,
                wait_for_event=True,
            )

            return {
                "success": True,
                "transaction_id": response["tx_id"],
                "grant_id": grant_data.get("grantId"),
            }

        except Exception as e:
            logger.error(f"Failed to grant access: {str(e)}")
            return {"success": False, "error": str(e)}

    async def check_access(
        self, user_id: str, resource_id: str, action: str
    ) -> Dict[str, Any]:
        """
        Check if a user has access to a resource

        Args:
            user_id: User identifier
            resource_id: Resource (record) identifier
            action: Action to check (read, write, etc.)

        Returns:
            Access check result
        """
        try:
            args = [user_id, resource_id, action]

            response = await self.client.chaincode_query(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=self._get_query_peers(),
                fcn="CheckAccess",
                args=args,
                cc_name=self.chaincode_name,
            )

            has_access = json.loads(response)

            return {
                "success": True,
                "has_access": has_access,
                "user_id": user_id,
                "resource_id": resource_id,
                "action": action,
            }

        except Exception as e:
            logger.error(f"Failed to check access: {str(e)}")
            return {"success": False, "error": str(e)}

    async def request_verification(
        self, verification_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Request verification for a health record

        Args:
            verification_request: Verification request data

        Returns:
            Transaction response
        """
        try:
            args = [json.dumps(verification_request)]

            response = await self.client.chaincode_invoke(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=self._get_endorsing_peers(),
                fcn="RequestVerification",
                args=args,
                cc_name=self.chaincode_name,
                wait_for_event=True,
            )

            return {
                "success": True,
                "transaction_id": response["tx_id"],
                "request_id": verification_request.get("requestId"),
            }

        except Exception as e:
            logger.error(f"Failed to request verification: {str(e)}")
            return {"success": False, "error": str(e)}

    def _get_endorsing_peers(self) -> List[Peer]:
        """Get list of endorsing peers for the organization"""
        # This would be determined based on the connection profile
        # and endorsement policy
        return self.client.get_peers_for_org(self.org_name)

    def _get_query_peers(self) -> List[Peer]:
        """Get list of peers for query operations"""
        # Usually just one peer is enough for queries
        peers = self.client.get_peers_for_org(self.org_name)
        return [peers[0]] if peers else []

    async def register_event_listener(self, event_name: str, callback):
        """
        Register an event listener for chaincode events

        Args:
            event_name: Name of the event to listen for
            callback: Callback function to handle events
        """
        try:
            # Get event hub
            if not self._event_hub:
                peer = self._get_query_peers()[0]
                self._event_hub = self.client.get_event_hub(peer)

            # Register chaincode event
            reg_id = self._event_hub.register_chaincode_event(
                self.chaincode_name,
                event_name,
                onEvent=callback,
                onError=self._handle_event_error,
            )

            # Connect to event hub
            await self._event_hub.connect()

            logger.info(f"Registered event listener for {event_name}")
            return reg_id

        except Exception as e:
            logger.error(f"Failed to register event listener: {str(e)}")
            raise

    def _handle_event_error(self, error):
        """Handle event hub errors"""
        logger.error(f"Event hub error: {error}")

    async def close(self):
        """Clean up SDK resources"""
        try:
            if self._event_hub:
                self._event_hub.disconnect()

            logger.info("SDK closed successfully")

        except Exception as e:
            logger.error(f"Error closing SDK: {str(e)}")


# Example usage
async def main():
    # Initialize SDK
    sdk = HavenHealthBlockchainSDK()
    await sdk.initialize(
        org_name="HealthcareProvider1MSP", user_name="doctor1", user_pwd="doctorpw"
    )

    # Create a health record
    record = {
        "recordId": "REC001",
        "patientId": "PAT001",
        "providerId": "PROV001",
        "recordType": "medical_history",
        "encryptedData": "encrypted_medical_data_here",
        "dataHash": "sha256_hash_here",
        "metadata": {"createdBy": "Dr. Smith", "department": "Cardiology"},
    }

    result = await sdk.create_health_record(record)
    print(f"Create record result: {result}")

    # Read the record
    read_result = await sdk.read_health_record("REC001")
    print(f"Read record result: {read_result}")

    # Grant access
    grant = {
        "grantId": "GRANT001",
        "resourceId": "REC001",
        "grantorId": "PAT001",
        "granteeId": "PROV002",
        "permissions": ["read"],
        "expiresAt": "2024-12-31T23:59:59Z",
    }

    grant_result = await sdk.grant_access(grant)
    print(f"Grant access result: {grant_result}")

    # Close SDK
    await sdk.close()


if __name__ == "__main__":
    asyncio.run(main())

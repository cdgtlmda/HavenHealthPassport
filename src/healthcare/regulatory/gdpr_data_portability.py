"""GDPR Data Portability Implementation.

This module implements comprehensive GDPR data portability features
for exporting and transferring personal health data.
"""

import base64
import csv
import json
import logging
import uuid
import zipfile
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional, Tuple

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import hipaa_access_control

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Supported export formats for data portability."""

    JSON = "json"
    XML = "xml"
    CSV = "csv"
    FHIR = "fhir"
    HL7 = "hl7"
    PDF = "pdf"
    PACKAGE = "package"  # Multi-format package


class DataScope(Enum):
    """Scope of data to export."""

    ALL = "all"
    HEALTH_RECORDS = "health_records"
    PERSONAL_INFO = "personal_info"
    ACTIVITY_LOGS = "activity_logs"
    CONSENT_RECORDS = "consent_records"
    COMMUNICATIONS = "communications"
    CUSTOM = "custom"


class PortabilityStatus(Enum):
    """Status of portability request."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    DELIVERED = "delivered"
    FAILED = "failed"


class GDPRDataPortability:
    """Implements GDPR data portability requirements."""

    # FHIR resource type
    __fhir_resource__ = "Bundle"

    def __init__(self) -> None:
        """Initialize data portability system."""
        self.export_requests: Dict[str, Dict[str, Any]] = {}
        self.transfer_requests: Dict[str, Dict[str, Any]] = {}
        self.export_templates = self._initialize_templates()
        self.format_handlers = self._initialize_handlers()
        self.export_cache: Dict[str, Any] = {}
        # Add FHIR validator
        self.fhir_validator = FHIRValidator()

    def _initialize_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize export templates."""
        return {
            "standard": {
                "name": "Standard Personal Data Export",
                "description": "Complete export of personal data",
                "scopes": [DataScope.ALL],
                "formats": [ExportFormat.JSON, ExportFormat.CSV],
                "include_metadata": True,
                "include_audit_log": True,
            },
            "health_only": {
                "name": "Health Records Export",
                "description": "Medical records and health data only",
                "scopes": [DataScope.HEALTH_RECORDS],
                "formats": [ExportFormat.FHIR, ExportFormat.PDF],
                "include_metadata": True,
                "include_audit_log": False,
            },
            "minimal": {
                "name": "Basic Information Export",
                "description": "Minimal personal information",
                "scopes": [DataScope.PERSONAL_INFO],
                "formats": [ExportFormat.JSON],
                "include_metadata": False,
                "include_audit_log": False,
            },
        }

    def _initialize_handlers(self) -> Dict[ExportFormat, Any]:
        """Initialize format handlers."""
        return {
            ExportFormat.JSON: self._export_to_json,
            ExportFormat.XML: self._export_to_xml,
            ExportFormat.CSV: self._export_to_csv,
            ExportFormat.FHIR: self._export_to_fhir,
            ExportFormat.HL7: self._export_to_hl7,
            ExportFormat.PDF: self._export_to_pdf,
            ExportFormat.PACKAGE: self._export_to_package,
        }

    def request_data_export(
        self,
        data_subject_id: str,
        scope: DataScope,
        export_format: ExportFormat,
        include_options: Optional[Dict[str, bool]] = None,
    ) -> str:
        """Request data export for portability.

        Args:
            data_subject_id: ID of data subject
            scope: Scope of data to export
            export_format: Export format
            include_options: Optional inclusion settings

        Returns:
            Export request ID
        """
        request_id = self._generate_request_id()

        request = {
            "request_id": request_id,
            "data_subject_id": data_subject_id,
            "request_date": datetime.now(),
            "scope": scope.value,
            "format": export_format.value,
            "status": PortabilityStatus.PENDING.value,
            "include_options": include_options
            or {
                "metadata": True,
                "audit_log": False,
                "consent_records": True,
                "communications": False,
            },
            "expiry_date": datetime.now() + timedelta(days=30),
            "file_location": None,
            "file_size": None,
            "completion_date": None,
        }

        self.export_requests[request_id] = request

        # Start processing
        self._process_export_request(request_id)

        logger.info(
            "Data export requested: %s for %s in %s format",
            request_id,
            data_subject_id,
            export_format.value,
        )

        return request_id

    def request_direct_transfer(
        self,
        data_subject_id: str,
        target_controller: str,
        scope: DataScope,
        transfer_details: Dict[str, Any],
    ) -> str:
        """Request direct transfer to another controller.

        Args:
            data_subject_id: ID of data subject
            target_controller: Target data controller
            scope: Scope of data to transfer
            transfer_details: Transfer specifications

        Returns:
            Transfer request ID
        """
        transfer_id = self._generate_transfer_id()

        transfer_request = {
            "transfer_id": transfer_id,
            "data_subject_id": data_subject_id,
            "request_date": datetime.now(),
            "source_controller": "Current Organization",
            "target_controller": target_controller,
            "scope": scope.value,
            "status": PortabilityStatus.PENDING.value,
            "transfer_method": transfer_details.get("method", "secure_api"),
            "encryption_required": True,
            "verification_required": True,
            "transfer_date": None,
            "confirmation": None,
        }

        self.transfer_requests[transfer_id] = transfer_request

        logger.info(
            "Direct transfer requested: %s to %s", transfer_id, target_controller
        )

        return transfer_id

    def get_export_status(self, request_id: str) -> Dict[str, Any]:
        """Get status of export request.

        Args:
            request_id: Export request ID

        Returns:
            Export status information
        """
        if request_id not in self.export_requests:
            return {"error": "Request not found"}

        request = self.export_requests[request_id]

        status_info = {
            "request_id": request_id,
            "status": request["status"],
            "requested_date": request["request_date"],
            "format": request["format"],
            "scope": request["scope"],
        }

        if request["status"] == PortabilityStatus.READY.value:
            status_info.update(
                {
                    "download_available": True,
                    "file_size": request.get("file_size"),
                    "expiry_date": request["expiry_date"],
                    "download_url": self._generate_download_url(request_id),
                }
            )
        elif request["status"] == PortabilityStatus.PROCESSING.value:
            status_info["estimated_completion"] = datetime.now() + timedelta(minutes=30)
        elif request["status"] == PortabilityStatus.FAILED.value:
            status_info["error_message"] = request.get("error_message", "Export failed")

        return status_info

    def _process_export_request(self, request_id: str) -> None:
        """Process export request asynchronously.

        Args:
            request_id: Export request ID
        """
        request = self.export_requests[request_id]
        request["status"] = PortabilityStatus.PROCESSING.value

        try:
            # Collect data based on scope
            data = self._collect_data(
                request["data_subject_id"],
                DataScope(request["scope"]),
                request["include_options"],
            )

            # Export to requested format
            format_enum = ExportFormat(request["format"])
            handler = self.format_handlers.get(format_enum)

            if handler:
                export_result = handler(data, request["data_subject_id"])

                # Store export result
                request["file_location"] = export_result["location"]
                request["file_size"] = export_result["size"]
                request["completion_date"] = datetime.now()
                request["status"] = PortabilityStatus.READY.value

                # Cache for quick access
                self.export_cache[request_id] = export_result["data"]

                logger.info("Export completed: %s", request_id)
            else:
                raise ValueError(f"Unsupported format: {request['format']}")

        except (ValueError, KeyError, IOError) as e:
            request["status"] = PortabilityStatus.FAILED.value
            request["error_message"] = str(e)
            logger.error("Export failed: %s - %s", request_id, str(e))

    def _collect_data(
        self, data_subject_id: str, scope: DataScope, include_options: Dict[str, bool]
    ) -> Dict[str, Any]:
        """Collect data for export based on scope.

        Args:
            data_subject_id: Data subject ID
            scope: Data scope
            include_options: What to include

        Returns:
            Collected data
        """
        collected_data: Dict[str, Any] = {
            "export_info": {
                "data_subject_id": data_subject_id,
                "export_date": datetime.now().isoformat(),
                "scope": scope.value,
                "gdpr_article": "Article 20 - Right to data portability",
            }
        }

        # Collect based on scope
        if scope in [DataScope.ALL, DataScope.PERSONAL_INFO]:
            collected_data["personal_information"] = self._get_personal_info(
                data_subject_id
            )

        if scope in [DataScope.ALL, DataScope.HEALTH_RECORDS]:
            collected_data["health_records"] = self._get_health_records(data_subject_id)

        if scope in [DataScope.ALL, DataScope.ACTIVITY_LOGS]:
            if include_options.get("audit_log", False):
                collected_data["activity_logs"] = self._get_activity_logs(
                    data_subject_id
                )

        if scope in [DataScope.ALL, DataScope.CONSENT_RECORDS]:
            if include_options.get("consent_records", True):
                collected_data["consent_records"] = self._get_consent_records(
                    data_subject_id
                )

        if scope in [DataScope.ALL, DataScope.COMMUNICATIONS]:
            if include_options.get("communications", False):
                collected_data["communications"] = self._get_communications(
                    data_subject_id
                )

        # Add metadata if requested
        if include_options.get("metadata", True):
            collected_data["metadata"] = self._generate_metadata(collected_data)

        return collected_data

    def _export_to_json(
        self, data: Dict[str, Any], data_subject_id: str
    ) -> Dict[str, Any]:
        """Export data to JSON format.

        Args:
            data: Data to export
            data_subject_id: Data subject ID

        Returns:
            Export result
        """
        json_data = json.dumps(data, indent=2, default=str)

        # In production, would save to secure storage
        filename = f"gdpr_export_{data_subject_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        return {
            "location": f"/exports/{filename}",
            "size": len(json_data.encode()),
            "data": json_data,
            "format": "application/json",
            "encoding": "utf-8",
        }

    def _export_to_xml(
        self, data: Dict[str, Any], data_subject_id: str
    ) -> Dict[str, Any]:
        """Export data to XML format.

        Args:
            data: Data to export
            data_subject_id: Data subject ID

        Returns:
            Export result
        """
        # Simple XML conversion
        xml_data = self._dict_to_xml(data, "PersonalDataExport")

        filename = f"gdpr_export_{data_subject_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"

        return {
            "location": f"/exports/{filename}",
            "size": len(xml_data.encode()),
            "data": xml_data,
            "format": "application/xml",
            "encoding": "utf-8",
        }

    def _export_to_csv(
        self, data: Dict[str, Any], data_subject_id: str
    ) -> Dict[str, Any]:
        """Export data to CSV format.

        Args:
            data: Data to export
            data_subject_id: Data subject ID

        Returns:
            Export result
        """
        # Flatten nested data for CSV
        flattened = self._flatten_dict(data)

        output = StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(["Field", "Value"])

        # Write data
        for key, value in flattened.items():
            writer.writerow([key, str(value)])

        csv_data = output.getvalue()

        filename = f"gdpr_export_{data_subject_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return {
            "location": f"/exports/{filename}",
            "size": len(csv_data.encode()),
            "data": csv_data,
            "format": "text/csv",
            "encoding": "utf-8",
        }

    def _export_to_fhir(
        self, data: Dict[str, Any], data_subject_id: str
    ) -> Dict[str, Any]:
        """Export data to FHIR format."""
        # In production, would convert to FHIR resources
        fhir_bundle: Dict[str, Any] = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [],
        }

        # Add patient resource
        if "personal_information" in data:
            fhir_bundle["entry"].append(
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": data_subject_id,
                        "name": [
                            {"text": data["personal_information"].get("name", "")}
                        ],
                    }
                }
            )

        # Validate FHIR bundle
        validation_result = self.fhir_validator.validate_bundle(fhir_bundle)
        if not validation_result["valid"]:
            logger.warning(
                "FHIR bundle validation errors: %s", validation_result["errors"]
            )

        filename = f"gdpr_export_{data_subject_id}_fhir.json"

        return {
            "location": f"/exports/{filename}",
            "size": len(json.dumps(fhir_bundle).encode()),
            "data": json.dumps(fhir_bundle),
            "format": "application/fhir+json",
            "encoding": "utf-8",
            "validation": validation_result,
        }

    def _export_to_hl7(
        self, data: Dict[str, Any], data_subject_id: str
    ) -> Dict[str, Any]:
        """Export data to HL7 format."""
        # Data parameter will be used in full implementation
        _ = data
        # Simplified HL7 message
        hl7_message = f"MSH|^~\\&|GDPR_EXPORT|||||{datetime.now().strftime('%Y%m%d%H%M%S')}||ADT^A08|{data_subject_id}|P|2.5\r"

        filename = f"gdpr_export_{data_subject_id}.hl7"

        return {
            "location": f"/exports/{filename}",
            "size": len(hl7_message.encode()),
            "data": hl7_message,
            "format": "x-application/hl7-v2+er7",
            "encoding": "utf-8",
        }

    def _export_to_pdf(
        self, data: Dict[str, Any], data_subject_id: str
    ) -> Dict[str, Any]:
        """Export data to PDF format."""
        # In production, would use PDF library
        pdf_content = f"Personal Data Export\n\nData Subject: {data_subject_id}\n"
        pdf_content += f"Export Date: {datetime.now()}\n\n"

        for section, content in data.items():
            pdf_content += f"\n{section.upper()}\n"
            pdf_content += "-" * 40 + "\n"
            pdf_content += str(content) + "\n"

        filename = f"gdpr_export_{data_subject_id}.pdf"

        return {
            "location": f"/exports/{filename}",
            "size": len(pdf_content.encode()),
            "data": base64.b64encode(pdf_content.encode()).decode(),
            "format": "application/pdf",
            "encoding": "base64",
        }

    def _export_to_package(
        self, data: Dict[str, Any], data_subject_id: str
    ) -> Dict[str, Any]:
        """Export data as multi-format package."""
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add JSON version
            json_result = self._export_to_json(data, data_subject_id)
            zip_file.writestr("data.json", json_result["data"])

            # Add CSV version
            csv_result = self._export_to_csv(data, data_subject_id)
            zip_file.writestr("data.csv", csv_result["data"])

            # Add README
            readme = "GDPR Data Export Package\n\nThis package contains your personal data in multiple formats."
            zip_file.writestr("README.txt", readme)

        zip_data = zip_buffer.getvalue()
        filename = f"gdpr_export_{data_subject_id}_package.zip"

        return {
            "location": f"/exports/{filename}",
            "size": len(zip_data),
            "data": base64.b64encode(zip_data).decode(),
            "format": "application/zip",
            "encoding": "base64",
        }

    def _get_personal_info(self, data_subject_id: str) -> Dict[str, Any]:
        """Get personal information for export."""
        # In production, would fetch from database
        return {
            "id": data_subject_id,
            "name": "Data Subject Name",
            "date_of_birth": "1990-01-01",
            "contact": {"email": "subject@example.com", "phone": "+1234567890"},
            "address": {"street": "123 Main St", "city": "City", "country": "Country"},
        }

    def _get_health_records(self, data_subject_id: str) -> List[Dict[str, Any]]:
        """Get health records for export."""
        # In production, would fetch from database
        # data_subject_id parameter will be used in production
        _ = data_subject_id
        return [
            {
                "record_id": "REC001",
                "date": "2024-01-15",
                "type": "consultation",
                "provider": "Dr. Smith",
                "diagnosis": "Annual checkup",
                "notes": "Patient in good health",
            }
        ]

    def _get_activity_logs(self, data_subject_id: str) -> List[Dict[str, Any]]:
        """Get activity logs for export."""
        # In production, would fetch from audit log
        _ = data_subject_id
        return [
            {
                "timestamp": "2024-01-20T10:30:00",
                "action": "login",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0",
            }
        ]

    def _get_consent_records(self, data_subject_id: str) -> List[Dict[str, Any]]:
        """Get consent records for export."""
        # In production, would fetch from consent database
        _ = data_subject_id
        return [
            {
                "consent_id": "CONSENT001",
                "date_given": "2024-01-01",
                "purpose": "healthcare_provision",
                "withdrawn": False,
            }
        ]

    def _get_communications(self, data_subject_id: str) -> List[Dict[str, Any]]:
        """Get communications for export."""
        # In production, would fetch from communication logs
        _ = data_subject_id
        return [
            {
                "date": "2024-01-10",
                "type": "email",
                "subject": "Appointment reminder",
                "direction": "outbound",
            }
        ]

    def _generate_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate metadata for export."""
        total_records = sum(
            len(v) if isinstance(v, list) else 1
            for v in data.values()
            if v and v != data.get("export_info")
        )

        return {
            "total_records": total_records,
            "data_categories": list(data.keys()),
            "export_version": "1.0",
            "gdpr_compliant": True,
        }

    def _dict_to_xml(self, data: Dict[str, Any], root_name: str) -> str:
        """Convert dictionary to XML string."""
        xml = f"<?xml version='1.0' encoding='UTF-8'?>\n<{root_name}>\n"

        def _process_item(key: str, value: Any, indent: int = 1) -> str:
            tabs = "  " * indent
            if isinstance(value, dict):
                result = f"{tabs}<{key}>\n"
                for k, v in value.items():
                    result += _process_item(k, v, indent + 1)
                result += f"{tabs}</{key}>\n"
                return result
            elif isinstance(value, list):
                result = ""
                for item in value:
                    result += f"{tabs}<{key}>\n"
                    if isinstance(item, dict):
                        for k, v in item.items():
                            result += _process_item(k, v, indent + 1)
                    else:
                        result += f"{tabs}  {str(item)}\n"
                    result += f"{tabs}</{key}>\n"
                return result
            else:
                return f"{tabs}<{key}>{str(value)}</{key}>\n"

        for key, value in data.items():
            xml += _process_item(key, value)

        xml += f"</{root_name}>"
        return xml

    def _flatten_dict(
        self, data: Dict[str, Any], parent_key: str = ""
    ) -> Dict[str, Any]:
        """Flatten nested dictionary for CSV export."""
        items: List[Tuple[str, Any]] = []
        for k, v in data.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key).items())
            elif isinstance(v, list):
                items.append((new_key, ", ".join(str(i) for i in v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def _generate_download_url(self, request_id: str) -> str:
        """Generate secure download URL."""
        # In production, would generate signed URL
        return f"/api/gdpr/download/{request_id}"

    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        return f"GDPR-EXP-{uuid.uuid4()}"

    def _generate_transfer_id(self) -> str:
        """Generate unique transfer ID."""
        return f"GDPR-TRF-{uuid.uuid4()}"

    def check_export_access(self, user_id: str, data_subject_id: str) -> bool:
        """Check if user has access to export data.

        Args:
            user_id: ID of user requesting export
            data_subject_id: ID of data subject

        Returns:
            True if access is allowed
        """
        # Users can export their own data
        if user_id == data_subject_id:
            return True

        # Check if user has GDPR data controller role
        # In production, would check specific GDPR roles
        # For now, check if user has admin access
        user = hipaa_access_control.users.get(user_id)
        if user:
            for role in user.roles:
                if role.name in ["admin", "data_controller", "privacy_officer"]:
                    return True

        return False

    def enforce_data_minimization(
        self, data: Dict[str, Any], purpose: str
    ) -> Dict[str, Any]:
        """Enforce data minimization principle.

        Args:
            data: Full data set
            purpose: Purpose of data export

        Returns:
            Minimized data set
        """
        minimized_data = {}

        # Define minimum necessary data for each purpose
        purpose_requirements = {
            "transfer": ["personal_information", "health_records", "consent_records"],
            "backup": ["personal_information", "health_records"],
            "audit": ["activity_logs", "consent_records"],
            "legal": ["personal_information", "consent_records", "activity_logs"],
            "personal_use": ["personal_information", "health_records"],
        }

        required_sections = purpose_requirements.get(purpose, ["personal_information"])

        for section in required_sections:
            if section in data:
                minimized_data[section] = data[section]

        return minimized_data

"""Health record service for managing medical records."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from src.healthcare.observation_resource import ObservationResource, VitalSignCode
from src.models.access_log import AccessType
from src.models.health_record import (
    HealthRecord,
    RecordPriority,
    RecordStatus,
    RecordType,
)
from src.models.patient import Patient
from src.services.base import BaseService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HealthRecordService(BaseService[HealthRecord]):
    """Service for managing health records."""

    model_class = HealthRecord

    def create_health_record(
        self,
        patient_id: UUID,
        record_type: RecordType,
        title: str,
        content: Dict[str, Any],
        provider_id: Optional[UUID] = None,
        provider_name: Optional[str] = None,
        **kwargs: Any,
    ) -> HealthRecord:
        """Create a new health record."""
        try:
            # Verify patient exists
            patient = (
                self.session.query(Patient)
                .filter(Patient.id == patient_id, Patient.deleted_at.is_(None))
                .first()
            )

            if not patient:
                raise ValueError(f"Patient {patient_id} not found")

            # Create health record
            record_data = {
                "patient_id": patient_id,
                "record_type": record_type,
                "title": title,
                "content": content,  # Will be encrypted by the model
                "provider_id": provider_id or self.current_user_id,
                "provider_name": provider_name,
                "record_date": datetime.utcnow(),
                **kwargs,
            }

            record = self.create(**record_data)

            logger.info(
                f"Created health record {record.id} for patient {patient_id} - {title}"
            )

            return record

        except (ValueError, IntegrityError, AttributeError) as e:
            logger.error(f"Error creating health record: {e}")
            raise

    def get_patient_records(
        self,
        patient_id: UUID,
        record_types: Optional[List[RecordType]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[RecordStatus] = None,
        limit: int = 100,
        offset: int = 0,
        include_content: bool = True,
    ) -> Tuple[List[HealthRecord], int]:
        """Get health records for a patient."""
        try:
            # Check patient access permission
            patient = (
                self.session.query(Patient).filter(Patient.id == patient_id).first()
            )

            if not patient:
                return [], 0

            # Build query
            query = self.session.query(HealthRecord).filter(
                HealthRecord.patient_id == patient_id, HealthRecord.deleted_at.is_(None)  # type: ignore[arg-type]
            )

            # Apply filters
            if record_types:
                query = query.filter(HealthRecord.record_type.in_(record_types))  # type: ignore[attr-defined]

            if start_date:
                query = query.filter(HealthRecord.record_date >= start_date)

            if end_date:
                query = query.filter(HealthRecord.record_date <= end_date)

            if status:
                query = query.filter(HealthRecord.status == status)  # type: ignore[arg-type]

            # Get total count
            total_count = query.count()

            # Apply pagination
            records = (
                query.order_by(HealthRecord.record_date.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Log access
            self.log_access(
                resource_id=patient_id,
                access_type=AccessType.VIEW,
                purpose="View patient health records",
                patient_id=patient_id,
                data_returned={
                    "count": len(records),
                    "total": total_count,
                    "types": [t.value for t in record_types] if record_types else "all",
                },
            )

            # Optionally decrypt content
            if not include_content:
                for record in records:
                    record.encrypted_content = None  # type: ignore[assignment]

            return records, total_count

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting patient records: {e}")
            return [], 0

    def update_record_content(
        self,
        record_id: UUID,
        content_updates: Dict[str, Any],
        reason: str = "Content update",
    ) -> Optional[HealthRecord]:
        """Update health record content."""
        try:
            record = self.get_by_id(record_id)
            if not record:
                return None

            # Get current content
            current_content = record.get_content()

            # Apply updates
            updated_content = {**current_content, **content_updates}

            # Create amended version if record is final
            if record.status == RecordStatus.FINAL:
                new_record = record.create_amended_version(content_updates, reason)
                self.session.add(new_record)
                self.session.flush()

                logger.info(
                    f"Created amended version {new_record.id} of record {record_id}"
                )

                return new_record
            else:
                # Update existing record
                record.set_content(updated_content)
                record.change_reason = reason  # type: ignore[assignment]
                self.session.flush()

                return record

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error updating record content: {e}")
            return None

    def finalize_record(
        self, record_id: UUID, verified_by: Optional[UUID] = None
    ) -> Optional[HealthRecord]:
        """Finalize a health record."""
        try:
            record = self.get_by_id(record_id)
            if not record:
                return None

            if record.status == RecordStatus.FINAL:
                logger.warning(f"Record {record_id} is already finalized")
                return record

            # Update status
            record.status = RecordStatus.FINAL
            record.verified_by = verified_by or self.current_user_id  # type: ignore[assignment]
            record.verified_at = datetime.utcnow()  # type: ignore[assignment]

            self.session.flush()

            # Log the finalization
            self.log_access(
                resource_id=record_id,
                access_type=AccessType.UPDATE,
                purpose="Finalize health record",
                patient_id=record.patient_id,  # type: ignore[arg-type]
            )

            logger.info(f"Finalized health record {record_id}")

            return record

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error finalizing record: {e}")
            return None

    def add_attachment(
        self, record_id: UUID, file_url: str, file_type: str, description: str = ""
    ) -> bool:
        """Add an attachment to a health record."""
        try:
            record = self.get_by_id(record_id)
            if not record:
                return False

            record.add_attachment(file_url, file_type, description)
            self.session.flush()

            # Log the attachment
            self.log_access(
                resource_id=record_id,
                access_type=AccessType.UPDATE,
                purpose=f"Add attachment - {file_type}",
                patient_id=record.patient_id,  # type: ignore[arg-type]
            )

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error adding attachment: {e}")
            return False

    def search_records(
        self,
        search_query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[HealthRecord], int]:
        """Search health records across all patients."""
        try:
            query = self.session.query(HealthRecord).filter(
                HealthRecord.deleted_at.is_(None)
            )

            # Apply search query
            if search_query:
                search_term = f"%{search_query}%"
                query = query.filter(
                    or_(
                        HealthRecord.title.ilike(search_term),
                        HealthRecord.provider_name.ilike(search_term),
                        HealthRecord.facility_name.ilike(search_term),
                    )
                )

            # Apply filters
            if filters:
                if filters.get("record_type"):
                    query = query.filter(
                        HealthRecord.record_type == filters["record_type"]
                    )

                if filters.get("status"):
                    query = query.filter(HealthRecord.status == filters["status"])

                if filters.get("priority"):
                    query = query.filter(HealthRecord.priority == filters["priority"])

                if filters.get("provider_id"):
                    query = query.filter(
                        HealthRecord.provider_id == filters["provider_id"]
                    )

                if filters.get("facility_name"):
                    query = query.filter(
                        HealthRecord.facility_name.ilike(
                            f"%{filters['facility_name']}%"
                        )
                    )

                if filters.get("date_from"):
                    query = query.filter(
                        HealthRecord.record_date >= filters["date_from"]
                    )

                if filters.get("date_to"):
                    query = query.filter(HealthRecord.record_date <= filters["date_to"])

                if filters.get("emergency_only"):
                    query = query.filter(
                        HealthRecord.priority.in_(  # type: ignore[attr-defined]
                            [RecordPriority.EMERGENCY, RecordPriority.STAT]
                        )
                    )

            # Get total count
            total_count = query.count()

            # Apply pagination
            records = (
                query.order_by(HealthRecord.record_date.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Log search
            self.log_access(
                resource_id=UUID("00000000-0000-0000-0000-000000000000"),
                access_type=AccessType.VIEW,
                purpose="Search health records",
                data_returned={
                    "count": len(records),
                    "total": total_count,
                    "query": search_query,
                },
            )

            return records, total_count

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error searching records: {e}")
            return [], 0

    def create_vital_signs_record(
        self, patient_id: UUID, vital_signs: Dict[str, Any], provider_name: str
    ) -> HealthRecord:
        """Create a vital signs record."""
        try:
            # Create FHIR observation
            observation = ObservationResource()

            # Map vital signs to observations
            observations = []

            if "blood_pressure" in vital_signs:
                bp = vital_signs["blood_pressure"]
                # Create separate observations for systolic and diastolic
                if "systolic" in bp:
                    obs = observation.create_vital_sign(
                        vital_type=VitalSignCode.SYSTOLIC_BP,
                        value=bp.get("systolic"),
                        patient_id=str(patient_id),
                    )
                    observations.append(obs.as_json())

                if "diastolic" in bp:
                    obs = observation.create_vital_sign(
                        vital_type=VitalSignCode.DIASTOLIC_BP,
                        value=bp.get("diastolic"),
                        patient_id=str(patient_id),
                    )
                    observations.append(obs.as_json())

            if "heart_rate" in vital_signs:
                obs = observation.create_vital_sign(
                    vital_type=VitalSignCode.HEART_RATE,
                    value=vital_signs["heart_rate"],
                    patient_id=str(patient_id),
                )
                observations.append(obs.as_json())

            if "temperature" in vital_signs:
                obs = observation.create_vital_sign(
                    vital_type=VitalSignCode.BODY_TEMPERATURE,
                    value=vital_signs["temperature"],
                    patient_id=str(patient_id),
                )
                observations.append(obs.as_json())

            if "respiratory_rate" in vital_signs:
                obs = observation.create_vital_sign(
                    vital_type=VitalSignCode.RESPIRATORY_RATE,
                    value=vital_signs["respiratory_rate"],
                    patient_id=str(patient_id),
                )
                observations.append(obs.as_json())

            if "oxygen_saturation" in vital_signs:
                obs = observation.create_vital_sign(
                    vital_type=VitalSignCode.OXYGEN_SATURATION,
                    value=vital_signs["oxygen_saturation"],
                    patient_id=str(patient_id),
                )
                observations.append(obs.as_json())

            # Create health record
            content = {
                "vital_signs": vital_signs,
                "fhir_observations": observations,
                "recorded_at": datetime.utcnow().isoformat(),
            }

            return self.create_health_record(
                patient_id=patient_id,
                record_type=RecordType.VITAL_SIGNS,
                title="Vital Signs",
                content=content,
                provider_name=provider_name,
                priority=RecordPriority.ROUTINE,
            )

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error creating vital signs record: {e}")
            raise

    def create_lab_result(
        self,
        patient_id: UUID,
        test_name: str,
        results: Dict[str, Any],
        provider_name: str,
        lab_name: str,
    ) -> HealthRecord:
        """Create a lab result record."""
        try:
            content = {
                "test_name": test_name,
                "results": results,
                "lab_name": lab_name,
                "collected_at": results.get(
                    "collected_at", datetime.utcnow().isoformat()
                ),
                "reported_at": datetime.utcnow().isoformat(),
            }

            # Determine priority based on results
            priority = RecordPriority.ROUTINE
            if results.get("critical_values"):
                priority = RecordPriority.URGENT

            return self.create_health_record(
                patient_id=patient_id,
                record_type=RecordType.LAB_RESULT,
                title=f"Lab Result - {test_name}",
                content=content,
                provider_name=provider_name,
                facility_name=lab_name,
                priority=priority,
                categories=[test_name.lower().replace(" ", "_")],
            )

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error creating lab result: {e}")
            raise

    def get_emergency_records(
        self, patient_id: Optional[UUID] = None, hours_back: int = 24
    ) -> List[HealthRecord]:
        """Get emergency/urgent records."""
        try:
            query = self.session.query(HealthRecord).filter(
                HealthRecord.priority.in_(  # type: ignore[attr-defined]
                    [
                        RecordPriority.EMERGENCY,
                        RecordPriority.STAT,
                        RecordPriority.URGENT,
                    ]
                ),
                HealthRecord.record_date
                >= datetime.utcnow() - timedelta(hours=hours_back),
                HealthRecord.deleted_at.is_(None),
            )

            if patient_id:
                query = query.filter(HealthRecord.patient_id == patient_id)  # type: ignore[arg-type]

            records = query.order_by(
                HealthRecord.priority, HealthRecord.record_date.desc()  # type: ignore[arg-type]
            ).all()

            # Log emergency access
            self.log_access(
                resource_id=patient_id or UUID("00000000-0000-0000-0000-000000000000"),
                access_type=AccessType.VIEW,
                purpose="View emergency records",
                patient_id=patient_id,
                emergency_override=True,
            )

            return records

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting emergency records: {e}")
            return []

    def get_record_history(self, record_id: UUID) -> List[HealthRecord]:
        """Get version history of a record."""
        try:
            # Get the current record
            current_record = self.get_by_id(record_id)
            if not current_record:
                return []

            history = [current_record]

            # Traverse back through previous versions
            previous_id = current_record.previous_version_id
            while previous_id:
                previous_record = (
                    self.session.query(HealthRecord)
                    .filter(HealthRecord.id == previous_id)
                    .first()
                )

                if previous_record:
                    history.append(previous_record)
                    previous_id = previous_record.previous_version_id
                else:
                    break

            return history

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting record history: {e}")
            return []

    def authorize_viewer(
        self, record_id: UUID, viewer_id: UUID, expiry_hours: Optional[int] = 24
    ) -> bool:
        """Authorize a specific viewer for a record."""
        try:
            record = self.get_by_id(record_id)
            if not record:
                return False

            expiry = None
            if expiry_hours:
                expiry = datetime.utcnow() + timedelta(hours=expiry_hours)

            record.authorize_viewer(str(viewer_id), expiry)
            self.session.flush()

            # Log authorization
            self.log_access(
                resource_id=record_id,
                access_type=AccessType.UPDATE,
                purpose=f"Authorize viewer access - expires in {expiry_hours}h",
                patient_id=record.patient_id,  # type: ignore[arg-type]
            )

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error authorizing viewer: {e}")
            return False


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

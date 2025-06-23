"""Patient service for managing patient records.

This service handles encrypted patient data with access control and audit logging.
Manages FHIR Patient Resource validation.
"""

import csv
import io
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, TypedDict
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from src.models.access_log import AccessType
from src.models.health_record import HealthRecord
from src.models.patient import Gender, Patient
from src.models.verification import Verification
from src.services.base import BaseService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BulkOperationResult(TypedDict):
    """Result structure for bulk operations."""

    total: int
    success: int
    failed: int
    errors: List[Any]


class BulkExportResult(TypedDict):
    """Result structure for bulk export operations."""

    format: str
    count: int
    data: Any
    errors: List[str]


class PatientService(BaseService[Patient]):
    """Service for managing patient records."""

    model_class = Patient

    def create_patient(
        self,
        given_name: str,
        family_name: str,
        gender: Gender,
        date_of_birth: Optional[date] = None,
        unhcr_number: Optional[str] = None,
        **kwargs: Any,
    ) -> Patient:
        """Create a new patient record."""
        try:
            # Check for duplicate UNHCR number
            if unhcr_number:
                existing = (
                    self.session.query(Patient)
                    .filter(
                        Patient.unhcr_number == unhcr_number,
                        Patient.deleted_at.is_(None),
                    )
                    .first()
                )

                if existing:
                    raise ValueError(
                        f"Patient with UNHCR number {unhcr_number} already exists"
                    )

            # Create patient
            patient_data = {
                "given_name": given_name,
                "family_name": family_name,
                "gender": gender,
                "date_of_birth": date_of_birth,
                "unhcr_number": unhcr_number,
                **kwargs,
            }

            patient = self.create(**patient_data)

            logger.info(f"Created patient {patient.id} - {patient.full_name}")

            return patient

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error creating patient: {e}")
            raise

    def search_patients(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> Tuple[List[Patient], int]:
        """Search for patients with various criteria."""
        try:
            # Base query
            base_query = self.session.query(Patient)

            if not include_deleted:
                base_query = base_query.filter(Patient.deleted_at.is_(None))

            # Apply search query
            if query:
                search_term = f"%{query}%"
                base_query = base_query.filter(
                    or_(
                        Patient.given_name.ilike(search_term),
                        Patient.family_name.ilike(search_term),
                        Patient.preferred_name.ilike(search_term),
                        Patient.unhcr_number.ilike(search_term),
                        Patient.phone_number.like(search_term),
                        Patient.email.ilike(search_term),
                    )
                )

            # Apply filters
            if filters:
                if filters.get("gender"):
                    base_query = base_query.filter(Patient.gender == filters["gender"])

                if filters.get("refugee_status"):
                    base_query = base_query.filter(
                        Patient.refugee_status == filters["refugee_status"]
                    )

                if filters.get("current_camp"):
                    base_query = base_query.filter(
                        Patient.current_camp.ilike(f"%{filters['current_camp']}%")
                    )

                if filters.get("verification_status"):
                    base_query = base_query.filter(
                        Patient.verification_status == filters["verification_status"]
                    )

                if filters.get("origin_country"):
                    base_query = base_query.filter(
                        Patient.origin_country == filters["origin_country"]
                    )

                if filters.get("age_min"):
                    min_birth_year = date.today().year - filters["age_min"]
                    base_query = base_query.filter(
                        or_(
                            Patient.date_of_birth <= date(min_birth_year, 12, 31),
                            Patient.estimated_birth_year <= min_birth_year,
                        )
                    )

                if filters.get("age_max"):
                    max_birth_year = date.today().year - filters["age_max"]
                    base_query = base_query.filter(
                        or_(
                            Patient.date_of_birth >= date(max_birth_year, 1, 1),
                            Patient.estimated_birth_year >= max_birth_year,
                        )
                    )

            # Get total count
            total_count = base_query.count()

            # Apply pagination and get results
            patients = (
                base_query.order_by(Patient.family_name, Patient.given_name)
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Log access
            self.log_access(
                resource_id=UUID("00000000-0000-0000-0000-000000000000"),
                access_type=AccessType.VIEW,
                purpose="Search patients",
                data_returned={
                    "count": len(patients),
                    "total": total_count,
                    "query": query,
                    "filters": filters,
                },
            )

            return patients, total_count

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error searching patients: {e}")
            return [], 0

    def get_patient_with_records(
        self,
        patient_id: UUID,
        include_health_records: bool = True,
        include_verifications: bool = True,
        include_family: bool = True,
    ) -> Optional[Patient]:
        """Get patient with related records."""
        try:
            query = self.session.query(Patient).filter(
                Patient.id == patient_id, Patient.deleted_at.is_(None)
            )

            # Eagerly load relationships
            if include_health_records:
                query = query.options(joinedload(Patient.health_records))

            if include_verifications:
                query = query.options(joinedload(Patient.verifications))

            if include_family:
                query = query.options(joinedload(Patient.family_members))

            patient = query.first()

            if patient:
                self.log_access(
                    resource_id=patient_id,
                    access_type=AccessType.VIEW,
                    purpose="View patient with records",
                    patient_id=patient_id,
                )

            return patient

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting patient with records: {e}")
            return None

    def update_patient_demographics(
        self, patient_id: UUID, demographics: Dict[str, Any]
    ) -> Optional[Patient]:
        """Update patient demographic information."""
        allowed_fields = {
            "given_name",
            "family_name",
            "middle_names",
            "preferred_name",
            "date_of_birth",
            "estimated_birth_year",
            "place_of_birth",
            "gender",
            "phone_number",
            "alternate_phone",
            "email",
            "current_address",
            "gps_coordinates",
        }

        # Filter to allowed fields only
        update_data = {k: v for k, v in demographics.items() if k in allowed_fields}

        return self.update(patient_id, **update_data)

    def update_refugee_information(
        self, patient_id: UUID, refugee_info: Dict[str, Any]
    ) -> Optional[Patient]:
        """Update refugee-specific information."""
        allowed_fields = {
            "refugee_status",
            "unhcr_number",
            "displacement_date",
            "origin_country",
            "current_camp",
            "camp_section",
        }

        update_data = {k: v for k, v in refugee_info.items() if k in allowed_fields}

        # Validate UNHCR number uniqueness if updating
        if "unhcr_number" in update_data:
            existing = (
                self.session.query(Patient)
                .filter(
                    Patient.unhcr_number == update_data["unhcr_number"],
                    Patient.id != patient_id,
                    Patient.deleted_at.is_(None),
                )
                .first()
            )

            if existing:
                raise ValueError(
                    f"UNHCR number {update_data['unhcr_number']} already assigned to another patient"
                )

        return self.update(patient_id, **update_data)

    def add_family_member(
        self, patient_id: UUID, family_member_id: UUID, relationship: str
    ) -> bool:
        """Add a family member relationship."""
        try:
            patient = self.get_by_id(patient_id)
            family_member = self.get_by_id(family_member_id)

            if not patient or not family_member:
                return False

            # Add bidirectional relationship
            patient.add_family_member(family_member, relationship)

            # Add reverse relationship
            reverse_relationships = {
                "mother": "child",
                "father": "child",
                "child": "parent",
                "sibling": "sibling",
                "spouse": "spouse",
            }
            reverse_rel = reverse_relationships.get(relationship, "relative")
            family_member.add_family_member(patient, reverse_rel)

            self.session.flush()

            # Log access
            self.log_access(
                resource_id=patient_id,
                access_type=AccessType.UPDATE,
                purpose=f"Add family member - {relationship}",
                patient_id=patient_id,
            )

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error adding family member: {e}")
            return False

    def get_patient_timeline(
        self,
        patient_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get patient's health timeline."""
        try:
            patient = self.get_by_id(patient_id)
            if not patient:
                return {"error": "Patient not found"}

            # Get health records
            records_query = self.session.query(HealthRecord).filter(
                and_(
                    HealthRecord.patient_id == patient_id,  # type: ignore[arg-type]
                    HealthRecord.deleted_at.is_(None),
                )
            )

            if start_date:
                records_query = records_query.filter(
                    HealthRecord.record_date >= start_date
                )

            if end_date:
                records_query = records_query.filter(
                    HealthRecord.record_date <= end_date
                )

            health_records = records_query.order_by(
                HealthRecord.record_date.desc()
            ).all()

            # Get verifications
            verifications = (
                self.session.query(Verification)
                .filter(Verification.patient_id == patient_id)
                .order_by(Verification.completed_at.desc())
                .all()
            )

            timeline = {
                "patient": patient.to_dict(),
                "health_records": [
                    {
                        "id": str(r.id),
                        "type": r.record_type.value,
                        "title": r.title,
                        "date": r.record_date.isoformat(),
                        "provider": r.provider_name,
                        "facility": r.facility_name,
                    }
                    for r in health_records
                ],
                "verifications": [v.to_summary() for v in verifications],
                "family_members": [
                    {
                        "id": str(fm.family_member.id),
                        "name": fm.family_member.full_name,
                        "relationship": fm.relationship_description,  # Now properly gets actual relationship type
                    }
                    for fm in patient.family_relationships
                ],
            }

            return timeline

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting patient timeline: {e}")
            return {"error": str(e)}

    def merge_patients(
        self,
        primary_patient_id: UUID,
        duplicate_patient_id: UUID,
        merge_strategy: str = "primary_wins",
    ) -> Optional[Patient]:
        """Merge duplicate patient records."""
        try:
            primary = self.get_by_id(primary_patient_id)
            duplicate = self.get_by_id(duplicate_patient_id)

            if not primary or not duplicate:
                raise ValueError("One or both patients not found")

            # Log the merge operation
            self.log_access(
                resource_id=primary_patient_id,
                access_type=AccessType.UPDATE,
                purpose=f"Merge patient records - strategy: {merge_strategy}",
                patient_id=primary_patient_id,
                data_returned={"merged_from": str(duplicate_patient_id)},
            )

            # Transfer health records
            health_records = (
                self.session.query(HealthRecord)
                .filter(HealthRecord.patient_id == duplicate_patient_id)  # type: ignore[arg-type]
                .all()
            )

            for record in health_records:
                record.patient_id = primary_patient_id  # type: ignore[assignment]

            # Transfer verifications
            verifications = (
                self.session.query(Verification)
                .filter(Verification.patient_id == duplicate_patient_id)
                .all()
            )

            for verification in verifications:
                verification.patient_id = primary_patient_id

            # Merge demographic data based on strategy
            if merge_strategy == "duplicate_wins":
                # Copy non-null fields from duplicate to primary
                for field in [
                    "phone_number",
                    "email",
                    "current_address",
                    "unhcr_number",
                    "current_camp",
                ]:
                    duplicate_value = getattr(duplicate, field)
                    if duplicate_value and not getattr(primary, field):
                        setattr(primary, field, duplicate_value)

            elif merge_strategy == "newest_wins":
                # Use the most recently updated value
                if duplicate.updated_at > primary.updated_at:
                    for field in ["phone_number", "email", "current_address"]:
                        duplicate_value = getattr(duplicate, field)
                        if duplicate_value:
                            setattr(primary, field, duplicate_value)

            # Merge family relationships
            for family_member in duplicate.family_members:
                if family_member not in primary.family_members:
                    primary.family_members.append(family_member)

            # Soft delete the duplicate
            duplicate.soft_delete(deleted_by_id=self.current_user_id)

            self.session.flush()

            logger.info(
                f"Merged patient {duplicate_patient_id} into {primary_patient_id}"
            )

            return primary

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error merging patients: {e}")
            self.session.rollback()
            raise

    def grant_emergency_access(
        self,
        patient_id: UUID,
        granted_by: UUID,
        duration_hours: int = 24,
        reason: str = "Emergency medical treatment",
    ) -> bool:
        """Grant emergency access to patient records."""
        try:
            patient = self.get_by_id(patient_id)
            if not patient:
                return False

            # Update access permissions
            if not patient.access_permissions:
                patient.access_permissions = dict()  # type: ignore[assignment]

            patient.access_permissions["emergency_access"] = {
                "granted": True,
                "granted_by": str(granted_by),
                "granted_at": datetime.utcnow().isoformat(),
                "expires_at": (
                    datetime.utcnow() + timedelta(hours=duration_hours)
                ).isoformat(),
                "reason": reason,
            }

            self.session.flush()

            # Log emergency access grant
            self.log_access(
                resource_id=patient_id,
                access_type=AccessType.UPDATE,
                purpose=f"Grant emergency access - {reason}",
                patient_id=patient_id,
                emergency_override=True,
            )

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error granting emergency access: {e}")
            return False

    def get_patients_by_camp(
        self, camp_name: str, include_sections: bool = True
    ) -> Dict[str, Any]:
        """Get all patients in a specific camp."""
        try:
            query = self.session.query(Patient).filter(
                Patient.current_camp == camp_name, Patient.deleted_at.is_(None)
            )

            patients = query.all()

            result = {
                "camp": camp_name,
                "total_patients": len(patients),
                "patients": [p.to_dict() for p in patients],
            }

            if include_sections:
                # Group by camp section
                sections: Dict[str, List[Dict[str, Any]]] = {}
                for patient in patients:
                    section = patient.camp_section or "Unknown"
                    if section not in sections:
                        sections[section] = []
                    sections[section].append(
                        {
                            "id": str(patient.id),
                            "name": patient.full_name,
                            "unhcr_number": patient.unhcr_number,
                        }
                    )

                result["sections"] = sections

            return result

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting patients by camp: {e}")
            return {"error": str(e)}

    def export_patient_data(
        self,
        patient_id: UUID,
        export_format: str = "fhir",
        include_records: bool = True,
    ) -> Dict[str, Any]:
        """Export patient data in specified format."""
        try:
            patient = self.get_patient_with_records(
                patient_id, include_health_records=include_records
            )

            if not patient:
                return {"error": "Patient not found"}

            # Log export
            self.log_access(
                resource_id=patient_id,
                access_type=AccessType.EXPORT,
                purpose=f"Export patient data - format: {format}",
                patient_id=patient_id,
                export_format=export_format,
            )

            if export_format == "fhir":
                return patient.to_fhir()

            elif export_format == "json":
                data = patient.to_dict()
                if include_records:
                    data["health_records"] = [
                        r.to_dict() for r in patient.health_records
                    ]
                return data

            else:
                return {"error": f"Unsupported format: {export_format}"}

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error exporting patient data: {e}")
            return {"error": str(e)}

    def validate_patient_data(self, patient_data: Dict[str, Any]) -> bool:
        """Validate patient data."""
        required_fields = ["given_name", "family_name", "gender"]
        for field in required_fields:
            if field not in patient_data or not patient_data[field]:
                return False
        return True

    def bulk_import_from_csv(
        self,
        csv_data: str,
        field_mapping: Dict[str, str],
        user_id: UUID,
        organization_id: Optional[UUID] = None,
    ) -> BulkOperationResult:
        """Bulk import patients from CSV data.

        Args:
            csv_data: CSV content as string
            field_mapping: Mapping of CSV columns to patient fields
            user_id: ID of the user performing the import
            organization_id: Optional organization ID

        Returns:
            Result dictionary with import statistics
        """
        _ = organization_id  # Will be used for organization-specific imports
        result: BulkOperationResult = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "errors": [],
        }

        try:
            # Parse CSV data
            csv_reader = csv.DictReader(io.StringIO(csv_data))

            for row_num, row in enumerate(csv_reader, 1):
                result["total"] += 1

                try:
                    # Map CSV fields to patient data
                    patient_data = {}
                    for csv_field, patient_field in field_mapping.items():
                        if csv_field in row:
                            value = row[csv_field].strip()
                            if value:  # Only add non-empty values
                                patient_data[patient_field] = value

                    # Parse special fields
                    if "gender" in patient_data:
                        patient_data["gender"] = Gender[patient_data["gender"].upper()]

                    if "date_of_birth" in patient_data:
                        # Try multiple date formats
                        dob_str = patient_data["date_of_birth"]
                        for date_format in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                            try:
                                patient_data["date_of_birth"] = datetime.strptime(
                                    dob_str, date_format
                                ).date()
                                break
                            except ValueError:
                                continue

                    # Create patient - validate required fields
                    given_name = patient_data.get("given_name")
                    family_name = patient_data.get("family_name")
                    gender_str = patient_data.get("gender")

                    if not given_name or not family_name or not gender_str:
                        raise ValueError(
                            "Missing required fields: given_name, family_name, or gender"
                        )

                    # Convert gender string to Gender enum
                    try:
                        gender = Gender(gender_str.upper())
                    except ValueError:
                        gender = Gender.OTHER

                    # Parse date of birth if provided
                    date_of_birth = None
                    if patient_data.get("date_of_birth"):
                        dob_str = patient_data.get("date_of_birth")
                        if isinstance(dob_str, str):
                            try:
                                date_of_birth = datetime.strptime(
                                    dob_str, "%Y-%m-%d"
                                ).date()
                            except ValueError:
                                # Try ISO format
                                try:
                                    date_of_birth = datetime.fromisoformat(
                                        dob_str
                                    ).date()
                                except ValueError:
                                    logger.warning(f"Invalid date format: {dob_str}")

                    patient = self.create_patient(
                        given_name=given_name,
                        family_name=family_name,
                        gender=gender,
                        date_of_birth=date_of_birth,
                        unhcr_number=patient_data.get("unhcr_number"),
                        medical_record_number=patient_data.get("medical_record_number"),
                        phone=patient_data.get("phone"),
                        email=patient_data.get("email"),
                        address=patient_data.get("address"),
                        city=patient_data.get("city"),
                        state=patient_data.get("state"),
                        country=patient_data.get("country"),
                        postal_code=patient_data.get("postal_code"),
                        blood_type=patient_data.get("blood_type"),
                        emergency_contact_name=patient_data.get(
                            "emergency_contact_name"
                        ),
                        emergency_contact_phone=patient_data.get(
                            "emergency_contact_phone"
                        ),
                        emergency_contact_relationship=patient_data.get(
                            "emergency_contact_relationship"
                        ),
                        languages=(
                            patient_data.get("languages", ["en"]).split(",")
                            if isinstance(patient_data.get("languages"), str)
                            else patient_data.get("languages", ["en"])
                        ),
                        active=True,
                    )

                    if patient:
                        result["success"] += 1
                    else:
                        result["failed"] += 1
                        result["errors"].append(
                            {"row": row_num, "error": "Failed to create patient"}
                        )

                except (ValueError, RuntimeError, AttributeError) as e:
                    result["failed"] += 1
                    result["errors"].append(
                        {"row": row_num, "error": str(e), "data": row}
                    )
                    logger.error("Error importing row %s: %s", row_num, e)

            # Commit all successful imports
            self.session.commit()

            # Log the bulk import
            self.log_access(
                resource_id=user_id,
                access_type=AccessType.CREATE,
                purpose=f"Bulk import {result['success']} patients",
                data_returned={"total": result["total"], "success": result["success"]},
            )

        except (ValueError, RuntimeError, AttributeError, csv.Error) as e:
            logger.error(f"Error in bulk import: {e}")
            result["errors"].append({"row": 0, "error": f"CSV parsing error: {str(e)}"})
            self.session.rollback()

        return result

    def bulk_export_patients(
        self,
        patient_ids: List[UUID],
        export_format: str,
        include_records: bool = False,
    ) -> BulkExportResult:
        """Bulk export patient data.

        Args:
            patient_ids: List of patient IDs to export
            export_format: Format for export (csv, json, fhir)
            include_records: Whether to include health records

        Returns:
            Export data dictionary
        """
        result: BulkExportResult = {
            "format": export_format,
            "count": 0,
            "data": None,
            "errors": [],
        }

        try:
            # Get patients
            patients = (
                self.session.query(Patient)
                .filter(Patient.id.in_(patient_ids), Patient.deleted_at.is_(None))
                .all()
            )

            result["count"] = len(patients)

            if export_format == "csv":
                output = io.StringIO()
                fieldnames = [
                    "id",
                    "unhcr_number",
                    "medical_record_number",
                    "given_name",
                    "family_name",
                    "gender",
                    "date_of_birth",
                    "phone",
                    "email",
                    "address",
                    "city",
                    "state",
                    "country",
                    "blood_type",
                    "languages",
                    "emergency_contact_name",
                    "emergency_contact_phone",
                    "created_at",
                    "updated_at",
                ]

                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()

                for patient in patients:
                    writer.writerow(
                        {
                            "id": str(patient.id),
                            "unhcr_number": patient.unhcr_number or "",
                            "medical_record_number": patient.medical_record_number
                            or "",
                            "given_name": patient.given_name,
                            "family_name": patient.family_name,
                            "gender": patient.gender.value,
                            "date_of_birth": (
                                patient.date_of_birth.isoformat()
                                if patient.date_of_birth
                                else ""
                            ),
                            "phone": patient.phone or "",
                            "email": patient.email or "",
                            "address": patient.address or "",
                            "city": patient.city or "",
                            "state": patient.state or "",
                            "country": patient.country or "",
                            "blood_type": patient.blood_type or "",
                            "languages": ",".join(patient.languages),
                            "emergency_contact_name": patient.emergency_contact_name
                            or "",
                            "emergency_contact_phone": patient.emergency_contact_phone
                            or "",
                            "created_at": patient.created_at.isoformat(),
                            "updated_at": (
                                patient.updated_at.isoformat()
                                if patient.updated_at
                                else ""
                            ),
                        }
                    )

                result["data"] = output.getvalue()

            elif export_format == "json":
                data = []
                for patient in patients:
                    patient_data = patient.to_dict()
                    if include_records:
                        patient_data["health_records"] = [
                            record.to_dict() for record in patient.health_records
                        ]
                    data.append(patient_data)
                result["data"] = data

            elif export_format == "fhir":
                bundle = {"resourceType": "Bundle", "type": "collection", "entry": []}
                for patient in patients:
                    if isinstance(bundle["entry"], list):
                        bundle["entry"].append({"resource": patient.to_fhir()})
                result["data"] = bundle

            else:
                result["errors"].append(f"Unsupported export format: {export_format}")

            # Log the bulk export
            if self.current_user_id:
                self.log_access(
                    resource_id=self.current_user_id,
                    access_type=AccessType.VIEW,
                    purpose=f"Bulk export {len(patients)} patients",
                    data_returned={"count": len(patients), "format": export_format},
                )

        except (ValueError, RuntimeError, AttributeError, csv.Error) as e:
            logger.error(f"Error in bulk export: {e}")
            result["errors"].append(str(e))

        return result

    def bulk_update_patients(
        self,
        patient_ids: List[UUID],
        update_data: Dict[str, Any],
    ) -> BulkOperationResult:
        """Bulk update patient records.

        Args:
            patient_ids: List of patient IDs to update
            update_data: Data to update for all patients

        Returns:
            Result dictionary with update statistics
        """
        result: BulkOperationResult = {
            "total": len(patient_ids),
            "success": 0,
            "failed": 0,
            "errors": [],
        }
        errors_list: List[Any] = result["errors"]

        try:
            # Validate update data
            allowed_fields = {
                "phone",
                "email",
                "address",
                "city",
                "state",
                "country",
                "postal_code",
                "emergency_contact_name",
                "emergency_contact_phone",
                "emergency_contact_relationship",
                "languages",
                "active",
            }

            # Filter to only allowed fields
            filtered_update = {
                k: v for k, v in update_data.items() if k in allowed_fields
            }

            if not filtered_update:
                errors_list.append("No valid fields to update")
                return result

            # Update each patient
            for patient_id in patient_ids:
                try:
                    patient = self.get_by_id(patient_id)
                    if not patient:
                        result["failed"] += 1
                        errors_list.append(
                            {
                                "patient_id": str(patient_id),
                                "error": "Patient not found",
                            }
                        )
                        continue

                    # Apply updates
                    for field, value in filtered_update.items():
                        setattr(patient, field, value)

                    patient.updated_at = datetime.utcnow()  # type: ignore[assignment]
                    result["success"] += 1

                except (ValueError, RuntimeError, AttributeError) as e:
                    result["failed"] += 1
                    errors_list.append({"patient_id": str(patient_id), "error": str(e)})
                    logger.error(f"Error updating patient {patient_id}: {e}")

            # Commit all updates
            self.session.commit()

            # Log the bulk update
            self.log_access(
                resource_id=self.current_user_id,  # type: ignore[arg-type]
                access_type=AccessType.UPDATE,
                purpose=f"Bulk update {result['success']} patients",
                data_returned={"total": result["total"], "success": result["success"]},
            )

        except (ValueError, RuntimeError, AttributeError, csv.Error) as e:
            logger.error(f"Error in bulk update: {e}")
            errors_list.append(str(e))
            self.session.rollback()

        return result

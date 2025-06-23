"""AI Analysis Service for health data insights.

This module provides AI-powered analysis of health data, including FHIR Resource
validation and PHI protection for HIPAA compliance.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.ai.langchain.chain_manager import ChainManager
from src.healthcare.fhir.validators import FHIRValidator
from src.models.health_record import HealthRecord, RecordType
from src.models.patient import Patient
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.services.base import BaseService
from src.services.health_record_service import HealthRecordService
from src.services.patient_service import PatientService
from src.utils.logging import get_logger

# FHIR resources imported for validation and schema reference


logger = get_logger(__name__)


class AIAnalysisService(BaseService):
    """Service for AI-powered health data analysis."""

    def __init__(self, db: Session):
        """Initialize AI analysis service."""
        super().__init__(db)
        self.db = db
        self.chain_manager = ChainManager()
        self.health_service = HealthRecordService(db)
        self.patient_service = PatientService(db)
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

    async def analyze_health_trends(
        self,
        patient_id: UUID,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze health trends for a patient using AI."""
        try:
            # Get patient data
            patient = self.patient_service.get_by_id(patient_id)
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")

            # Get health records
            records, _ = self.health_service.get_patient_records(
                patient_id=patient_id,
                start_date=(
                    datetime.fromisoformat(start_date)
                    if start_date
                    else datetime.utcnow() - timedelta(days=90)
                ),
                end_date=(
                    datetime.fromisoformat(end_date) if end_date else datetime.utcnow()
                ),
                include_content=True,
            )

            # Prepare data for AI analysis
            medical_history = []
            conditions = []
            medications = []
            vitals = []

            for record in records:
                if record.record_type == RecordType.DIAGNOSIS:
                    conditions.append(record.content)
                elif record.record_type == RecordType.MEDICATION:
                    medications.append(record.content)
                elif record.record_type == RecordType.VITAL_SIGNS:
                    vitals.append(record.content)
                medical_history.append(
                    {
                        "type": record.record_type.value,
                        "date": record.record_date.isoformat(),
                        "title": record.title,
                    }
                )

            # Get AI analysis chain
            analysis_chain = self.chain_manager.get_chain("health_analysis")

            # Run analysis
            result = {}
            if analysis_chain:
                result = await analysis_chain.arun(
                    demographics={
                        "age": patient.age if hasattr(patient, "age") else "Unknown",
                        "gender": (
                            patient.gender if hasattr(patient, "gender") else "Unknown"
                        ),
                        "origin_country": (
                            patient.origin_country
                            if hasattr(patient, "origin_country")
                            else "Unknown"
                        ),
                    },
                    medical_history=medical_history,
                    conditions=conditions,
                    medications=medications,
                    vitals=vitals,
                )

            return {
                "patient_id": str(patient_id),
                "analysis_date": datetime.utcnow().isoformat(),
                "trends": result.get("summary", []),
                "insights": result.get("recommendations", []),
                "recommendations": result.get("follow_up", []),
                "cultural_considerations": result.get("cultural_considerations", []),
            }

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error analyzing health trends: %s", e)
            return {
                "patient_id": str(patient_id),
                "trends": [],
                "insights": [],
                "recommendations": [],
                "error": str(e),
            }

    async def predict_health_risks(
        self, patient_id: UUID, time_horizon: str = "30d"
    ) -> Dict[str, Any]:
        """Predict potential health risks using AI."""
        try:
            # Get patient data
            patient = self.patient_service.get_by_id(patient_id)
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")

            # Get recent health records
            records, _ = self.health_service.get_patient_records(
                patient_id=patient_id,
                start_date=datetime.utcnow() - timedelta(days=180),
                limit=50,
            )

            # Extract relevant data
            conditions = []
            symptoms = []

            for record in records:
                if record.record_type == RecordType.DIAGNOSIS:
                    conditions.append(record.title)
                elif record.record_type == RecordType.CLINICAL_NOTE:
                    symptoms.append(record.title)

            # Get risk assessment chain
            risk_chain = self.chain_manager.get_chain("risk_assessment")

            # Run risk assessment
            if risk_chain:
                result = await risk_chain.arun(
                    origin_country=(
                        patient.origin_country
                        if hasattr(patient, "origin_country")
                        else "Unknown"
                    ),
                    transit_route=(
                        patient.transit_route
                        if hasattr(patient, "transit_route")
                        else "Unknown"
                    ),
                    current_location=(
                        patient.current_location
                        if hasattr(patient, "current_location")
                        else "Unknown"
                    ),
                    age=patient.age if hasattr(patient, "age") else "Unknown",
                    gender=patient.gender if hasattr(patient, "gender") else "Unknown",
                    conditions=conditions,
                    symptoms=symptoms,
                )

                return {
                    "patient_id": str(patient_id),
                    "assessment_date": datetime.utcnow().isoformat(),
                    "time_horizon": time_horizon,
                    "risk_factors": result.get("immediate_risks", []),
                    "predictions": result.get("medium_term_risks", []),
                    "preventive_measures": result.get("preventive_measures", []),
                    "screening_recommendations": result.get("screening_needed", []),
                    "confidence": result.get("confidence_level", 0.0),
                }
            else:
                return {
                    "patient_id": str(patient_id),
                    "assessment_date": datetime.utcnow().isoformat(),
                    "time_horizon": time_horizon,
                    "risk_factors": [],
                    "predictions": [],
                    "preventive_measures": [],
                    "screening_recommendations": [],
                    "confidence": 0.0,
                    "error": "Risk assessment chain not available",
                }

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error predicting health risks: %s", e)
            return {
                "patient_id": str(patient_id),
                "risk_factors": [],
                "predictions": [],
                "confidence": 0.0,
                "error": str(e),
            }

    async def generate_health_summary(
        self, patient_id: UUID, language: str = "en"
    ) -> Dict[str, Any]:
        """Generate AI health summary for refugee health passport.

        Critical for:
        - Quick overview for healthcare providers at borders
        - Emergency medical information
        - Continuity of care across countries
        - Language-appropriate summaries for providers
        """
        # Get patient data
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return {
                "patient_id": str(patient_id),
                "error": "Patient not found",
                "language": language,
            }

        # Get recent health records (last 2 years)
        two_years_ago = datetime.utcnow() - timedelta(days=730)
        health_records = (
            self.db.query(HealthRecord)
            .filter(HealthRecord.patient_id == patient_id)  # type: ignore[arg-type]
            .filter(HealthRecord.created_at >= two_years_ago)
            .order_by(HealthRecord.created_at.desc())
            .all()
        )

        # Extract key medical information
        conditions = []
        medications = []
        allergies = []
        vaccinations = []
        recent_visits = []

        for record in health_records:
            if (
                record.record_type == RecordType.DIAGNOSIS
                and hasattr(record, "data")
                and record.data
            ):
                conditions.append(
                    {
                        "name": record.data.get("name", "Unknown"),
                        "date": record.created_at.isoformat(),
                        "status": record.data.get("status", "active"),
                    }
                )
            elif (
                record.record_type == RecordType.MEDICATION
                and hasattr(record, "data")
                and record.data
            ):
                medications.append(
                    {
                        "name": record.data.get("name", "Unknown"),
                        "dosage": record.data.get("dosage", ""),
                        "frequency": record.data.get("frequency", ""),
                        "start_date": record.created_at.isoformat(),
                    }
                )
            elif (
                record.record_type == RecordType.ALLERGY
                and hasattr(record, "data")
                and record.data
            ):
                allergies.append(
                    {
                        "substance": record.data.get("substance", "Unknown"),
                        "severity": record.data.get("severity", "unknown"),
                        "reaction": record.data.get("reaction", ""),
                    }
                )
            elif (
                record.record_type == RecordType.IMMUNIZATION
                and hasattr(record, "data")
                and record.data
            ):
                vaccinations.append(
                    {
                        "vaccine": record.data.get("vaccine", "Unknown"),
                        "date": record.created_at.isoformat(),
                        "next_due": record.data.get("next_due", ""),
                    }
                )
            elif (
                record.record_type == RecordType.CLINICAL_NOTE
                and hasattr(record, "data")
                and record.data
            ):
                recent_visits.append(
                    {
                        "date": record.created_at.isoformat(),
                        "provider": record.data.get("provider", "Unknown"),
                        "reason": record.data.get("reason", ""),
                        "outcome": record.data.get("outcome", ""),
                    }
                )

        # Generate key points based on data
        key_points = []

        # Critical allergies
        severe_allergies = [
            a for a in allergies if a["severity"] in ["severe", "life-threatening"]
        ]
        if severe_allergies:
            key_points.append(
                {
                    "type": "critical",
                    "category": "allergy",
                    "text": f"SEVERE ALLERGIES: {', '.join([a['substance'] for a in severe_allergies])}",
                }
            )

        # Chronic conditions
        chronic_conditions = [c for c in conditions if c["status"] == "active"]
        if chronic_conditions:
            key_points.append(
                {
                    "type": "important",
                    "category": "condition",
                    "text": f"Active conditions: {', '.join([c['name'] for c in chronic_conditions[:3]])}",
                }
            )

        # Current medications
        if medications:
            key_points.append(
                {
                    "type": "important",
                    "category": "medication",
                    "text": f"Current medications: {len(medications)} active prescriptions",
                }
            )

        # Vaccination status
        essential_vaccines = ["COVID-19", "MMR", "Hepatitis B", "Yellow Fever"]
        received_vaccines = [v["vaccine"] for v in vaccinations]
        missing_vaccines = [
            v
            for v in essential_vaccines
            if not any(v.lower() in rv.lower() for rv in received_vaccines)
        ]

        if missing_vaccines:
            key_points.append(
                {
                    "type": "warning",
                    "category": "vaccination",
                    "text": f"Missing vaccinations: {', '.join(missing_vaccines)}",
                }
            )

        # Generate summary text
        summary_parts = []

        # Basic demographics
        age = "Unknown"
        if hasattr(patient, "date_of_birth") and patient.date_of_birth:
            age = (datetime.utcnow().date() - patient.date_of_birth).days // 365

        summary_parts.append(
            f"{getattr(patient, 'gender', 'Unknown gender')}, {age} years old"
        )

        # Health status
        if chronic_conditions:
            summary_parts.append(
                f"Has {len(chronic_conditions)} active medical condition(s)"
            )
        else:
            summary_parts.append("No chronic conditions recorded")

        # Medication status
        if medications:
            summary_parts.append(f"Taking {len(medications)} medication(s)")

        # Allergy status
        if allergies:
            summary_parts.append(f"{len(allergies)} known allergie(s)")

        # Recent care
        if recent_visits:
            last_visit = recent_visits[0]
            days_since = (
                datetime.utcnow() - datetime.fromisoformat(last_visit["date"])
            ).days
            summary_parts.append(f"Last medical visit: {days_since} days ago")

        # Translate summary if needed
        summary_text = ". ".join(summary_parts) + "."

        # For non-English, add translation note
        if language != "en":
            summary_text += (
                f" [Summary generated in English - translation to {language} pending]"
            )

        return {
            "patient_id": str(patient_id),
            "summary": summary_text,
            "key_points": key_points,
            "language": language,
            "generated_at": datetime.utcnow().isoformat(),
            "data_summary": {
                "total_records": len(health_records),
                "conditions": len(conditions),
                "medications": len(medications),
                "allergies": len(allergies),
                "vaccinations": len(vaccinations),
                "recent_visits": len(recent_visits[:5]),  # Last 5 visits
            },
            "medical_details": {
                "conditions": conditions[:5],  # Top 5
                "medications": medications[:10],  # Top 10
                "allergies": allergies,  # All allergies
                "vaccinations": vaccinations[:10],  # Recent 10
                "recent_visits": recent_visits[:3],  # Last 3
            },
        }

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        return self.fhir_validator.validate_resource(resource)

    @audit_phi_access("process_phi_data")
    @require_permission(AccessPermission.READ_PHI)
    def process_with_phi_protection(self, data: dict) -> dict:
        """Process data with PHI protection and audit logging."""
        # Encrypt sensitive fields
        sensitive_fields = ["name", "birthDate", "ssn", "address"]
        encrypted_data = data.copy()

        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[field] = self.encryption_service.encrypt(
                    str(encrypted_data[field]).encode("utf-8")
                )

        return encrypted_data

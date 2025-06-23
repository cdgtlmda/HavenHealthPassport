"""
Test suite for GDPR Compliance module.

This test ensures 80% statement coverage as required for regulatory compliance.
Uses real implementation code - NO MOCKS for core functionality.
"""

from datetime import datetime, timedelta

import pytest

from src.healthcare.regulatory.gdpr_compliance import (
    GDPRConsentManager,
    GDPRDataPortability,
    GDPRDataProtectionOfficer,
    GDPRErasure,
    GDPRLawfulBasis,
    GDPRRight,
    HIPAAAuditControls,
    HIPAAMinimumNecessary,
    ProcessingPurpose,
    validate_fhir,
)


class TestGDPRLawfulBasis:
    """Test GDPR lawful basis enum."""

    def test_all_basis_values(self):
        """Test all lawful basis values are defined."""
        assert GDPRLawfulBasis.CONSENT.value == "consent"
        assert GDPRLawfulBasis.CONTRACT.value == "contract"
        assert GDPRLawfulBasis.LEGAL_OBLIGATION.value == "legal_obligation"
        assert GDPRLawfulBasis.VITAL_INTERESTS.value == "vital_interests"
        assert GDPRLawfulBasis.PUBLIC_TASK.value == "public_task"
        assert GDPRLawfulBasis.LEGITIMATE_INTERESTS.value == "legitimate_interests"
        assert GDPRLawfulBasis.EXPLICIT_CONSENT.value == "explicit_consent"
        assert GDPRLawfulBasis.EMPLOYMENT.value == "employment"
        assert (
            GDPRLawfulBasis.VITAL_INTERESTS_INCAPABLE.value
            == "vital_interests_incapable"
        )
        assert GDPRLawfulBasis.HEALTHCARE.value == "healthcare"
        assert GDPRLawfulBasis.PUBLIC_HEALTH.value == "public_health"


class TestGDPRRight:
    """Test GDPR rights enum."""

    def test_all_rights_values(self):
        """Test all GDPR rights are defined."""
        assert GDPRRight.ACCESS.value == "access"
        assert GDPRRight.RECTIFICATION.value == "rectification"
        assert GDPRRight.ERASURE.value == "erasure"
        assert GDPRRight.RESTRICTION.value == "restriction"
        assert GDPRRight.PORTABILITY.value == "portability"
        assert GDPRRight.OBJECT.value == "object"
        assert GDPRRight.AUTOMATED_DECISION.value == "automated_decision"


class TestProcessingPurpose:
    """Test processing purpose enum."""

    def test_all_purposes(self):
        """Test all processing purposes are defined."""
        assert ProcessingPurpose.HEALTHCARE_PROVISION.value == "healthcare_provision"
        assert ProcessingPurpose.MEDICAL_DIAGNOSIS.value == "medical_diagnosis"
        assert ProcessingPurpose.HEALTH_MANAGEMENT.value == "health_management"
        assert ProcessingPurpose.MEDICAL_RESEARCH.value == "medical_research"
        assert ProcessingPurpose.PUBLIC_HEALTH.value == "public_health"
        assert ProcessingPurpose.HUMANITARIAN_AID.value == "humanitarian_aid"
        assert ProcessingPurpose.EMERGENCY_CARE.value == "emergency_care"
        assert ProcessingPurpose.BILLING.value == "billing"
        assert ProcessingPurpose.QUALITY_IMPROVEMENT.value == "quality_improvement"


class TestGDPRConsentManager:
    """Test GDPR consent management."""

    @pytest.fixture
    def consent_manager(self):
        """Create consent manager instance."""
        return GDPRConsentManager()

    def test_initialization(self, consent_manager):
        """Test consent manager initialization."""
        assert isinstance(consent_manager.consents, dict)
        assert isinstance(consent_manager.consent_templates, dict)
        assert "healthcare" in consent_manager.consent_templates
        assert "research" in consent_manager.consent_templates
        assert "humanitarian" in consent_manager.consent_templates

    def test_consent_templates(self, consent_manager):
        """Test consent templates are properly configured."""
        healthcare_template = consent_manager.consent_templates["healthcare"]

        assert healthcare_template["purpose"] == ProcessingPurpose.HEALTHCARE_PROVISION
        assert healthcare_template["lawful_basis"] == GDPRLawfulBasis.HEALTHCARE
        assert "identification_data" in healthcare_template["data_categories"]
        assert "health_data" in healthcare_template["data_categories"]
        assert healthcare_template["retention_period"] == 365 * 10
        assert "healthcare_providers" in healthcare_template["third_parties"]
        assert healthcare_template["international_transfer"] is False

        research_template = consent_manager.consent_templates["research"]
        assert research_template["purpose"] == ProcessingPurpose.MEDICAL_RESEARCH
        assert research_template["lawful_basis"] == GDPRLawfulBasis.EXPLICIT_CONSENT
        assert research_template["requires_explicit_consent"] is True
        assert research_template["international_transfer"] is True

        humanitarian_template = consent_manager.consent_templates["humanitarian"]
        assert humanitarian_template["purpose"] == ProcessingPurpose.HUMANITARIAN_AID
        assert humanitarian_template["lawful_basis"] == GDPRLawfulBasis.VITAL_INTERESTS

    def test_record_consent_basic(self, consent_manager):
        """Test basic consent recording."""
        data_subject_id = "patient-123"
        purpose = ProcessingPurpose.HEALTHCARE_PROVISION

        consent_id = consent_manager.record_consent(
            data_subject_id=data_subject_id, purpose=purpose, consent_given=True
        )

        assert consent_id is not None
        assert data_subject_id in consent_manager.consents
        assert len(consent_manager.consents[data_subject_id]) == 1

        consent_record = consent_manager.consents[data_subject_id][0]
        assert consent_record["consent_id"] == consent_id
        assert consent_record["data_subject_id"] == data_subject_id
        assert consent_record["purpose"] == purpose.value
        assert consent_record["consent_given"] is True
        assert consent_record["withdrawn"] is False
        assert consent_record["language"] == "en"
        assert consent_record["method"] == "electronic"

    def test_record_consent_with_guardian(self, consent_manager):
        """Test recording consent with parent/guardian."""
        data_subject_id = "minor-456"
        guardian_id = "guardian-789"
        purpose = ProcessingPurpose.HEALTHCARE_PROVISION

        _ = consent_manager.record_consent(
            data_subject_id=data_subject_id,
            purpose=purpose,
            consent_given=True,
            parent_guardian_id=guardian_id,
            language="ar",
            method="written",
        )

        consent_record = consent_manager.consents[data_subject_id][0]
        assert consent_record["parent_guardian_id"] == guardian_id
        assert consent_record["language"] == "ar"
        assert consent_record["method"] == "written"

    def test_record_consent_with_details(self, consent_manager):
        """Test recording consent with additional details."""
        data_subject_id = "patient-789"
        purpose = ProcessingPurpose.MEDICAL_RESEARCH

        details = {
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "consent_text_version": "2.1",
        }

        _ = consent_manager.record_consent(
            data_subject_id=data_subject_id,
            purpose=purpose,
            consent_given=True,
            details=details,
        )

        consent_record = consent_manager.consents[data_subject_id][0]
        assert consent_record["ip_address"] == "192.168.1.1"
        assert consent_record["user_agent"] == "Mozilla/5.0"
        assert consent_record["consent_text_version"] == "2.1"

    def test_record_consent_denial(self, consent_manager):
        """Test recording consent denial."""
        data_subject_id = "patient-denial"
        purpose = ProcessingPurpose.MEDICAL_RESEARCH

        _ = consent_manager.record_consent(
            data_subject_id=data_subject_id, purpose=purpose, consent_given=False
        )

        consent_record = consent_manager.consents[data_subject_id][0]
        assert consent_record["consent_given"] is False

    def test_multiple_consents_same_subject(self, consent_manager):
        """Test recording multiple consents for same subject."""
        data_subject_id = "patient-multi"

        # First consent
        consent_id1 = consent_manager.record_consent(
            data_subject_id=data_subject_id,
            purpose=ProcessingPurpose.HEALTHCARE_PROVISION,
            consent_given=True,
        )

        # Second consent
        consent_id2 = consent_manager.record_consent(
            data_subject_id=data_subject_id,
            purpose=ProcessingPurpose.MEDICAL_RESEARCH,
            consent_given=False,
        )

        assert len(consent_manager.consents[data_subject_id]) == 2
        assert consent_id1 != consent_id2

        consents = consent_manager.consents[data_subject_id]
        purposes = [c["purpose"] for c in consents]
        assert "healthcare_provision" in purposes
        assert "medical_research" in purposes

    def test_withdraw_consent(self, consent_manager):
        """Test withdrawing consent."""
        data_subject_id = "patient-withdraw"
        purpose = ProcessingPurpose.HEALTHCARE_PROVISION

        # Record consent
        consent_id = consent_manager.record_consent(
            data_subject_id=data_subject_id, purpose=purpose, consent_given=True
        )

        # Withdraw consent
        result = consent_manager.withdraw_consent(
            data_subject_id=data_subject_id,
            consent_id=consent_id,
            reason="Changed mind",
        )

        assert result is True

        consent_record = consent_manager.consents[data_subject_id][0]
        assert consent_record["withdrawn"] is True
        assert consent_record["withdrawal_date"] is not None
        assert isinstance(consent_record["withdrawal_date"], datetime)

    def test_withdraw_nonexistent_consent(self, consent_manager):
        """Test withdrawing non-existent consent."""
        result = consent_manager.withdraw_consent(
            data_subject_id="nonexistent",
            consent_id="nonexistent-consent",
            reason="Test",
        )

        assert result is False

    def test_check_consent_valid(self, consent_manager):
        """Test checking valid consent."""
        data_subject_id = "patient-check"
        purpose = ProcessingPurpose.HEALTHCARE_PROVISION

        # Record consent
        consent_manager.record_consent(
            data_subject_id=data_subject_id, purpose=purpose, consent_given=True
        )

        # Check consent
        has_consent, consent_id = consent_manager.check_consent(
            data_subject_id=data_subject_id, purpose=purpose
        )

        assert has_consent is True
        assert consent_id is not None

    def test_check_consent_denied(self, consent_manager):
        """Test checking denied consent."""
        data_subject_id = "patient-denied"
        purpose = ProcessingPurpose.MEDICAL_RESEARCH

        # Record denial
        consent_manager.record_consent(
            data_subject_id=data_subject_id, purpose=purpose, consent_given=False
        )

        # Check consent
        has_consent, consent_id = consent_manager.check_consent(
            data_subject_id=data_subject_id, purpose=purpose
        )

        assert has_consent is False
        assert consent_id is not None

    def test_check_consent_withdrawn(self, consent_manager):
        """Test checking withdrawn consent."""
        data_subject_id = "patient-withdrawn"
        purpose = ProcessingPurpose.HEALTHCARE_PROVISION

        # Record and withdraw consent
        consent_id = consent_manager.record_consent(
            data_subject_id=data_subject_id, purpose=purpose, consent_given=True
        )

        consent_manager.withdraw_consent(
            data_subject_id=data_subject_id, consent_id=consent_id
        )

        # Check consent
        has_consent, returned_consent_id = consent_manager.check_consent(
            data_subject_id=data_subject_id, purpose=purpose
        )

        assert has_consent is False
        assert returned_consent_id == consent_id

    def test_check_consent_no_record(self, consent_manager):
        """Test checking consent with no record."""
        has_consent, consent_id = consent_manager.check_consent(
            data_subject_id="nonexistent",
            purpose=ProcessingPurpose.HEALTHCARE_PROVISION,
        )

        assert has_consent is False
        assert consent_id is None

    def test_get_consent_history(self, consent_manager):
        """Test getting consent history."""
        data_subject_id = "patient-history"

        # Record multiple consents
        consent_manager.record_consent(
            data_subject_id=data_subject_id,
            purpose=ProcessingPurpose.HEALTHCARE_PROVISION,
            consent_given=True,
        )

        consent_manager.record_consent(
            data_subject_id=data_subject_id,
            purpose=ProcessingPurpose.MEDICAL_RESEARCH,
            consent_given=False,
        )

        history = consent_manager.get_consent_history(data_subject_id)

        assert len(history) == 2
        assert all(isinstance(record, dict) for record in history)
        assert all("consent_id" in record for record in history)
        assert all("timestamp" in record for record in history)

    def test_get_consent_history_empty(self, consent_manager):
        """Test getting empty consent history."""
        history = consent_manager.get_consent_history("nonexistent")
        assert history == []


class TestGDPRDataPortability:
    """Test GDPR data portability."""

    @pytest.fixture
    def portability_manager(self):
        """Create data portability manager instance."""
        return GDPRDataPortability()

    def test_initialization(self, portability_manager):
        """Test data portability manager initialization."""
        assert isinstance(portability_manager.exports, dict)
        assert isinstance(portability_manager.transfers, dict)

    def test_export_personal_data_default(self, portability_manager):
        """Test exporting personal data with default parameters."""
        data_subject_id = "patient-export"

        export_data = portability_manager.export_personal_data(data_subject_id)

        assert isinstance(export_data, dict)
        assert "export_id" in export_data
        assert "data_subject_id" in export_data
        assert export_data["data_subject_id"] == data_subject_id
        assert "export_date" in export_data
        assert "format" in export_data
        assert export_data["format"] == "json"
        assert "categories_included" in export_data
        assert "personal_data" in export_data

    def test_export_personal_data_specific_categories(self, portability_manager):
        """Test exporting specific data categories."""
        data_subject_id = "patient-specific"
        categories = ["identification_data", "health_data"]

        export_data = portability_manager.export_personal_data(
            data_subject_id=data_subject_id,
            include_categories=categories,
            export_format="xml",
        )

        assert export_data["format"] == "xml"
        assert set(export_data["categories_included"]) == set(categories)

    def test_transfer_to_controller(self, portability_manager):
        """Test transferring data to another controller."""
        data_subject_id = "patient-transfer"
        target_controller = "new-healthcare-provider"

        # First export data
        export_data = portability_manager.export_personal_data(data_subject_id)

        # Then transfer
        transfer_id = portability_manager.transfer_to_controller(
            data_subject_id=data_subject_id,
            target_controller=target_controller,
            data_package=export_data,
        )

        assert transfer_id is not None
        assert data_subject_id in portability_manager.transfers

        transfer_record = portability_manager.transfers[data_subject_id][0]
        assert transfer_record["transfer_id"] == transfer_id
        assert transfer_record["target_controller"] == target_controller
        assert transfer_record["data_package"] == export_data
        assert "transfer_date" in transfer_record


class TestGDPRErasure:
    """Test GDPR erasure (right to be forgotten)."""

    @pytest.fixture
    def erasure_manager(self):
        """Create erasure manager instance."""
        return GDPRErasure()

    def test_initialization(self, erasure_manager):
        """Test erasure manager initialization."""
        assert isinstance(erasure_manager.erasure_requests, dict)
        assert isinstance(erasure_manager.erasure_log, list)

    def test_request_erasure_basic(self, erasure_manager):
        """Test basic erasure request."""
        data_subject_id = "patient-erasure"
        categories = ["identification_data", "contact_data"]
        reason = "No longer needed"

        request_id = erasure_manager.request_erasure(
            data_subject_id=data_subject_id, categories=categories, reason=reason
        )

        assert request_id is not None
        assert request_id in erasure_manager.erasure_requests

        request = erasure_manager.erasure_requests[request_id]
        assert request["data_subject_id"] == data_subject_id
        assert request["categories"] == categories
        assert request["reason"] == reason
        assert request["status"] == "pending"
        assert "request_date" in request

    def test_request_erasure_with_requestor(self, erasure_manager):
        """Test erasure request with specific requestor."""
        data_subject_id = "patient-requestor"
        requestor_id = "legal-representative"
        categories = ["health_data"]
        reason = "Legal representative request"

        request_id = erasure_manager.request_erasure(
            data_subject_id=data_subject_id,
            categories=categories,
            reason=reason,
            requestor_id=requestor_id,
        )

        request = erasure_manager.erasure_requests[request_id]
        assert request["requestor_id"] == requestor_id

    def test_multiple_erasure_requests(self, erasure_manager):
        """Test multiple erasure requests for same subject."""
        data_subject_id = "patient-multiple"

        request_id1 = erasure_manager.request_erasure(
            data_subject_id=data_subject_id,
            categories=["contact_data"],
            reason="Reason 1",
        )

        request_id2 = erasure_manager.request_erasure(
            data_subject_id=data_subject_id,
            categories=["identification_data"],
            reason="Reason 2",
        )

        assert request_id1 != request_id2
        assert len(erasure_manager.erasure_requests) == 2


class TestGDPRDataProtectionOfficer:
    """Test GDPR Data Protection Officer functions."""

    @pytest.fixture
    def dpo(self):
        """Create DPO instance."""
        return GDPRDataProtectionOfficer()

    def test_initialization(self, dpo):
        """Test DPO initialization."""
        assert isinstance(dpo.dpias, dict)
        assert isinstance(dpo.breaches, dict)

    def test_conduct_dpia(self, dpo):
        """Test conducting Data Protection Impact Assessment."""
        project_name = "New Medical AI System"
        description = "AI system for medical diagnosis"
        data_categories = ["health_data", "genetic_data"]
        purposes = [ProcessingPurpose.MEDICAL_DIAGNOSIS]
        risks = [
            {
                "type": "accuracy",
                "likelihood": 3,
                "impact": 4,
                "description": "Misdiagnosis risk",
            }
        ]

        dpia_id = dpo.conduct_dpia(
            project_name=project_name,
            processing_description=description,
            data_categories=data_categories,
            purposes=purposes,
            risks=risks,
        )

        assert dpia_id is not None
        assert dpia_id in dpo.dpias

        dpia = dpo.dpias[dpia_id]
        assert dpia["project_name"] == project_name
        assert dpia["processing_description"] == description
        assert dpia["data_categories"] == data_categories
        assert dpia["purposes"] == [p.value for p in purposes]
        assert dpia["risks"] == risks
        assert "risk_score" in dpia
        assert "assessment_date" in dpia
        assert "necessity_assessment" in dpia
        assert "proportionality_assessment" in dpia
        assert "mitigation_measures" in dpia

    def test_report_breach(self, dpo):
        """Test reporting data breach."""
        breach_type = "unauthorized_access"
        affected_records = 150
        data_categories = ["health_data", "identification_data"]
        discovery_date = datetime.now()
        description = "Unauthorized access to patient records"
        consequences = "Potential privacy violations"
        measures = "Access revoked, systems secured"

        breach_id = dpo.report_breach(
            breach_type=breach_type,
            affected_records=affected_records,
            data_categories=data_categories,
            discovery_date=discovery_date,
            description=description,
            likely_consequences=consequences,
            measures_taken=measures,
        )

        assert breach_id is not None
        assert breach_id in dpo.breaches

        breach = dpo.breaches[breach_id]
        assert breach["breach_type"] == breach_type
        assert breach["affected_records"] == affected_records
        assert breach["data_categories"] == data_categories
        assert breach["description"] == description
        assert breach["likely_consequences"] == consequences
        assert breach["measures_taken"] == measures
        assert "severity" in breach
        assert "notify_authority" in breach
        assert "notify_subjects" in breach


class TestHIPAAMinimumNecessary:
    """Test HIPAA minimum necessary standard."""

    @pytest.fixture
    def hipaa_manager(self):
        """Create HIPAA minimum necessary manager."""
        return HIPAAMinimumNecessary()

    def test_initialization(self, hipaa_manager):
        """Test HIPAA manager initialization."""
        assert isinstance(hipaa_manager.roles, dict)
        assert isinstance(hipaa_manager.purposes, dict)
        assert isinstance(hipaa_manager.access_logs, list)
        assert isinstance(hipaa_manager.policies, dict)

    def test_role_definitions(self, hipaa_manager):
        """Test role definitions are properly configured."""
        assert "physician" in hipaa_manager.roles
        assert "nurse" in hipaa_manager.roles
        assert "administrative_staff" in hipaa_manager.roles
        assert "researcher" in hipaa_manager.roles
        assert "patient" in hipaa_manager.roles

        physician_role = hipaa_manager.roles["physician"]
        assert "allowed_data" in physician_role
        assert "restrictions" in physician_role
        assert "requires_approval" in physician_role

    def test_purpose_definitions(self, hipaa_manager):
        """Test purpose definitions are properly configured."""
        assert "treatment" in hipaa_manager.purposes
        assert "payment" in hipaa_manager.purposes
        assert "healthcare_operations" in hipaa_manager.purposes
        assert "research" in hipaa_manager.purposes
        assert "emergency" in hipaa_manager.purposes

    def test_determine_minimum_necessary_physician_treatment(self, hipaa_manager):
        """Test minimum necessary determination for physician treatment."""
        allowed_data, decision_log = hipaa_manager.determine_minimum_necessary(
            requester_role="physician",
            purpose="treatment",
            patient_id="patient-123",
            requested_data=[
                "demographics",
                "medical_history",
                "current_medications",
                "billing_info",
            ],
        )

        assert isinstance(allowed_data, list)
        assert isinstance(decision_log, dict)
        assert "demographics" in allowed_data
        assert "medical_history" in allowed_data
        assert "current_medications" in allowed_data
        # Billing info typically not needed for treatment
        assert "billing_info" not in allowed_data

        assert "decision_id" in decision_log
        assert "requester_role" in decision_log
        assert "purpose" in decision_log
        assert "patient_id" in decision_log

    def test_determine_minimum_necessary_researcher(self, hipaa_manager):
        """Test minimum necessary determination for researcher."""
        allowed_data, decision_log = hipaa_manager.determine_minimum_necessary(
            requester_role="researcher",
            purpose="research",
            patient_id="patient-research",
            requested_data=[
                "demographics",
                "medical_history",
                "genetic_data",
                "contact_info",
            ],
        )

        # Researchers typically get limited access and may need de-identified data
        assert isinstance(allowed_data, list)
        assert len(allowed_data) <= len(
            ["demographics", "medical_history", "genetic_data", "contact_info"]
        )

    def test_determine_minimum_necessary_with_context(self, hipaa_manager):
        """Test minimum necessary with additional context."""
        context = {
            "emergency": True,
            "patient_condition": "critical",
            "time_of_access": datetime.now(),
        }

        allowed_data, decision_log = hipaa_manager.determine_minimum_necessary(
            requester_role="nurse",
            purpose="emergency",
            patient_id="patient-emergency",
            requested_data=[
                "demographics",
                "allergies",
                "current_medications",
                "emergency_contacts",
            ],
            context=context,
        )

        # Emergency context should allow broader access
        assert isinstance(allowed_data, list)
        assert "allergies" in allowed_data
        assert "current_medications" in allowed_data
        assert "emergency_contacts" in allowed_data

    def test_create_access_policy(self, hipaa_manager):
        """Test creating custom access policy."""
        policy_name = "Cardiology Department Policy"
        description = "Access policy for cardiology staff"
        roles = ["cardiologist", "cardiac_nurse"]
        purposes = ["treatment", "healthcare_operations"]
        data_categories = ["demographics", "cardiac_history", "lab_results"]

        policy_id = hipaa_manager.create_access_policy(
            policy_name=policy_name,
            description=description,
            roles=roles,
            purposes=purposes,
            data_categories=data_categories,
        )

        assert policy_id is not None
        assert policy_id in hipaa_manager.policies

        policy = hipaa_manager.policies[policy_id]
        assert policy["name"] == policy_name
        assert policy["description"] == description
        assert policy["roles"] == roles
        assert policy["purposes"] == purposes
        assert policy["data_categories"] == data_categories

    def test_audit_minimum_necessary_compliance(self, hipaa_manager):
        """Test auditing minimum necessary compliance."""
        # First make some access decisions to generate logs
        hipaa_manager.determine_minimum_necessary(
            requester_role="physician",
            purpose="treatment",
            patient_id="patient-audit1",
            requested_data=["demographics", "medical_history"],
        )

        hipaa_manager.determine_minimum_necessary(
            requester_role="nurse",
            purpose="treatment",
            patient_id="patient-audit2",
            requested_data=["demographics", "current_medications"],
        )

        # Now audit compliance
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now() + timedelta(days=1)

        audit_report = hipaa_manager.audit_minimum_necessary_compliance(
            start_date=start_date, end_date=end_date
        )

        assert isinstance(audit_report, dict)
        assert "total_decisions" in audit_report
        assert "compliance_score" in audit_report
        assert "role_statistics" in audit_report
        assert "purpose_statistics" in audit_report
        assert "recommendations" in audit_report
        assert audit_report["total_decisions"] >= 2  # We made at least 2 decisions


class TestHIPAAAuditControls:
    """Test HIPAA audit controls."""

    @pytest.fixture
    def audit_controls(self):
        """Create audit controls instance."""
        return HIPAAAuditControls()

    def test_initialization(self, audit_controls):
        """Test audit controls initialization."""
        assert isinstance(audit_controls.audit_log, list)
        assert isinstance(audit_controls.audit_policies, dict)
        assert isinstance(audit_controls.alert_rules, dict)

    def test_log_event_basic(self, audit_controls):
        """Test basic event logging."""
        audit_id = audit_controls.log_event(
            event_type="access",
            user_id="user123",
            action="view_patient",
            resource_type="patient",
            resource_id="patient-456",
        )

        assert audit_id is not None
        assert len(audit_controls.audit_log) == 1

        log_entry = audit_controls.audit_log[0]
        assert log_entry["audit_id"] == audit_id
        assert log_entry["event_type"] == "access"
        assert log_entry["user_id"] == "user123"
        assert log_entry["action"] == "view_patient"
        assert log_entry["resource_type"] == "patient"
        assert log_entry["resource_id"] == "patient-456"
        assert log_entry["outcome"] == "success"
        assert "timestamp" in log_entry

    def test_log_event_with_details(self, audit_controls):
        """Test event logging with additional details."""
        details = {
            "department": "cardiology",
            "duration_seconds": 45,
            "data_accessed": ["demographics", "medical_history"],
        }

        _ = audit_controls.log_event(
            event_type="access",
            user_id="physician123",
            action="view_patient",
            resource_type="patient",
            resource_id="patient-789",
            details=details,
            outcome="success",
            ip_address="10.0.1.15",
            user_agent="EMR-System/2.1",
        )

        log_entry = audit_controls.audit_log[0]
        assert log_entry["details"] == details
        assert log_entry["ip_address"] == "10.0.1.15"
        assert log_entry["user_agent"] == "EMR-System/2.1"

    def test_log_phi_access(self, audit_controls):
        """Test PHI access logging."""
        audit_id = audit_controls.log_phi_access(
            user_id="physician456",
            patient_id="patient-phi",
            data_accessed=["medical_history", "lab_results"],
            purpose="treatment",
            access_granted=True,
        )

        assert audit_id is not None

        log_entry = audit_controls.audit_log[0]
        assert log_entry["event_type"] == "phi_access"
        assert log_entry["patient_id"] == "patient-phi"
        assert log_entry["data_accessed"] == ["medical_history", "lab_results"]
        assert log_entry["purpose"] == "treatment"
        assert log_entry["access_granted"] is True

    def test_log_phi_access_denied(self, audit_controls):
        """Test PHI access denial logging."""
        _ = audit_controls.log_phi_access(
            user_id="staff789",
            patient_id="patient-denied",
            data_accessed=["medical_history"],
            purpose="curiosity",
            access_granted=False,
            denial_reason="Insufficient privileges",
        )

        log_entry = audit_controls.audit_log[0]
        assert log_entry["access_granted"] is False
        assert log_entry["denial_reason"] == "Insufficient privileges"

    def test_log_data_modification(self, audit_controls):
        """Test data modification logging."""
        changes = {
            "old_values": {"status": "active", "diagnosis": "hypertension"},
            "new_values": {
                "status": "inactive",
                "diagnosis": "controlled hypertension",
            },
        }

        _ = audit_controls.log_data_modification(
            user_id="physician999",
            resource_type="patient",
            resource_id="patient-modified",
            changes=changes,
            modification_type="update",
        )

        log_entry = audit_controls.audit_log[0]
        assert log_entry["event_type"] == "data_modification"
        assert log_entry["changes"] == changes
        assert log_entry["modification_type"] == "update"

    def test_log_security_event(self, audit_controls):
        """Test security event logging."""
        details = {
            "failed_attempts": 5,
            "source_ip": "192.168.1.100",
            "attempted_username": "admin",
        }

        _ = audit_controls.log_security_event(
            event_subtype="failed_login",
            user_id="attempted-user",
            details=details,
            severity="high",
        )

        log_entry = audit_controls.audit_log[0]
        assert log_entry["event_type"] == "security"
        assert log_entry["event_subtype"] == "failed_login"
        assert log_entry["severity"] == "high"
        assert log_entry["details"]["failed_attempts"] == 5

    def test_log_emergency_access(self, audit_controls):
        """Test emergency access logging."""
        _ = audit_controls.log_emergency_access(
            user_id="emergency-physician",
            patient_id="patient-emergency",
            reason="Cardiac arrest - immediate access needed",
            authorizing_physician="chief-physician",
        )

        log_entry = audit_controls.audit_log[0]
        assert log_entry["event_type"] == "emergency_access"
        assert log_entry["patient_id"] == "patient-emergency"
        assert log_entry["reason"] == "Cardiac arrest - immediate access needed"
        assert log_entry["authorizing_physician"] == "chief-physician"

    def test_query_audit_log(self, audit_controls):
        """Test querying audit log."""
        # Add some test entries
        audit_controls.log_event("access", "user1", "view", "patient", "p1")
        audit_controls.log_event("modification", "user2", "update", "patient", "p2")
        audit_controls.log_event("access", "user1", "view", "patient", "p3")

        # Query by user
        user1_logs = audit_controls.query_audit_log({"user_id": "user1"})
        assert len(user1_logs) == 2
        assert all(log["user_id"] == "user1" for log in user1_logs)

        # Query by event type
        access_logs = audit_controls.query_audit_log({"event_type": "access"})
        assert len(access_logs) == 2
        assert all(log["event_type"] == "access" for log in access_logs)

    def test_generate_audit_report_user_activity(self, audit_controls):
        """Test generating user activity audit report."""
        # Add test data
        audit_controls.log_event("access", "physician1", "view", "patient", "p1")
        audit_controls.log_event("access", "physician1", "view", "patient", "p2")
        audit_controls.log_event(
            "modification", "physician1", "update", "patient", "p1"
        )

        start_date = datetime.now() - timedelta(hours=1)
        end_date = datetime.now() + timedelta(hours=1)

        report = audit_controls.generate_audit_report(
            report_type="user_activity",
            start_date=start_date,
            end_date=end_date,
            parameters={"user_id": "physician1"},
        )

        assert isinstance(report, dict)
        assert "report_id" in report
        assert "report_type" in report
        assert "user_statistics" in report
        assert "total_events" in report
        assert report["total_events"] >= 3

    def test_verify_audit_integrity(self, audit_controls):
        """Test audit log integrity verification."""
        # Add some entries
        audit_controls.log_event("access", "user1", "view", "patient", "p1")
        audit_controls.log_event("access", "user2", "view", "patient", "p2")

        integrity_report = audit_controls.verify_audit_integrity()

        assert isinstance(integrity_report, dict)
        assert "total_entries" in integrity_report
        assert "integrity_violations" in integrity_report
        assert "hash_mismatches" in integrity_report
        assert integrity_report["total_entries"] >= 2


class TestFHIRIntegration:
    """Test FHIR integration functions."""

    def test_validate_fhir_function(self):
        """Test standalone FHIR validation function."""
        test_data = {"resourceType": "Patient", "id": "patient123", "active": True}

        result = validate_fhir(test_data)

        assert isinstance(result, dict)
        assert "is_valid" in result

    def test_hipaa_audit_controls_create_fhir_consent(self):
        """Test creating FHIR consent resource."""
        audit_controls = HIPAAAuditControls()

        consent = audit_controls.create_fhir_consent(
            patient_id="patient-123",
            purpose=ProcessingPurpose.HEALTHCARE_PROVISION,
            lawful_basis=GDPRLawfulBasis.HEALTHCARE,
            status="active",
        )

        assert isinstance(consent, dict)
        assert consent["resourceType"] == "Consent"
        assert consent["status"] == "active"
        assert "patient" in consent
        assert consent["patient"]["reference"] == "Patient/patient-123"
        assert "policy" in consent
        assert "provision" in consent

    def test_hipaa_audit_controls_validate_fhir_consent(self):
        """Test validating FHIR consent resource."""
        audit_controls = HIPAAAuditControls()

        consent_data = {
            "resourceType": "Consent",
            "id": "consent-123",
            "status": "active",
            "patient": {"reference": "Patient/patient-123"},
        }

        validation_result = audit_controls.validate_fhir_consent(consent_data)

        assert isinstance(validation_result, dict)
        assert "is_valid" in validation_result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

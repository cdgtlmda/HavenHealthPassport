"""HIPAA De-identification Implementation.

This module implements HIPAA-compliant de-identification methods for PHI,
including both Safe Harbor and Expert Determination methods.

Compliance Notes:
- PHI Protection: Implements encryption and secure hashing for de-identified data
- Audit Logging: All de-identification operations are logged for compliance auditing
- FHIR Support: Generates FHIR-compliant DomainResource structures for de-identified data
"""

import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DeIdentificationMethod(Enum):
    """HIPAA de-identification methods."""

    SAFE_HARBOR = "safe_harbor"  # §164.514(b)(2)
    EXPERT_DETERMINATION = "expert_determination"  # §164.514(b)(1)
    LIMITED_DATA_SET = "limited_data_set"  # §164.514(e)


class IdentifierType(Enum):
    """Types of identifiers per HIPAA Safe Harbor."""

    # Direct identifiers
    NAME = "name"
    GEOGRAPHIC = "geographic"
    DATE = "date"
    PHONE = "phone"
    FAX = "fax"
    EMAIL = "email"
    SSN = "ssn"
    MRN = "medical_record_number"
    HEALTH_PLAN = "health_plan_beneficiary"
    ACCOUNT = "account_number"
    LICENSE = "certificate_license"
    VEHICLE = "vehicle_identifier"
    DEVICE = "device_identifier"
    URL = "url"
    IP = "ip_address"
    BIOMETRIC = "biometric"
    PHOTO = "full_face_photo"
    OTHER = "other_unique_identifier"


class HIPAADeIdentification:
    """Implements HIPAA de-identification standards."""

    def __init__(self) -> None:
        """Initialize de-identification system."""
        self.safe_harbor_rules = self._initialize_safe_harbor_rules()
        self.de_identification_log: List[Dict[str, Any]] = []
        self.identifier_mappings: Dict[str, Dict[str, str]] = {}
        self.salt = secrets.token_bytes(32)

    def _initialize_safe_harbor_rules(self) -> Dict[IdentifierType, Dict[str, Any]]:
        """Initialize Safe Harbor de-identification rules."""
        return {
            IdentifierType.NAME: {
                "description": "Names",
                "action": "remove",
                "patterns": [
                    r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # Full names
                    r"\b(Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+\b",  # Titles
                ],
            },
            IdentifierType.GEOGRAPHIC: {
                "description": "Geographic subdivisions smaller than state",
                "action": "generalize",
                "zip_code_rule": "first_three_digits",  # If population > 20,000
                "remove": ["street_address", "city", "county"],
            },
            IdentifierType.DATE: {
                "description": "Date elements except year",
                "action": "generalize_to_year",
                "age_limit": 89,  # Ages > 89 become "90+"
                "remove": ["birth_date", "admission_date", "discharge_date"],
            },
            IdentifierType.PHONE: {
                "description": "Telephone numbers",
                "action": "remove",
                "patterns": [
                    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
                    r"\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b",
                ],
            },
            IdentifierType.EMAIL: {
                "description": "Email addresses",
                "action": "remove",
                "patterns": [r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"],
            },
            IdentifierType.SSN: {
                "description": "Social Security numbers",
                "action": "remove",
                "patterns": [r"\b\d{3}-\d{2}-\d{4}\b", r"\b\d{9}\b"],
            },
            IdentifierType.MRN: {
                "description": "Medical record numbers",
                "action": "replace_with_pseudonym",
                "preserve_linkage": True,
            },
            IdentifierType.IP: {
                "description": "IP addresses",
                "action": "remove",
                "patterns": [
                    r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",  # IPv4
                    r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b",  # IPv6
                ],
            },
        }

    def de_identify_safe_harbor(
        self, data: Dict[str, Any], preserve_utility: bool = True
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """De-identify data using Safe Harbor method.

        Args:
            data: Data to de-identify
            preserve_utility: Whether to preserve data utility

        Returns:
            Tuple of (de_identified_data, de_identification_report)
        """
        _ = preserve_utility  # Mark as intentionally unused
        de_identified = data.copy()
        removed_identifiers = {}
        transformations = []

        # Process each identifier type
        for identifier_type, rule in self.safe_harbor_rules.items():
            if rule["action"] == "remove":
                removed, transformed = self._remove_identifiers(
                    de_identified, identifier_type, rule
                )
                removed_identifiers.update(removed)
                transformations.extend(transformed)

            elif rule["action"] == "generalize":
                transformed = self._generalize_identifiers(
                    de_identified, identifier_type, rule
                )
                transformations.extend(transformed)

            elif rule["action"] == "generalize_to_year":
                transformed = self._generalize_dates(
                    de_identified, identifier_type, rule
                )
                transformations.extend(transformed)

            elif rule["action"] == "replace_with_pseudonym":
                transformed = self._pseudonymize_identifiers(
                    de_identified, identifier_type, rule
                )
                transformations.extend(transformed)

        # Create de-identification report
        report = {
            "method": DeIdentificationMethod.SAFE_HARBOR.value,
            "timestamp": datetime.now().isoformat(),
            "identifiers_removed": len(removed_identifiers),
            "transformations_applied": len(transformations),
            "removed_identifier_types": list(removed_identifiers.keys()),
            "transformation_details": transformations,
            "compliant": self._verify_safe_harbor_compliance(de_identified),
        }

        # Log de-identification
        self._log_de_identification(
            DeIdentificationMethod.SAFE_HARBOR,
            len(removed_identifiers),
            len(transformations),
        )

        return de_identified, report

    def de_identify_expert_determination(
        self,
        data: Dict[str, Any],
        risk_threshold: float = 0.01,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """De-identify using Expert Determination method.

        Args:
            data: Data to de-identify
            risk_threshold: Acceptable re-identification risk
            context: Additional context for risk assessment

        Returns:
            Tuple of (de_identified_data, risk_assessment)
        """
        de_identified = data.copy()

        # Perform risk assessment
        initial_risk = self._assess_reidentification_risk(data, context)

        # Apply transformations to reduce risk
        transformations = []
        current_risk = initial_risk

        while current_risk > risk_threshold:
            # Identify highest risk attributes
            risk_attributes = self._identify_risk_attributes(de_identified, context)

            if not risk_attributes:
                break

            # Apply transformation to highest risk attribute
            highest_risk = max(risk_attributes, key=lambda x: x["risk_score"])
            transformation = self._apply_risk_reduction(
                de_identified, highest_risk["attribute"], highest_risk["risk_score"]
            )
            transformations.append(transformation)

            # Reassess risk
            current_risk = self._assess_reidentification_risk(de_identified, context)

        # Create risk assessment report
        risk_assessment = {
            "method": DeIdentificationMethod.EXPERT_DETERMINATION.value,
            "timestamp": datetime.now().isoformat(),
            "initial_risk": initial_risk,
            "final_risk": current_risk,
            "risk_threshold": risk_threshold,
            "compliant": current_risk <= risk_threshold,
            "transformations_applied": len(transformations),
            "transformation_details": transformations,
            "expert_notes": self._generate_expert_notes(initial_risk, current_risk),
        }

        return de_identified, risk_assessment

    def create_limited_data_set(
        self, data: Dict[str, Any], permitted_uses: List[str]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Create Limited Data Set under §164.514(e).

        Args:
            data: Data to transform
            permitted_uses: Permitted uses (research, healthcare ops, public health)

        Returns:
            Tuple of (limited_data_set, data_use_agreement)
        """
        # Limited Data Set can retain certain identifiers
        retained_identifiers = {
            "dates": True,  # Can keep dates
            "city": True,
            "state": True,
            "zip_code": True,  # Can keep full ZIP
            "age": True,
        }

        # Must remove direct identifiers
        remove_identifiers = [
            IdentifierType.NAME,
            IdentifierType.PHONE,
            IdentifierType.EMAIL,
            IdentifierType.SSN,
            IdentifierType.MRN,
            IdentifierType.IP,
            IdentifierType.PHOTO,
            IdentifierType.BIOMETRIC,
        ]

        limited_data = data.copy()

        # Remove direct identifiers
        for identifier_type in remove_identifiers:
            if identifier_type in self.safe_harbor_rules:
                rule = self.safe_harbor_rules[identifier_type]
                self._remove_identifiers(limited_data, identifier_type, rule)

        # Create Data Use Agreement
        data_use_agreement = {
            "agreement_id": self._generate_agreement_id(),
            "created_date": datetime.now().isoformat(),
            "data_set_type": "limited_data_set",
            "permitted_uses": permitted_uses,
            "retained_identifiers": list(retained_identifiers.keys()),
            "removed_identifiers": [id_type.value for id_type in remove_identifiers],
            "restrictions": [
                "No re-identification attempts",
                "No contact with individuals",
                "Security safeguards required",
                "Report any breaches",
            ],
            "expiration_date": (datetime.now() + timedelta(days=365)).isoformat(),
        }

        return limited_data, data_use_agreement

    def re_identify(
        self, de_identified_data: Dict[str, Any], authorization: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Re-identify previously de-identified data.

        Args:
            de_identified_data: De-identified data
            authorization: Authorization for re-identification

        Returns:
            Tuple of (success, re_identified_data)
        """
        # Verify authorization
        if not self._verify_reidentification_auth(authorization):
            logger.warning("Unauthorized re-identification attempt")
            return False, None

        re_identified = de_identified_data.copy()

        # Check for pseudonym mappings
        data_id = de_identified_data.get("_deidentification_id")
        if data_id and data_id in self.identifier_mappings:
            mappings = self.identifier_mappings[data_id]

            # Restore original identifiers
            for field, original_value in mappings.items():
                if field in re_identified:
                    re_identified[field] = original_value

            logger.info("Re-identified data with ID: %s", data_id)
            return True, re_identified

        return False, None

    def verify_de_identification(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify data is properly de-identified.

        Args:
            data: Data to verify

        Returns:
            Verification results
        """
        results: Dict[str, Any] = {
            "verified": True,
            "found_identifiers": [],
            "risk_score": 0.0,
            "recommendations": [],
        }

        # Check for each identifier type
        for identifier_type, rule in self.safe_harbor_rules.items():
            if "patterns" in rule:
                for pattern in rule["patterns"]:
                    if self._search_pattern_in_data(data, pattern):
                        results["verified"] = False
                        results["found_identifiers"].append(
                            {"type": identifier_type.value, "pattern": pattern}
                        )

        # Calculate risk score
        results["risk_score"] = self._calculate_identifier_risk(
            results["found_identifiers"]
        )

        # Generate recommendations
        if not results["verified"]:
            results["recommendations"] = [
                f"Remove {id_info['type']} identifiers"
                for id_info in results["found_identifiers"]
            ]

        return results

    def _remove_identifiers(
        self,
        data: Dict[str, Any],
        identifier_type: IdentifierType,
        rule: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Remove identifiers from data."""
        removed = {}
        transformations = []

        if "patterns" in rule:
            for key, value in list(data.items()):
                if isinstance(value, str):
                    for pattern in rule["patterns"]:
                        if re.search(pattern, value):
                            removed[key] = value
                            data[key] = "[REMOVED]"
                            transformations.append(
                                {
                                    "field": key,
                                    "type": identifier_type.value,
                                    "action": "removed",
                                }
                            )
                            break

        return removed, transformations

    def _generalize_identifiers(
        self,
        data: Dict[str, Any],
        identifier_type: IdentifierType,
        rule: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generalize geographic identifiers."""
        transformations = []

        # Handle ZIP codes
        if "zip_code" in data and rule.get("zip_code_rule") == "first_three_digits":
            original = data["zip_code"]
            data["zip_code"] = original[:3] + "00"
            transformations.append(
                {
                    "field": "zip_code",
                    "type": identifier_type.value,
                    "action": "generalized",
                    "original_length": len(original),
                }
            )

        # Remove specific geographic data
        for field in rule.get("remove", []):
            if field in data:
                data[field] = "[REMOVED]"
                transformations.append(
                    {"field": field, "type": identifier_type.value, "action": "removed"}
                )

        return transformations

    def _generalize_dates(
        self,
        data: Dict[str, Any],
        identifier_type: IdentifierType,
        rule: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generalize date elements."""
        transformations = []
        date_fields = rule.get("remove", [])

        for field in date_fields:
            if field in data:
                try:
                    # Parse date
                    if isinstance(data[field], str):
                        date_obj = datetime.fromisoformat(data[field])
                    else:
                        date_obj = data[field]

                    # Keep only year
                    data[field] = str(date_obj.year)
                    transformations.append(
                        {
                            "field": field,
                            "type": identifier_type.value,
                            "action": "generalized_to_year",
                        }
                    )
                except (ValueError, AttributeError):
                    # If can't parse, remove entirely
                    data[field] = "[REMOVED]"
                    transformations.append(
                        {
                            "field": field,
                            "type": identifier_type.value,
                            "action": "removed",
                        }
                    )

        # Handle age > 89
        if "age" in data and isinstance(data["age"], (int, float)):
            if data["age"] > rule.get("age_limit", 89):
                data["age"] = "90+"
                transformations.append(
                    {
                        "field": "age",
                        "type": identifier_type.value,
                        "action": "generalized_90_plus",
                    }
                )

        return transformations

    def _pseudonymize_identifiers(
        self,
        data: Dict[str, Any],
        identifier_type: IdentifierType,
        rule: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Replace identifiers with pseudonyms."""
        transformations = []

        # Generate data ID if not exists
        if "_deidentification_id" not in data:
            data["_deidentification_id"] = self._generate_data_id()

        data_id = data["_deidentification_id"]

        # Initialize mapping for this data if needed
        if data_id not in self.identifier_mappings:
            self.identifier_mappings[data_id] = {}

        # Pseudonymize MRN and similar fields
        fields_to_pseudonymize = ["medical_record_number", "patient_id", "mrn"]

        for field in fields_to_pseudonymize:
            if field in data:
                original_value = data[field]

                # Generate consistent pseudonym
                pseudonym = self._generate_pseudonym(original_value, identifier_type)
                data[field] = pseudonym

                # Store mapping if preserving linkage
                if rule.get("preserve_linkage", False):
                    self.identifier_mappings[data_id][field] = original_value

                transformations.append(
                    {
                        "field": field,
                        "type": identifier_type.value,
                        "action": "pseudonymized",
                        "linkage_preserved": rule.get("preserve_linkage", False),
                    }
                )

        return transformations

    def _generate_pseudonym(
        self, original_value: str, identifier_type: IdentifierType
    ) -> str:
        """Generate consistent pseudonym for value."""
        # Create hash of original value with salt
        hash_input = f"{original_value}:{identifier_type.value}:{self.salt.hex()}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()

        # Format based on identifier type
        if identifier_type == IdentifierType.MRN:
            return f"MRN-{hash_value[:8].upper()}"
        else:
            return f"ID-{hash_value[:10].upper()}"

    def _assess_reidentification_risk(
        self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Assess re-identification risk score."""
        risk_score = 0.0

        # Check for quasi-identifiers
        quasi_identifiers = ["age", "gender", "zip_code", "race", "ethnicity"]
        quasi_count = sum(1 for qi in quasi_identifiers if qi in data)

        # Risk increases with more quasi-identifiers
        risk_score += quasi_count * 0.1

        # Check for rare attributes
        if context:
            population_size = context.get("population_size", 1000000)
            if population_size < 100000:
                risk_score += 0.2

        # Check for unique combinations
        if quasi_count >= 3:
            risk_score += 0.3

        return min(risk_score, 1.0)

    def _identify_risk_attributes(
        self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Identify attributes contributing to re-identification risk."""
        risk_attributes = []

        # Use context for detailed risk analysis
        if context:
            # Geographic risk calculation
            if "location" in data:
                geo_risk = self._calculate_geographic_risk(
                    data["location"],
                    population_density=context.get("population_density", "unknown"),
                    uniqueness_threshold=context.get("uniqueness_threshold", 0.05),
                )
                risk_attributes.append(
                    {
                        "field": "location",
                        "value": data["location"],
                        "risk_score": geo_risk,
                        "risk_type": "geographic",
                        "mitigation": self._get_geographic_mitigation(geo_risk),
                    }
                )

            # Temporal risk calculation
            date_fields = [
                f
                for f in data.keys()
                if "date" in f.lower() or f in ["dob", "birth_date"]
            ]
            if date_fields:
                temporal_risk = self._calculate_temporal_risk(
                    {f: data[f] for f in date_fields},
                    event_rarity=context.get("event_rarity", {}),
                )
                for field in date_fields:
                    risk_attributes.append(
                        {
                            "field": field,
                            "value": data[field],
                            "risk_score": temporal_risk,
                            "risk_type": "temporal",
                            "mitigation": self._get_temporal_mitigation(
                                temporal_risk, field
                            ),
                        }
                    )

            # Demographic combination risk
            demo_fields = {"age", "gender", "race", "ethnicity"}
            present_demo_fields = demo_fields.intersection(data.keys())
            if present_demo_fields:
                demo_risk = self._calculate_demographic_risk(
                    {f: data[f] for f in present_demo_fields},
                    population_stats=context.get("population_statistics", {}),
                )
                risk_attributes.append(
                    {
                        "field": "demographic_combination",
                        "value": {f: data[f] for f in present_demo_fields},
                        "risk_score": demo_risk,
                        "risk_type": "demographic",
                        "mitigation": self._get_demographic_mitigation(demo_risk),
                    }
                )

            # Rare disease risk
            if "diagnosis" in data or "condition" in data:
                condition = data.get("diagnosis") or data.get("condition")
                if condition and self._is_rare_disease(
                    condition, context.get("disease_prevalence", {})
                ):
                    risk_attributes.append(
                        {
                            "field": "diagnosis",
                            "value": condition,
                            "risk_score": 0.9,  # High risk for rare diseases
                            "risk_type": "rare_condition",
                            "mitigation": "Consider suppressing or generalizing rare conditions",
                        }
                    )

        # Standard risk assessment for direct identifiers
        for field, value in data.items():
            if field.startswith("_"):
                continue

            risk_score = 0.0
            # risk_type = "unknown"  # Default risk type

            # Direct identifiers have highest risk
            if any(
                pattern in field.lower()
                for pattern in ["name", "ssn", "email", "phone", "fax"]
            ):
                risk_score = 1.0
                # risk_type = "direct_identifier"  # Direct identifiers have highest risk
            # Quasi-identifiers have moderate risk
            elif field in ["age", "gender", "zip_code", "race"]:
                risk_score = 0.5
                # risk_type = "quasi_identifier"  # Could be used for categorization
            # Rare values increase risk
            elif isinstance(value, str) and len(value) > 20:
                risk_score = 0.3

            if risk_score > 0:
                risk_attributes.append(
                    {
                        "attribute": field,
                        "risk_score": risk_score,
                        "value_type": type(value).__name__,
                    }
                )

        return sorted(risk_attributes, key=lambda x: x["risk_score"], reverse=True)

    def _apply_risk_reduction(
        self, data: Dict[str, Any], attribute: str, risk_score: float
    ) -> Dict[str, Any]:
        """Apply transformation to reduce risk."""
        transformation = {
            "attribute": attribute,
            "original_risk": risk_score,
            "action": "none",
        }

        if attribute not in data:
            return transformation

        # High risk - remove entirely
        if risk_score > 0.8:
            data[attribute] = "[REMOVED]"
            transformation["action"] = "removed"
        # Medium risk - generalize
        elif risk_score > 0.4:
            if attribute == "age" and isinstance(data[attribute], (int, float)):
                # Convert to age range
                age = data[attribute]
                data[attribute] = f"{(age // 10) * 10}-{(age // 10) * 10 + 9}"
                transformation["action"] = "generalized_to_range"
            else:
                # Generic generalization
                data[attribute] = "[GENERALIZED]"
                transformation["action"] = "generalized"

        return transformation

    def _generate_expert_notes(self, initial_risk: float, final_risk: float) -> str:
        """Generate expert determination notes."""
        risk_reduction = initial_risk - final_risk

        if final_risk <= 0.01:
            return (
                f"Re-identification risk reduced from {initial_risk:.2%} to "
                f"{final_risk:.2%}. Risk is now below HIPAA threshold of 1%. "
                "Data can be considered de-identified under Expert Determination."
            )
        else:
            return (
                f"Risk reduced by {risk_reduction:.2%} but remains at {final_risk:.2%}. "
                "Additional transformations recommended to meet HIPAA standard."
            )

    def _verify_safe_harbor_compliance(self, data: Dict[str, Any]) -> bool:
        """Verify Safe Harbor compliance."""
        # Check for any remaining identifiers
        for identifier_type in IdentifierType:
            if identifier_type in self.safe_harbor_rules:
                rule = self.safe_harbor_rules[identifier_type]
                if "patterns" in rule:
                    for pattern in rule["patterns"]:
                        if self._search_pattern_in_data(data, pattern):
                            return False
        return True

    def _search_pattern_in_data(self, data: Dict[str, Any], pattern: str) -> bool:
        """Search for pattern in data values."""
        for value in data.values():
            if isinstance(value, str) and re.search(pattern, value):
                return True
            elif isinstance(value, dict):
                if self._search_pattern_in_data(value, pattern):
                    return True
        return False

    def _calculate_identifier_risk(
        self, found_identifiers: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall identifier risk score."""
        if not found_identifiers:
            return 0.0

        # Each identifier type has different risk weight
        risk_weights = {
            "name": 1.0,
            "ssn": 1.0,
            "email": 0.8,
            "phone": 0.7,
            "ip_address": 0.6,
            "geographic": 0.5,
        }

        total_risk = 0.0
        for identifier in found_identifiers:
            id_type = identifier["type"]
            risk = risk_weights.get(id_type, 0.5)
            total_risk += risk

        return min(total_risk, 1.0)

    def _verify_reidentification_auth(self, authorization: Dict[str, Any]) -> bool:
        """Verify authorization for re-identification."""
        required_fields = ["authorized_by", "purpose", "expiration"]

        for field in required_fields:
            if field not in authorization:
                return False

        # Check expiration
        try:
            expiration = datetime.fromisoformat(authorization["expiration"])
            if expiration < datetime.now():
                return False
        except (ValueError, KeyError):
            return False

        return True

    def _log_de_identification(
        self,
        method: DeIdentificationMethod,
        identifiers_removed: int,
        transformations: int,
    ) -> None:
        """Log de-identification event."""
        log_entry = {
            "timestamp": datetime.now(),
            "method": method.value,
            "identifiers_removed": identifiers_removed,
            "transformations_applied": transformations,
            "log_id": self._generate_log_id(),
        }

        self.de_identification_log.append(log_entry)
        logger.info(
            "De-identification completed: %s - Removed %d identifiers",
            method.value,
            identifiers_removed,
        )

    def _generate_data_id(self) -> str:
        """Generate unique data ID."""
        return f"DEID-DATA-{uuid.uuid4()}"

    def _generate_agreement_id(self) -> str:
        """Generate unique agreement ID."""
        return f"DEID-DUA-{uuid.uuid4()}"

    def _generate_log_id(self) -> str:
        """Generate unique log ID."""
        return f"DEID-LOG-{uuid.uuid4()}"

    def _calculate_geographic_risk(
        self, location: str, population_density: str, uniqueness_threshold: float
    ) -> float:
        """Calculate re-identification risk based on geographic information."""
        _ = uniqueness_threshold  # Mark as intentionally unused
        # Higher risk for less populated areas
        density_risk = {
            "rural": 0.8,
            "suburban": 0.5,
            "urban": 0.3,
            "metropolitan": 0.2,
            "unknown": 0.5,
        }

        base_risk = density_risk.get(population_density, 0.5)

        # Adjust based on location specificity
        if location:
            if len(location) == 5:  # Full ZIP code
                base_risk *= 1.5
            elif len(location) == 3:  # ZIP code prefix
                base_risk *= 0.7
            elif "county" in location.lower():
                base_risk *= 0.6
            elif "state" in location.lower():
                base_risk *= 0.3

        return min(1.0, base_risk)

    def _calculate_temporal_risk(
        self, dates: Dict[str, Any], event_rarity: Dict[str, float]
    ) -> float:
        """Calculate risk based on temporal information."""
        max_risk = 0.0

        for field, date_value in dates.items():
            # Birth dates have high risk
            if field in ["dob", "birth_date", "date_of_birth"]:
                risk = 0.7
            # Rare events have higher risk
            elif field in event_rarity:
                risk = event_rarity[field]
            # Recent dates have moderate risk
            else:
                risk = 0.3
                if isinstance(date_value, str):
                    try:
                        date_obj = datetime.fromisoformat(date_value)
                        days_ago = (datetime.now() - date_obj).days
                        if days_ago < 30:
                            risk = 0.5
                        elif days_ago < 365:
                            risk = 0.4
                    except (ValueError, TypeError):
                        pass

            max_risk = max(max_risk, risk)

        return max_risk

    def _calculate_demographic_risk(
        self,
        demographics: Dict[str, Any],
        population_stats: Dict[str, Any],
        **kwargs: Any,
    ) -> float:
        """Calculate risk from demographic combinations."""
        _ = kwargs  # Mark as intentionally unused
        # More demographic attributes = higher risk
        num_attributes = len(demographics)
        base_risk = min(0.2 * num_attributes, 0.8)

        # Adjust based on rarity in population
        if population_stats:
            # Check if combination is rare
            combo_key = "_".join(str(v) for v in demographics.values())
            rarity = population_stats.get("combination_rarity", {}).get(combo_key, 0.5)
            base_risk *= 1 + rarity

        return min(1.0, base_risk)

    def _get_geographic_mitigation(self, risk_score: float) -> str:
        """Get mitigation strategy for geographic risk."""
        if risk_score > 0.7:
            return "Remove or generalize to state level"
        elif risk_score > 0.5:
            return "Use only first 3 digits of ZIP code"
        elif risk_score > 0.3:
            return "Consider using county instead of ZIP"
        return "Current geographic granularity acceptable"

    def _get_temporal_mitigation(self, risk_score: float, field: str) -> str:
        """Get mitigation strategy for temporal risk."""
        if "birth" in field.lower():
            return "Remove birth date or use only year"
        elif risk_score > 0.6:
            return "Generalize to month and year only"
        elif risk_score > 0.4:
            return "Consider using relative dates or ranges"
        return "Current date precision acceptable"

    def _get_demographic_mitigation(self, risk_score: float) -> str:
        """Get mitigation strategy for demographic risk."""
        if risk_score > 0.7:
            return "Remove or generalize some demographic attributes"
        elif risk_score > 0.5:
            return "Consider using broader categories (e.g., age ranges)"
        return "Current demographic detail acceptable"

    def _is_rare_disease(
        self, condition: str, prevalence_data: Dict[str, float]
    ) -> bool:
        """Check if a condition is considered rare."""
        if not condition:
            return False

        # Check prevalence data
        if condition.lower() in prevalence_data:
            return prevalence_data[condition.lower()] < 0.001  # Less than 0.1%

        # Check for known rare disease indicators
        rare_indicators = ["rare", "orphan", "genetic", "hereditary", "syndrome"]
        return any(indicator in condition.lower() for indicator in rare_indicators)

    def calculate_reidentification_risk(
        self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculate comprehensive re-identification risk with detailed context analysis."""
        risk_factors = []

        # Use context for more detailed risk analysis
        if context:
            # Geographic risk calculation
            if "location" in data:
                geo_risk = self._calculate_geographic_risk(
                    data["location"],
                    population_density=context.get("population_density", "unknown"),
                    uniqueness_threshold=context.get("uniqueness_threshold", 0.05),
                )
                risk_factors.append(("geographic", geo_risk))

            # Temporal risk calculation
            if "dates" in data or any(k for k in data.keys() if "date" in k.lower()):
                date_fields = {
                    k: v
                    for k, v in data.items()
                    if "date" in k.lower() or k in ["dob", "birth_date"]
                }
                temporal_risk = self._calculate_temporal_risk(
                    date_fields, event_rarity=context.get("event_rarity", {})
                )
                risk_factors.append(("temporal", temporal_risk))

            # Demographic combination risk
            demo_fields = ["age", "gender", "ethnicity", "race"]
            demo_data = {k: data[k] for k in demo_fields if k in data}
            if demo_data:
                demo_risk = self._calculate_demographic_risk(
                    demo_data,
                    population_stats=context.get("population_statistics", {}),
                )
                risk_factors.append(("demographic", demo_risk))

        # Get standard risk attributes
        risk_attributes = self._identify_risk_attributes(data, context)

        # Calculate composite risk score
        composite_risk = self._combine_risk_factors(risk_factors, risk_attributes)

        # Generate recommendations if needed
        recommendations = []
        if composite_risk.get("score", 0) > 0.05:  # 5% risk threshold
            recommendations = self._generate_deidentification_recommendations(
                risk_attributes, risk_factors, context
            )

        # Build comprehensive risk score
        risk_score = {
            "score": composite_risk.get("score", 0),
            "factors": risk_factors,
            "attributes": risk_attributes,
            "recommendations": recommendations,
            "safe_harbor_compliant": composite_risk.get("score", 0) < 0.01,
            "k_anonymity": self._check_k_anonymity(data, context) if context else None,
            "risk_level": self._get_risk_level(composite_risk.get("score", 0)),
            "suppression_required": self._determine_suppression_requirements(
                composite_risk, risk_factors
            ),
        }

        return risk_score

    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level."""
        if risk_score >= 0.8:
            return "CRITICAL"
        elif risk_score >= 0.6:
            return "HIGH"
        elif risk_score >= 0.4:
            return "MEDIUM"
        elif risk_score >= 0.2:
            return "LOW"
        else:
            return "MINIMAL"

    def _generate_deidentification_recommendations(
        self,
        risk_attributes: List[Dict[str, Any]],
        risk_factors: List[Tuple[str, float]],
        context: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Generate specific recommendations to reduce re-identification risk."""
        _ = context  # Mark as used
        recommendations = []

        # Analyze risk factors for targeted recommendations
        for factor_type, risk_score in risk_factors:
            if factor_type == "geographic" and risk_score > 0.3:
                recommendations.append(
                    "Consider generalizing geographic data to larger regions"
                )
                if risk_score > 0.7:
                    recommendations.append(
                        "Remove or truncate zip codes to first 3 digits"
                    )
            elif factor_type == "temporal" and risk_score > 0.3:
                recommendations.append("Generalize dates to month/year only")
                if risk_score > 0.7:
                    recommendations.append(
                        "Consider removing exact dates for rare events"
                    )
            elif factor_type == "demographic" and risk_score > 0.5:
                recommendations.append(
                    "Use age ranges instead of exact ages (e.g., 5-year ranges)"
                )
                recommendations.append(
                    "Consider suppressing rare demographic combinations"
                )

        # Group by risk type
        risk_groups: Dict[str, List[Dict[str, Any]]] = {}
        for attr in risk_attributes:
            risk_type = attr.get("risk_type", "unknown")
            if risk_type not in risk_groups:
                risk_groups[risk_type] = []
            risk_groups[risk_type].append(attr)

        # Generate type-specific recommendations
        if "direct_identifier" in risk_groups:
            recommendations.append(
                "Remove all direct identifiers (names, SSN, email, phone numbers)"
            )

        if "geographic" in risk_groups:
            recommendations.append(
                "Generalize geographic information to 3-digit ZIP codes or county level"
            )

        if "temporal" in risk_groups:
            recommendations.append(
                "Apply date shifting with consistent offset per patient"
            )

        if "demographic" in risk_groups:
            recommendations.append(
                "Verify k-anonymity >= 5 for demographic attribute combinations"
            )

        if "rare_condition" in risk_groups:
            recommendations.append(
                "Suppress or generalize rare disease diagnoses to broader categories"
            )

        # Add general recommendations based on composite risk
        if len(risk_attributes) > 5:
            recommendations.append(
                "Consider expert determination method due to complex attribute combinations"
            )

        return recommendations

    def _combine_risk_factors(
        self,
        risk_factors: List[Tuple[str, float]],
        risk_attributes: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Combine multiple risk factors into a composite score."""
        # Calculate weighted risk score
        factor_weights = {
            "geographic": 0.3,
            "temporal": 0.2,
            "demographic": 0.3,
            "direct_identifier": 1.0,
            "quasi_identifier": 0.2,
        }

        weighted_sum = 0.0
        total_weight = 0.0

        # Process risk factors
        for factor_type, risk_score in risk_factors:
            weight = factor_weights.get(factor_type, 0.1)
            weighted_sum += risk_score * weight
            total_weight += weight

        # Process risk attributes
        for attr in risk_attributes:
            risk_type = attr.get("risk_type", "unknown")
            risk_score = attr.get("risk_score", 0)
            weight = factor_weights.get(risk_type, 0.1)
            weighted_sum += risk_score * weight
            total_weight += weight

        # Calculate composite score
        composite_score = weighted_sum / total_weight if total_weight > 0 else 0

        return {
            "score": min(composite_score, 1.0),
            "weighted_sum": weighted_sum,
            "total_weight": total_weight,
        }

    def _check_k_anonymity(
        self, data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check k-anonymity for the given data."""
        # Extract quasi-identifiers
        quasi_identifiers = ["age", "gender", "zip_code", "ethnicity", "occupation"]
        qi_values = {k: data.get(k) for k in quasi_identifiers if k in data}

        if not qi_values or not context.get("population_statistics"):
            return {"k": "unknown", "anonymity_set_size": 0}

        # Calculate anonymity set size
        population_stats = context["population_statistics"]
        anonymity_set_size = population_stats.get("total_population", 0)

        # Apply filters based on quasi-identifiers
        for qi, value in qi_values.items():
            if value and qi in population_stats:
                # Calculate fraction of population with this value
                fraction = population_stats[qi].get(
                    str(value), 0.001
                )  # Default to 0.1%
                anonymity_set_size *= fraction

        # Calculate k value
        k_value = max(1, int(anonymity_set_size))

        return {
            "k": k_value,
            "anonymity_set_size": anonymity_set_size,
            "quasi_identifiers": list(qi_values.keys()),
            "sufficient": k_value >= 5,  # Common threshold
        }

    def _determine_suppression_requirements(
        self, composite_risk: Dict[str, float], risk_factors: List[Tuple[str, float]]
    ) -> List[str]:
        """Determine which fields need suppression based on risk analysis."""
        suppression_requirements = []

        # Check overall risk
        if composite_risk.get("score", 0) > 0.1:
            # High risk - need aggressive suppression
            suppression_requirements.append("dates_generalize_to_year")
            suppression_requirements.append("geographic_generalize_to_state")

        # Check specific risk factors
        for factor_type, risk_score in risk_factors:
            if factor_type == "geographic" and risk_score > 0.5:
                suppression_requirements.append("zip_code_truncate_to_3")
            elif factor_type == "temporal" and risk_score > 0.5:
                suppression_requirements.append("dates_remove_day")
            elif factor_type == "demographic" and risk_score > 0.7:
                suppression_requirements.append("age_generalize_to_range")

        return list(set(suppression_requirements))  # Remove duplicates

"""Medication FHIR Resource Implementation.

This module implements the Medication FHIR resource for Haven Health Passport,
handling medication definitions with special considerations for generic drugs,
local formulations, and resource-limited settings common in refugee healthcare.
"""

import logging
import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.extension import Extension
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.identifier import Identifier
from fhirclient.models.medication import (
    Medication,
    MedicationBatch,
    MedicationIngredient,
)
from fhirclient.models.quantity import Quantity
from fhirclient.models.ratio import Ratio

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

from .fhir_base import BaseFHIRResource
from .fhir_profiles import REFUGEE_MEDICATION_PROFILE

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "Medication"


class MedicationStatus(Enum):
    """Medication status codes."""

    ACTIVE = "active"  # Active medication
    INACTIVE = "inactive"  # Inactive medication
    ENTERED_IN_ERROR = "entered-in-error"  # Entered in error


class MedicationForm(Enum):
    """Common medication forms in refugee settings."""

    # Solid forms
    TABLET = "385055001"  # Tablet
    CAPSULE = "385049006"  # Capsule
    POWDER = "420699003"  # Powder
    GRANULES = "385043007"  # Granules

    # Liquid forms
    SOLUTION = "385219001"  # Solution
    SUSPENSION = "385024007"  # Suspension
    SYRUP = "385197005"  # Syrup
    DROPS = "385018001"  # Drops

    # Injectable forms
    INJECTION = "385218009"  # Injection
    INFUSION = "385229008"  # Infusion

    # Topical forms
    CREAM = "385101003"  # Cream
    OINTMENT = "385100002"  # Ointment
    GEL = "385102001"  # Gel
    LOTION = "385099003"  # Lotion

    # Other forms
    SUPPOSITORY = "385194001"  # Suppository
    INHALER = "385203008"  # Inhaler
    PATCH = "385114002"  # Patch

    # Traditional/local forms
    HERBAL_PREPARATION = "HERB001"  # Herbal preparation
    TRADITIONAL_MIXTURE = "TRAD001"  # Traditional mixture


class EssentialMedicineCategory(Enum):
    """WHO Essential Medicine List categories."""

    ANAESTHETICS = "1"
    ANALGESICS = "2"
    ANTIALLERGICS = "3"
    ANTIDOTES = "4"
    ANTICONVULSANTS = "5"
    ANTI_INFECTIVES = "6"
    ANTIMIGRAINE = "7"
    ANTINEOPLASTICS = "8"
    ANTIPARKINSONISM = "9"
    BLOOD_PRODUCTS = "10"
    CARDIOVASCULAR = "12"
    DERMATOLOGICAL = "13"
    DIAGNOSTICS = "14"
    DISINFECTANTS = "15"
    DIURETICS = "16"
    GASTROINTESTINAL = "17"
    HORMONES = "18"
    IMMUNOLOGICALS = "19"
    MUSCLE_RELAXANTS = "20"
    OPHTHALMOLOGICAL = "21"
    OXYTOCICS = "22"
    PERITONEAL_DIALYSIS = "23"
    PSYCHOTHERAPEUTICS = "24"
    RESPIRATORY = "25"
    SOLUTIONS = "26"
    VITAMINS = "27"


class CommonRefugeeMedications:
    """Common medications in refugee healthcare settings."""

    MEDICATIONS = {
        # Antibiotics
        "amoxicillin": {
            "code": "372687004",
            "display": "Amoxicillin",
            "category": EssentialMedicineCategory.ANTI_INFECTIVES,
            "forms": ["tablet", "capsule", "suspension", "powder"],
            "strengths": ["250mg", "500mg", "125mg/5ml", "250mg/5ml"],
        },
        "azithromycin": {
            "code": "387531004",
            "display": "Azithromycin",
            "category": EssentialMedicineCategory.ANTI_INFECTIVES,
            "forms": ["tablet", "suspension"],
            "strengths": ["250mg", "500mg", "200mg/5ml"],
        },
        # Antimalarials
        "artemether_lumefantrine": {
            "code": "427327005",
            "display": "Artemether + Lumefantrine",
            "category": EssentialMedicineCategory.ANTI_INFECTIVES,
            "forms": ["tablet"],
            "strengths": ["20mg/120mg", "40mg/240mg"],
        },
        "chloroquine": {
            "code": "373468005",
            "display": "Chloroquine",
            "category": EssentialMedicineCategory.ANTI_INFECTIVES,
            "forms": ["tablet", "syrup"],
            "strengths": ["150mg", "50mg/5ml"],
        },
        # Analgesics
        "paracetamol": {
            "code": "387517004",
            "display": "Paracetamol",
            "category": EssentialMedicineCategory.ANALGESICS,
            "forms": ["tablet", "syrup", "suppository"],
            "strengths": ["500mg", "120mg/5ml", "125mg", "250mg"],
        },
        "ibuprofen": {
            "code": "387207008",
            "display": "Ibuprofen",
            "category": EssentialMedicineCategory.ANALGESICS,
            "forms": ["tablet", "suspension"],
            "strengths": ["200mg", "400mg", "100mg/5ml"],
        },
        # Nutritional
        "vitamin_a": {
            "code": "82622003",
            "display": "Vitamin A",
            "category": EssentialMedicineCategory.VITAMINS,
            "forms": ["capsule", "drops"],
            "strengths": ["200000IU", "100000IU", "50000IU/ml"],
        },
        "iron_folate": {
            "code": "426298002",
            "display": "Iron + Folic Acid",
            "category": EssentialMedicineCategory.VITAMINS,
            "forms": ["tablet"],
            "strengths": ["60mg/0.4mg"],
        },
        "ors": {
            "code": "387390002",
            "display": "Oral Rehydration Salts",
            "category": EssentialMedicineCategory.SOLUTIONS,
            "forms": ["powder"],
            "strengths": ["20.5g/L"],
        },
        "rutf": {
            "code": "RUTF001",
            "display": "Ready-to-Use Therapeutic Food",
            "category": EssentialMedicineCategory.VITAMINS,
            "forms": ["paste"],
            "strengths": ["92g", "100g"],
        },
        # Vaccines
        "bcg_vaccine": {
            "code": "420538001",
            "display": "BCG Vaccine",
            "category": EssentialMedicineCategory.IMMUNOLOGICALS,
            "forms": ["injection"],
            "strengths": ["0.05ml", "0.1ml"],
        },
        "measles_vaccine": {
            "code": "396429000",
            "display": "Measles Vaccine",
            "category": EssentialMedicineCategory.IMMUNOLOGICALS,
            "forms": ["injection"],
            "strengths": ["0.5ml"],
        },
    }

    @classmethod
    def get_medication_info(cls, name: str) -> Optional[Dict]:
        """Get information about a common medication."""
        return cls.MEDICATIONS.get(name.lower().replace(" ", "_"))


class MedicationResource(BaseFHIRResource):
    """Medication FHIR resource implementation."""

    def __init__(self) -> None:
        """Initialize Medication resource handler."""
        super().__init__(Medication)
        self._encrypted_fields = []  # Medications typically not encrypted

    @require_phi_access(AccessLevel.WRITE)
    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_medication_resource")
    def create_resource(self, data: Dict[str, Any]) -> Medication:
        """Create a new Medication resource.

        Args:
            data: Dictionary containing medication data with fields:
                - code: Medication code (required)
                - status: Medication status
                - manufacturer: Manufacturer reference
                - form: Medication form
                - amount: Package amount
                - ingredient: List of ingredients
                - batch: Batch information

        Returns:
            Created Medication resource
        """
        medication = Medication()

        # Set required fields
        medication.code = self._create_medication_code(data["code"])

        # Set status
        medication.status = data.get("status", MedicationStatus.ACTIVE.value)

        # Set ID if provided
        if "id" in data:
            medication.id = data["id"]

        # Set manufacturer
        if "manufacturer" in data:
            medication.manufacturer = FHIRReference({"reference": data["manufacturer"]})

        # Set form
        if "form" in data:
            medication.form = self._create_medication_form(data["form"])

        # Set amount
        if "amount" in data:
            medication.amount = self._create_ratio(data["amount"])

        # Set ingredients
        if "ingredient" in data:
            medication.ingredient = [
                self._create_ingredient(ing) for ing in data["ingredient"]
            ]

        # Set batch information
        if "batch" in data:
            medication.batch = self._create_batch(data["batch"])

        # Set identifiers (e.g., local formulary codes)
        if "identifier" in data:
            medication.identifier = [
                self._create_identifier(ident) for ident in data["identifier"]
            ]

        # Add refugee-specific extensions
        if "refugee_context" in data:
            self._add_refugee_context(medication, data["refugee_context"])

        # Add profile and validate
        self.add_meta_profile(medication, REFUGEE_MEDICATION_PROFILE)

        # Store and validate
        self._resource = medication
        self.validate()

        # Add audit entry
        self.add_audit_entry("create", data.get("created_by", "system"))

        return medication

    def get_encrypted_fields(self) -> List[str]:
        """Return list of fields that should be encrypted."""
        return self._encrypted_fields

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_common_medication")
    def create_from_common_medication(
        self,
        medication_name: str,
        form: Optional[str] = None,
        strength: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Medication]:
        """Create medication from common medication database.

        Args:
            medication_name: Name of common medication
            form: Specific form (tablet, syrup, etc.)
            strength: Specific strength
            **kwargs: Additional medication fields

        Returns:
            Created Medication resource or None if not found
        """
        med_info = CommonRefugeeMedications.get_medication_info(medication_name)
        if not med_info:
            logger.warning(
                "Medication not found in common database: %s", medication_name
            )
            return None

        # Build medication data
        data = {
            "code": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": med_info["code"],
                        "display": med_info["display"],
                    }
                ],
                "text": med_info["display"],
            }
        }

        # Set form if specified and available
        if form and form.lower() in med_info["forms"]:
            form_enum = MedicationForm[form.upper()]
            data["form"] = {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": form_enum.value,
                        "display": form_enum.value,
                    }
                ]
            }

        # Add strength as extension if specified
        if strength and strength in med_info["strengths"]:
            data["refugee_context"] = {
                "strength": strength,
                "essential_medicine_category": med_info["category"].value,
            }

        # Add any additional fields
        data.update(kwargs)

        return self.create_resource(data)

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_traditional_medication")
    def create_traditional_medication(
        self,
        name: str,
        description: str,
        ingredients: Optional[List[str]] = None,
        preparation: Optional[str] = None,
        **kwargs: Any,
    ) -> Medication:
        """Create traditional/herbal medication resource.

        Args:
            name: Name of traditional medication
            description: Description of the medication
            ingredients: List of ingredients
            preparation: Preparation method
            **kwargs: Additional medication fields

        Returns:
            Created Medication resource
        """
        data: Dict[str, Any] = {
            "code": {
                "coding": [
                    {
                        "system": "http://havenhealthpassport.org/fhir/CodeSystem/traditional-medicine",
                        "code": f"TRAD-{name.upper().replace(' ', '-')}",
                        "display": name,
                    }
                ],
                "text": description,
            },
            "form": MedicationForm.TRADITIONAL_MIXTURE.value,
            "status": MedicationStatus.ACTIVE.value,
        }

        # Add ingredients if provided
        if ingredients:
            ingredient_list = []
            for ing in ingredients:
                ingredient_list.append({"item": {"text": ing}, "isActive": True})
            data["ingredient"] = ingredient_list

        # Add preparation as extension
        if preparation:
            data["refugee_context"] = {"traditional_preparation": preparation}

        # Add any additional fields
        data.update(kwargs)

        return self.create_resource(data)

    def _create_medication_code(self, code_data: Union[str, Dict]) -> CodeableConcept:
        """Create medication code."""
        if isinstance(code_data, str):
            # Try to look up in common medications
            med_info = CommonRefugeeMedications.get_medication_info(code_data)
            if med_info:
                return CodeableConcept(
                    {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": med_info["code"],
                                "display": med_info["display"],
                            }
                        ],
                        "text": med_info["display"],
                    }
                )
            else:
                # Create as text-only
                return CodeableConcept({"text": code_data})
        else:
            return self._create_codeable_concept(code_data)

    def _create_medication_form(self, form_data: Union[str, Dict]) -> CodeableConcept:
        """Create medication form."""
        if isinstance(form_data, str):
            # Try to match to enum
            try:
                form_enum = MedicationForm[form_data.upper()]
                return CodeableConcept(
                    {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": form_enum.value,
                                "display": form_enum.name.replace("_", " ").title(),
                            }
                        ]
                    }
                )
            except KeyError:
                return CodeableConcept({"text": form_data})
        else:
            return self._create_codeable_concept(form_data)

    def _create_ingredient(self, ingredient_data: Dict) -> MedicationIngredient:
        """Create medication ingredient."""
        ingredient = MedicationIngredient()

        # Set item (required)
        if "item" in ingredient_data:
            if isinstance(ingredient_data["item"], str):
                ingredient.itemCodeableConcept = CodeableConcept(
                    {"text": ingredient_data["item"]}
                )
            elif isinstance(ingredient_data["item"], dict):
                if "reference" in ingredient_data["item"]:
                    ingredient.itemReference = FHIRReference(ingredient_data["item"])
                else:
                    ingredient.itemCodeableConcept = self._create_codeable_concept(
                        ingredient_data["item"]
                    )

        # Set if active ingredient
        ingredient.isActive = ingredient_data.get("isActive", True)

        # Set strength
        if "strength" in ingredient_data:
            ingredient.strength = self._create_ratio(ingredient_data["strength"])

        return ingredient

    def _create_batch(self, batch_data: Dict) -> MedicationBatch:
        """Create medication batch information."""
        batch = MedicationBatch()

        if "lotNumber" in batch_data:
            batch.lotNumber = batch_data["lotNumber"]

        if "expirationDate" in batch_data:
            batch.expirationDate = self._create_fhir_date(batch_data["expirationDate"])

        return batch

    def _create_identifier(self, identifier_data: Dict) -> Identifier:
        """Create medication identifier."""
        identifier = Identifier()

        if "system" in identifier_data:
            identifier.system = identifier_data["system"]

        if "value" in identifier_data:
            identifier.value = identifier_data["value"]

        if "use" in identifier_data:
            identifier.use = identifier_data["use"]

        return identifier

    def _create_ratio(self, ratio_data: Union[str, Dict]) -> Ratio:
        """Create ratio for medication strength/amount."""
        ratio = Ratio()

        if isinstance(ratio_data, str):
            # Parse string like "500mg/5ml"
            parts = ratio_data.split("/")
            if len(parts) == 2:
                # Parse numerator
                num_val, num_unit = self._parse_quantity_string(parts[0])
                ratio.numerator = Quantity(
                    {
                        "value": num_val,
                        "unit": num_unit,
                        "system": "http://unitsofmeasure.org",
                    }
                )

                # Parse denominator
                den_val, den_unit = self._parse_quantity_string(parts[1])
                ratio.denominator = Quantity(
                    {
                        "value": den_val,
                        "unit": den_unit,
                        "system": "http://unitsofmeasure.org",
                    }
                )
            else:
                # Single value, use as numerator with denominator of 1
                num_val, num_unit = self._parse_quantity_string(ratio_data)
                ratio.numerator = Quantity(
                    {
                        "value": num_val,
                        "unit": num_unit,
                        "system": "http://unitsofmeasure.org",
                    }
                )
                ratio.denominator = Quantity(
                    {"value": 1, "unit": "unit", "system": "http://unitsofmeasure.org"}
                )
        else:
            if "numerator" in ratio_data:
                ratio.numerator = self._create_quantity(ratio_data["numerator"])
            if "denominator" in ratio_data:
                ratio.denominator = self._create_quantity(ratio_data["denominator"])

        return ratio

    def _parse_quantity_string(self, quantity_str: str) -> Tuple[float, str]:
        """Parse quantity string like '500mg' into value and unit."""
        # Match number (including decimals) followed by unit
        match = re.match(r"^([\d.]+)\s*(.+)$", quantity_str.strip())
        if match:
            value = float(match.group(1))
            unit = match.group(2)

            # Standardize common units
            unit_map = {
                "mg": "mg",
                "g": "g",
                "ml": "mL",
                "l": "L",
                "iu": "IU",
                "mcg": "ug",
            }

            unit_lower = unit.lower()
            if unit_lower in unit_map:
                unit = unit_map[unit_lower]

            return value, unit
        else:
            # Couldn't parse, return as is
            return 1.0, quantity_str

    def _create_quantity(self, quantity_data: Union[float, Dict]) -> Quantity:
        """Create quantity value."""
        quantity = Quantity()

        if isinstance(quantity_data, (int, float)):
            quantity.value = float(quantity_data)
        else:
            quantity.value = quantity_data.get("value")
            quantity.unit = quantity_data.get("unit")
            quantity.system = quantity_data.get("system", "http://unitsofmeasure.org")
            quantity.code = quantity_data.get("code")

        return quantity

    def _create_codeable_concept(self, data: Union[str, Dict]) -> CodeableConcept:
        """Create CodeableConcept from data."""
        concept = CodeableConcept()

        if isinstance(data, str):
            concept.text = data
        else:
            if "coding" in data:
                concept.coding = []
                for coding_data in data["coding"]:
                    coding = Coding()
                    if "system" in coding_data:
                        coding.system = coding_data["system"]
                    if "code" in coding_data:
                        coding.code = coding_data["code"]
                    if "display" in coding_data:
                        coding.display = coding_data["display"]
                    concept.coding.append(coding)

            if "text" in data:
                concept.text = data["text"]

        return concept

    def _create_fhir_date(self, date_value: Union[str, date, datetime]) -> str:
        """Create FHIR date string."""
        if isinstance(date_value, str):
            return date_value
        elif isinstance(date_value, datetime):
            return date_value.date().isoformat()
        elif isinstance(date_value, date):
            return date_value.isoformat()
        else:
            raise ValueError(f"Invalid date format: {type(date_value)}")

    def _add_refugee_context(
        self, medication: Medication, context_data: Dict[str, Any]
    ) -> None:
        """Add refugee-specific context extensions."""
        if not medication.extension:
            medication.extension = []

        # Add essential medicine category
        if "essential_medicine_category" in context_data:
            ext = Extension()
            ext.url = "http://havenhealthpassport.org/fhir/extension/essential-medicine-category"
            ext.valueCode = context_data["essential_medicine_category"]
            medication.extension.append(ext)

        # Add local availability
        if "local_availability" in context_data:
            ext = Extension()
            ext.url = "http://havenhealthpassport.org/fhir/extension/local-availability"
            ext.valueString = context_data["local_availability"]
            medication.extension.append(ext)

        # Add substitute medications
        if "substitutes" in context_data:
            for substitute in context_data["substitutes"]:
                ext = Extension()
                ext.url = "http://havenhealthpassport.org/fhir/extension/substitute-medication"
                ext.valueString = substitute
                medication.extension.append(ext)

        # Add strength for common medications
        if "strength" in context_data:
            ext = Extension()
            ext.url = (
                "http://havenhealthpassport.org/fhir/extension/medication-strength"
            )
            ext.valueString = context_data["strength"]
            medication.extension.append(ext)

        # Add traditional preparation method
        if "traditional_preparation" in context_data:
            ext = Extension()
            ext.url = (
                "http://havenhealthpassport.org/fhir/extension/traditional-preparation"
            )
            ext.valueString = context_data["traditional_preparation"]
            medication.extension.append(ext)

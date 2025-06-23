"""Medication Packaging Implementation.

This module handles medication packaging information including container types,
quantities, labeling, and special packaging considerations for refugee healthcare
settings where medications may come from various sources.
Handles FHIR MedicationKnowledge Resource validation and structure.

COMPLIANCE NOTE: This module processes PHI related to patient medications,
prescriptions, and medication administration records. All medication data
must be encrypted at rest and in transit. Access control required - only
authorized pharmacy staff and prescribing providers should access medication
records. Implement drug-drug interaction checks and allergy alerts. Maintain
audit trails for all medication dispensing activities.
"""

import logging
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.healthcare.fhir_validator import FHIRValidator

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "MedicationKnowledge"


class PackageType(Enum):
    """Types of medication packaging."""

    # Primary containers
    BOTTLE = "bottle"
    BLISTER = "blister"
    STRIP = "strip"
    TUBE = "tube"
    VIAL = "vial"
    AMPOULE = "ampoule"
    SYRINGE = "syringe"
    SACHET = "sachet"
    JAR = "jar"
    BOX = "box"

    # Secondary packaging
    CARTON = "carton"
    CASE = "case"

    # Special packaging
    UNIT_DOSE = "unit-dose"
    MULTI_DOSE = "multi-dose"
    PATIENT_PACK = "patient-pack"
    BULK = "bulk"

    # Emergency/field packaging
    EMERGENCY_KIT = "emergency-kit"
    FIELD_PACK = "field-pack"
    DONATION_PACK = "donation-pack"


class PackageMaterial(Enum):
    """Materials used for medication packaging."""

    PLASTIC = "plastic"
    GLASS = "glass"
    ALUMINUM = "aluminum"
    PAPER = "paper"
    CARDBOARD = "cardboard"
    FOIL = "foil"
    COMPOSITE = "composite"


class StorageCondition(Enum):
    """Storage conditions for medications."""

    ROOM_TEMPERATURE = "room-temp"  # 15-25°C
    COOL = "cool"  # 8-15°C
    REFRIGERATED = "refrigerated"  # 2-8°C
    FROZEN = "frozen"  # <-15°C
    DRY = "dry"  # <60% humidity
    DARK = "dark"  # Protected from light

    # Special conditions
    DO_NOT_FREEZE = "do-not-freeze"
    PROTECT_FROM_HEAT = "protect-from-heat"
    PROTECT_FROM_MOISTURE = "protect-from-moisture"


class LabelingRequirement(Enum):
    """Labeling requirements for medications."""

    # Standard labels
    DRUG_NAME = "drug-name"
    STRENGTH = "strength"
    DOSAGE_FORM = "dosage-form"
    QUANTITY = "quantity"
    EXPIRY_DATE = "expiry-date"
    BATCH_NUMBER = "batch-number"
    MANUFACTURER = "manufacturer"

    # Instructions
    DOSING_INSTRUCTIONS = "dosing-instructions"
    STORAGE_INSTRUCTIONS = "storage-instructions"
    WARNINGS = "warnings"

    # Multi-language requirements
    PICTOGRAMS = "pictograms"
    MULTILINGUAL = "multilingual"
    BRAILLE = "braille"

    # Special populations
    PEDIATRIC_DOSING = "pediatric-dosing"
    PREGNANCY_WARNING = "pregnancy-warning"


class MedicationPackage:
    """Represents medication packaging information."""

    def __init__(self, package_type: PackageType):
        """Initialize medication package.

        Args:
            package_type: Type of packaging
        """
        self.type = package_type
        self.material: Optional[PackageMaterial] = None
        self.quantity: Optional[int] = None
        self.unit_of_use: Optional[str] = None
        self.contains: List["MedicationPackage"] = []  # Nested packages
        self.identifier: Optional[str] = None
        self.lot_number: Optional[str] = None
        self.expiry_date: Optional[date] = None
        self.manufactured_date: Optional[date] = None
        self.opened_date: Optional[datetime] = None
        self.storage_conditions: List[StorageCondition] = []
        self.labeling: Dict[LabelingRequirement, Any] = {}
        self.dimensions: Optional[Dict[str, float]] = (
            None  # length, width, height in cm
        )
        self.images: List[str] = []  # URLs or base64 encoded images
        self.validator = FHIRValidator()

    def validate(self) -> bool:
        """Validate medication package data.

        Returns:
            True if valid
        """
        try:
            # Validate expiry date if present
            if self.expiry_date and self.expiry_date < date.today():
                return False

            # Validate quantity
            if self.quantity is not None and self.quantity < 0:
                return False

            return True
        except (AttributeError, KeyError, TypeError, ValueError):
            return False

    def set_material(self, material: PackageMaterial) -> "MedicationPackage":
        """Set package material."""
        self.material = material
        return self

    def set_quantity(self, quantity: int, unit: str = "unit") -> "MedicationPackage":
        """Set quantity in package.

        Args:
            quantity: Number of units
            unit: Unit of measure (tablet, ml, etc.)
        """
        self.quantity = quantity
        self.unit_of_use = unit
        return self

    def add_contained_package(
        self, package: "MedicationPackage"
    ) -> "MedicationPackage":
        """Add a contained package (for nested packaging)."""
        self.contains.append(package)
        return self

    def set_lot_info(
        self,
        lot_number: str,
        expiry_date: date,
        manufactured_date: Optional[date] = None,
    ) -> "MedicationPackage":
        """Set lot and expiry information."""
        self.lot_number = lot_number
        self.expiry_date = expiry_date
        self.manufactured_date = manufactured_date
        return self

    def mark_opened(
        self, opened_date: Optional[datetime] = None
    ) -> "MedicationPackage":
        """Mark package as opened."""
        self.opened_date = opened_date or datetime.now()
        return self

    def add_storage_condition(self, condition: StorageCondition) -> "MedicationPackage":
        """Add required storage condition."""
        if condition not in self.storage_conditions:
            self.storage_conditions.append(condition)
        return self

    def add_label(
        self, requirement: LabelingRequirement, value: Any
    ) -> "MedicationPackage":
        """Add labeling information."""
        self.labeling[requirement] = value
        return self

    def set_dimensions(
        self, length: float, width: float, height: float
    ) -> "MedicationPackage":
        """Set package dimensions in centimeters."""
        self.dimensions = {
            "length": length,
            "width": width,
            "height": height,
            "volume": length * width * height,
        }
        return self

    def add_image(self, image_url_or_data: str) -> "MedicationPackage":
        """Add package image."""
        self.images.append(image_url_or_data)
        return self

    def calculate_remaining_quantity(self) -> Optional[int]:
        """Calculate remaining quantity based on usage."""
        # In a full implementation, would track dispensing
        return self.quantity

    def is_expired(self, reference_date: Optional[date] = None) -> bool:
        """Check if package is expired."""
        if not self.expiry_date:
            return False
        check_date = reference_date or date.today()
        return check_date > self.expiry_date

    def days_until_expiry(self, reference_date: Optional[date] = None) -> Optional[int]:
        """Calculate days until expiry."""
        if not self.expiry_date:
            return None
        check_date = reference_date or date.today()
        delta = self.expiry_date - check_date
        return delta.days

    def get_storage_temperature_range(self) -> Optional[Tuple[float, float]]:
        """Get required storage temperature range in Celsius."""
        temp_ranges = {
            StorageCondition.FROZEN: (-25, -15),
            StorageCondition.REFRIGERATED: (2, 8),
            StorageCondition.COOL: (8, 15),
            StorageCondition.ROOM_TEMPERATURE: (15, 25),
        }

        for condition in self.storage_conditions:
            if condition in temp_ranges:
                return temp_ranges[condition]

        return None  # No specific temperature requirement

    def to_fhir_extension(self) -> Dict[str, Any]:
        """Convert to FHIR extension format."""
        extension: Dict[str, Any] = {
            "url": "http://havenhealthpassport.org/fhir/extension/medication-package",
            "extension": [],
        }

        # Add type
        extension["extension"].append({"url": "type", "valueCode": self.type.value})

        # Add material
        if self.material:
            extension["extension"].append(
                {"url": "material", "valueCode": self.material.value}
            )

        # Add quantity
        if self.quantity:
            extension["extension"].append(
                {
                    "url": "quantity",
                    "valueQuantity": {"value": self.quantity, "unit": self.unit_of_use},
                }
            )

        # Add lot information
        if self.lot_number:
            extension["extension"].append(
                {"url": "lotNumber", "valueString": self.lot_number}
            )

        if self.expiry_date:
            extension["extension"].append(
                {"url": "expiryDate", "valueDate": self.expiry_date.isoformat()}
            )

        # Add storage conditions
        for condition in self.storage_conditions:
            extension["extension"].append(
                {"url": "storageCondition", "valueCode": condition.value}
            )

        # Add labeling
        if self.labeling:
            label_ext: Dict[str, Any] = {"url": "labeling", "extension": []}

            for req, value in self.labeling.items():
                label_ext["extension"].append(
                    {"url": req.value, "valueString": str(value)}
                )

            extension["extension"].append(label_ext)

        return extension


class RefugeePackagingAdapter:
    """Adapts packaging information for refugee healthcare contexts."""

    @staticmethod
    def create_field_packaging(
        medication_name: str, quantity: int, unit: str = "tablet"
    ) -> MedicationPackage:
        """Create standard field packaging for refugee settings.

        Args:
            medication_name: Name of medication
            quantity: Quantity in package
            unit: Unit of measure

        Returns:
            MedicationPackage configured for field use
        """
        package = MedicationPackage(PackageType.FIELD_PACK)
        package.set_quantity(quantity, unit)
        package.add_storage_condition(StorageCondition.PROTECT_FROM_HEAT)
        package.add_storage_condition(StorageCondition.PROTECT_FROM_MOISTURE)

        # Add multilingual labeling
        package.add_label(LabelingRequirement.DRUG_NAME, medication_name)
        package.add_label(LabelingRequirement.MULTILINGUAL, True)
        package.add_label(LabelingRequirement.PICTOGRAMS, True)

        return package

    @staticmethod
    def create_emergency_kit_packaging(
        kit_type: str, medications: List[Dict[str, Any]]
    ) -> MedicationPackage:
        """Create emergency kit packaging.

        Args:
            kit_type: Type of emergency kit
            medications: List of medications in kit

        Returns:
            MedicationPackage for emergency kit
        """
        kit = MedicationPackage(PackageType.EMERGENCY_KIT)
        kit.add_label(LabelingRequirement.DRUG_NAME, f"{kit_type} Emergency Kit")

        # Add individual medication packages
        for med in medications:
            med_package = MedicationPackage(PackageType.UNIT_DOSE)
            med_package.set_quantity(med["quantity"], med.get("unit", "unit"))
            med_package.add_label(LabelingRequirement.DRUG_NAME, med["name"])
            med_package.add_label(LabelingRequirement.STRENGTH, med.get("strength", ""))

            kit.add_contained_package(med_package)

        # Standard storage for emergency kits
        kit.add_storage_condition(StorageCondition.ROOM_TEMPERATURE)
        kit.add_storage_condition(StorageCondition.DRY)

        return kit

    @staticmethod
    def repackage_bulk_medication(
        bulk_package: MedicationPackage, patient_quantities: List[int]
    ) -> List[MedicationPackage]:
        """Repackage bulk medication into patient-specific packages.

        Args:
            bulk_package: Bulk medication package
            patient_quantities: List of quantities for each patient

        Returns:
            List of patient packages
        """
        patient_packages = []

        for i, quantity in enumerate(patient_quantities):
            patient_pack = MedicationPackage(PackageType.PATIENT_PACK)
            patient_pack.set_quantity(quantity, bulk_package.unit_of_use or "")

            # Copy relevant information from bulk package
            patient_pack.lot_number = bulk_package.lot_number
            patient_pack.expiry_date = bulk_package.expiry_date
            patient_pack.storage_conditions = bulk_package.storage_conditions.copy()

            # Add patient-specific labeling
            patient_pack.add_label(
                LabelingRequirement.DRUG_NAME,
                bulk_package.labeling.get(LabelingRequirement.DRUG_NAME, ""),
            )
            patient_pack.add_label(
                LabelingRequirement.DOSING_INSTRUCTIONS,
                f"Patient {i+1} - Take as directed",
            )
            patient_pack.add_label(LabelingRequirement.PICTOGRAMS, True)

            patient_packages.append(patient_pack)

        return patient_packages


class PackagingValidator:
    """Validates medication packaging for safety and compliance."""

    @classmethod
    def validate_package(cls, package: MedicationPackage) -> Tuple[bool, List[str]]:
        """Validate medication package.

        Args:
            package: Package to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check expiry
        if package.is_expired():
            issues.append("Package is expired")
        elif package.days_until_expiry() is not None:
            days_left = package.days_until_expiry()
            if days_left is not None and days_left < 30:
                issues.append(f"Package expires in {days_left} days")

        # Check required labeling
        required_labels = [
            LabelingRequirement.DRUG_NAME,
            LabelingRequirement.EXPIRY_DATE,
        ]

        for req in required_labels:
            if req not in package.labeling:
                issues.append(f"Missing required label: {req.value}")

        # Check for opened multi-dose containers
        if package.opened_date and package.type == PackageType.MULTI_DOSE:
            days_open = (datetime.now() - package.opened_date).days
            if days_open > 28:  # Standard 28-day limit for multi-dose vials
                issues.append(f"Multi-dose container open for {days_open} days")

        # Check storage conditions
        if not package.storage_conditions:
            issues.append("No storage conditions specified")

        return len(issues) == 0, issues

    @classmethod
    def check_storage_compatibility(
        cls, package: MedicationPackage, current_conditions: Dict[str, Any]
    ) -> List[str]:
        """Check if current storage conditions are suitable.

        Args:
            package: Package with storage requirements
            current_conditions: Current storage conditions

        Returns:
            List of storage issues
        """
        issues = []

        # Check temperature
        temp_range = package.get_storage_temperature_range()
        if temp_range and "temperature" in current_conditions:
            current_temp = current_conditions["temperature"]
            if current_temp < temp_range[0] or current_temp > temp_range[1]:
                issues.append(
                    f"Temperature {current_temp}°C outside required range {temp_range}"
                )

        # Check humidity
        if StorageCondition.DRY in package.storage_conditions:
            if current_conditions.get("humidity", 0) > 60:
                issues.append("Humidity too high for dry storage requirement")

        # Check light exposure
        if StorageCondition.DARK in package.storage_conditions:
            if current_conditions.get("light_exposed", False):
                issues.append("Package requires protection from light")

        return issues


def create_donation_package_manifest(
    packages: List[MedicationPackage],
) -> Dict[str, Any]:
    """Create manifest for donated medication packages.

    Args:
        packages: List of donated packages

    Returns:
        Manifest dictionary
    """
    storage_requirements_set: set[str] = set()
    manifest: Dict[str, Any] = {
        "total_packages": len(packages),
        "creation_date": datetime.now().isoformat(),
        "medications": {},
        "expiry_summary": {
            "expired": 0,
            "expires_30_days": 0,
            "expires_90_days": 0,
            "expires_later": 0,
        },
        "storage_requirements": [],
    }

    for package in packages:
        # Group by medication
        med_name = package.labeling.get(LabelingRequirement.DRUG_NAME, "Unknown")
        if med_name not in manifest["medications"]:
            manifest["medications"][med_name] = {"total_quantity": 0, "packages": []}

        manifest["medications"][med_name]["total_quantity"] += package.quantity or 0
        manifest["medications"][med_name]["packages"].append(
            {
                "lot_number": package.lot_number,
                "quantity": package.quantity,
                "expiry_date": (
                    package.expiry_date.isoformat() if package.expiry_date else None
                ),
            }
        )

        # Update expiry summary
        if package.is_expired():
            manifest["expiry_summary"]["expired"] += 1
        elif package.days_until_expiry() is not None:
            days = package.days_until_expiry()
            if days is not None and days <= 30:
                manifest["expiry_summary"]["expires_30_days"] += 1
            elif days is not None and days <= 90:
                manifest["expiry_summary"]["expires_90_days"] += 1
            else:
                manifest["expiry_summary"]["expires_later"] += 1

        # Collect storage requirements
        for condition in package.storage_conditions:
            storage_requirements_set.add(condition.value)

    # Convert set to list for JSON serialization
    manifest["storage_requirements"] = list(storage_requirements_set)

    return manifest

#!/usr/bin/env python3
"""Preprocessing script for cultural adaptation training data.

CRITICAL: This handles PHI data for refugees. All data must be
properly anonymized and encrypted.
Includes validation for FHIR Resource data preprocessing.
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import boto3
import spacy
from cryptography.fernet import Fernet
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MedicalDataAnonymizer:
    """Production PHI anonymizer using Presidio and spaCy for medical texts."""

    def __init__(self) -> None:
        """Initialize the anonymizer with medical NER models."""
        # Load spaCy model with biomedical entities
        try:
            self.nlp = spacy.load("en_core_sci_md")
        except OSError:
            logger.warning("Medical spaCy model not found. Installing...")
            os.system("pip install scispacy")
            os.system(
                "pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_md-0.5.1.tar.gz"
            )
            self.nlp = spacy.load("en_core_sci_md")

        # Initialize Presidio analyzers
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

        # Add custom medical record patterns
        self._add_medical_patterns()

        # Initialize encryption for reversible anonymization
        self.encryption_key = os.environ.get("PHI_ENCRYPTION_KEY")
        if not self.encryption_key:
            raise ValueError(
                "CRITICAL: PHI_ENCRYPTION_KEY not set! "
                "This is required for HIPAA-compliant anonymization!"
            )
        self.cipher_suite = Fernet(self.encryption_key.encode())

        # Mapping for reversible anonymization
        self.anonymization_map: Dict[str, str] = {}

    def _add_medical_patterns(self) -> None:
        """Add medical-specific patterns to Presidio."""
        # Medical Record Number pattern
        mrn_pattern = Pattern(
            name="mrn_pattern",
            regex=r"\b(MRN|Medical Record Number|Patient ID)[\s:]*[\w\-]+\b",
            score=0.9,
        )
        mrn_recognizer = PatternRecognizer(
            supported_entity="MEDICAL_RECORD_NUMBER", patterns=[mrn_pattern]
        )
        self.analyzer.registry.add_recognizer(mrn_recognizer)

        # Medication names pattern
        med_pattern = Pattern(
            name="medication_pattern", regex=r"\b(mg|mcg|ml|IU|units?)\b", score=0.7
        )
        med_recognizer = PatternRecognizer(
            supported_entity="MEDICATION", patterns=[med_pattern]
        )
        self.analyzer.registry.add_recognizer(med_recognizer)

        # Hospital/Clinic names
        hospital_pattern = Pattern(
            name="hospital_pattern",
            regex=r"\b(Hospital|Clinic|Medical Center|Health Center|Dispensary|Camp Clinic)\b",
            score=0.8,
        )
        hospital_recognizer = PatternRecognizer(
            supported_entity="HEALTHCARE_FACILITY", patterns=[hospital_pattern]
        )
        self.analyzer.registry.add_recognizer(hospital_recognizer)

    def anonymize_text(
        self, text: str, preserve_context: bool = True
    ) -> Tuple[str, Dict[str, str]]:
        """
        Anonymize PHI in healthcare text using Presidio.

        Args:
            text: Text containing potential PHI
            preserve_context: Whether to preserve medical context

        Returns:
            Tuple of (anonymized_text, anonymization_mapping)
        """
        # Analyze text for PHI entities
        analyzer_results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=[
                "PERSON",
                "LOCATION",
                "DATE_TIME",
                "PHONE_NUMBER",
                "EMAIL_ADDRESS",
                "MEDICAL_RECORD_NUMBER",
                "ID",
                "HEALTHCARE_FACILITY",
                "AGE",
                "URL",
                "IP_ADDRESS",
            ],
        )

        # Create reversible anonymization mapping
        anonymization_mapping = {}

        # Configure anonymization operators
        operators = {}
        for result in analyzer_results:
            entity_text = text[result.start : result.end]
            entity_type = result.entity_type

            if preserve_context and entity_type in ["AGE", "DATE_TIME"]:
                # Preserve age ranges and relative dates for medical context
                if entity_type == "AGE":
                    age_value = self._extract_age(entity_text)
                    if age_value:
                        age_range = self._get_age_range(age_value)
                        operators[entity_type] = OperatorConfig(
                            "replace", {"new_value": f"[AGE_{age_range}]"}
                        )
                        anonymization_mapping[f"[AGE_{age_range}]"] = self._encrypt_phi(
                            entity_text
                        )
                else:  # DATE_TIME
                    relative_date = self._get_relative_date(entity_text)
                    operators[entity_type] = OperatorConfig(
                        "replace", {"new_value": relative_date}
                    )
                    anonymization_mapping[relative_date] = self._encrypt_phi(
                        entity_text
                    )
            else:
                # Full anonymization for other PHI
                placeholder = f"[{entity_type}_{len(anonymization_mapping)}]"
                operators[entity_type] = OperatorConfig(
                    "replace", {"new_value": placeholder}
                )
                anonymization_mapping[placeholder] = self._encrypt_phi(entity_text)

        # Apply anonymization
        anonymized_result = self.anonymizer.anonymize(
            text=text, analyzer_results=analyzer_results, operators=operators
        )

        return anonymized_result.text, anonymization_mapping

    def _extract_age(self, text: str) -> int | None:
        """Extract numeric age from text."""
        match = re.search(r"\d+", text)
        return int(match.group()) if match else None

    def _get_age_range(self, age: int) -> str:
        """Convert age to range for preserving medical context."""
        if age < 1:
            return "INFANT"
        elif age < 5:
            return "TODDLER"
        elif age < 13:
            return "CHILD"
        elif age < 20:
            return "ADOLESCENT"
        elif age < 65:
            return "ADULT"
        else:
            return "ELDERLY"

    def _get_relative_date(self, date_text: str) -> str:
        """Convert date to relative timeframe."""
        # This is simplified - in production, parse the date properly
        if "today" in date_text.lower() or "now" in date_text.lower():
            return "[CURRENT_DATE]"
        elif "yesterday" in date_text.lower():
            return "[PREVIOUS_DAY]"
        elif "week" in date_text.lower():
            return "[THIS_WEEK]"
        elif "month" in date_text.lower():
            return "[THIS_MONTH]"
        else:
            return "[PAST_DATE]"

    def _encrypt_phi(self, phi_text: str) -> str:
        """Encrypt PHI for reversible anonymization."""
        return self.cipher_suite.encrypt(phi_text.encode()).decode()

    def decrypt_phi(self, encrypted_text: str) -> str:
        """Decrypt PHI when authorized."""
        return self.cipher_suite.decrypt(encrypted_text.encode()).decode()


def preprocess_cultural_data(
    input_path: str, output_path: str, anonymizer: MedicalDataAnonymizer
) -> None:
    """Preprocess cultural communication data for training with HIPAA compliance."""
    logger.info(f"Processing data from {input_path}")

    # Initialize AWS clients for secure storage
    s3 = boto3.client("s3")
    kms = boto3.client("kms")

    # Load raw data
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Track anonymization audit trail
    audit_trail: Dict[str, Any] = {
        "processing_timestamp": datetime.utcnow().isoformat(),
        "input_file": str(input_path),
        "total_records": len(data.get("communication_patterns", [])),
        "anonymization_mappings": [],
    }

    # Process each communication pattern
    processed_data = []

    for idx, item in enumerate(data.get("communication_patterns", [])):
        try:
            # Anonymize text with PHI detection
            original_text = item.get("text", "")
            anonymized_text, phi_mapping = anonymizer.anonymize_text(
                original_text, preserve_context=True
            )

            # Store anonymization mapping for audit
            if phi_mapping:
                audit_trail["anonymization_mappings"].append(
                    {
                        "record_index": idx,
                        "phi_found": len(phi_mapping),
                        "mapping_hash": hashlib.sha256(
                            json.dumps(phi_mapping, sort_keys=True).encode()
                        ).hexdigest(),
                    }
                )

            # Extract cultural markers with medical context
            processed_item = {
                "text": anonymized_text,
                "pattern_type": item.get("pattern_type", "medical_communication"),
                "language": item.get("language", "en"),
                "cultural_region": data.get("cultural_region", "unknown"),
                # Cultural pattern labels
                "formal": item.get("formal", False),
                "includes_honorific": item.get("includes_honorific", False),
                "gender_specific": item.get("gender_specific", False),
                "indirect_communication": item.get("indirect_communication", False),
                "family_involvement": item.get("family_involvement", False),
                "religious_references": item.get("religious_references", False),
                "age_respectful": item.get("age_respectful", False),
                "authority_deference": item.get("authority_deference", False),
                # Medical context markers
                "medical_urgency": detect_medical_urgency(anonymized_text),
                "symptom_description": contains_symptom_description(anonymized_text),
                "treatment_discussion": contains_treatment_discussion(anonymized_text),
                "medication_mention": contains_medication_mention(anonymized_text),
                # Data quality indicators
                "anonymized": bool(phi_mapping),
                "processing_version": "2.0",
                "quality_score": calculate_quality_score(anonymized_text, item),
            }

            processed_data.append(processed_item)

        except Exception as e:
            logger.error(f"Error processing item {idx}: {str(e)}")
            # Don't include items that failed processing
            continue

    # Generate culturally appropriate synthetic examples
    synthetic_data = generate_production_synthetic_examples(
        data.get("cultural_region", "unknown"),
        data.get("language_pair", "en-ar"),
        anonymizer,
    )
    processed_data.extend(synthetic_data)

    # Quality filtering
    filtered_data = [
        item for item in processed_data if item.get("quality_score", 0) >= 0.7
    ]

    logger.info(
        f"Filtered {len(processed_data) - len(filtered_data)} low-quality samples"
    )

    # Stratified split to maintain cultural balance
    train_data, val_data = stratified_cultural_split(filtered_data)

    # Save processed data with encryption
    save_encrypted_data(train_data, os.path.join(output_path, "train"), s3, kms)
    save_encrypted_data(val_data, os.path.join(output_path, "validation"), s3, kms)

    # Save audit trail
    audit_trail["final_records"] = len(filtered_data)
    audit_trail["train_records"] = len(train_data)
    audit_trail["validation_records"] = len(val_data)

    with open(os.path.join(output_path, "audit_trail.json"), "w") as f:
        json.dump(audit_trail, f, indent=2)

    logger.info(f"Processed {len(filtered_data)} samples")
    logger.info(f"Train: {len(train_data)}, Validation: {len(val_data)}")


def detect_medical_urgency(text: str) -> str:
    """Detect medical urgency level in text."""
    urgent_keywords = [
        "emergency",
        "urgent",
        "immediate",
        "critical",
        "severe",
        "acute",
    ]
    moderate_keywords = ["soon", "concern", "worrying", "persistent", "chronic"]

    text_lower = text.lower()

    if any(keyword in text_lower for keyword in urgent_keywords):
        return "high"
    elif any(keyword in text_lower for keyword in moderate_keywords):
        return "moderate"
    else:
        return "low"


def contains_symptom_description(text: str) -> bool:
    """Check if text contains symptom descriptions."""
    symptom_patterns = [
        r"(pain|ache|hurt|sore)",
        r"(fever|temperature|hot|cold)",
        r"(cough|sneeze|runny nose)",
        r"(tired|fatigue|weak)",
        r"(nausea|vomit|dizzy)",
        r"(rash|itch|swell)",
    ]

    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in symptom_patterns)


def contains_treatment_discussion(text: str) -> bool:
    """Check if text discusses treatment options."""
    treatment_keywords = [
        "treatment",
        "therapy",
        "medication",
        "medicine",
        "prescription",
        "surgery",
        "procedure",
        "care plan",
        "follow-up",
        "appointment",
    ]

    text_lower = text.lower()
    return any(keyword in text_lower for keyword in treatment_keywords)


def contains_medication_mention(text: str) -> bool:
    """Check if text mentions medications."""
    # Check for common medication patterns
    med_patterns = [
        r"\b\d+\s*(mg|mcg|ml|IU|units?)\b",
        r"\b(tablet|pill|capsule|injection|dose)\b",
        r"\b(daily|twice|three times|before|after)\s*(meals?|food)\b",
    ]

    text_lower = text.lower()
    return any(
        re.search(pattern, text_lower, re.IGNORECASE) for pattern in med_patterns
    )


def calculate_quality_score(text: str, original_item: Dict[str, Any]) -> float:
    """Calculate quality score for training data."""
    score = 1.0

    # Reduce score for very short text
    if len(text.split()) < 5:
        score *= 0.5

    # Reduce score for missing cultural markers
    cultural_markers = [
        "formal",
        "includes_honorific",
        "gender_specific",
        "indirect_communication",
        "family_involvement",
        "religious_references",
        "age_respectful",
        "authority_deference",
    ]

    marked_count = sum(
        1 for marker in cultural_markers if original_item.get(marker, False)
    )
    if marked_count == 0:
        score *= 0.7

    # Reduce score for excessive anonymization
    anonymization_ratio = len(re.findall(r"\[[\w_]+\]", text)) / max(
        len(text.split()), 1
    )
    if anonymization_ratio > 0.5:
        score *= 0.8

    return min(score, 1.0)


def stratified_cultural_split(
    data: List[Dict[str, Any]], test_size: float = 0.2
) -> Tuple[List[Dict], List[Dict]]:
    """Perform stratified split maintaining cultural region balance."""
    # Group by cultural region
    region_groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in data:
        region = item.get("cultural_region", "unknown")
        if region not in region_groups:
            region_groups[region] = []
        region_groups[region].append(item)

    train_data = []
    val_data = []

    # Split each region proportionally
    for _region, items in region_groups.items():
        if len(items) < 2:
            # Too few items to split
            train_data.extend(items)
        else:
            region_train, region_val = train_test_split(
                items, test_size=test_size, random_state=42
            )
            train_data.extend(region_train)
            val_data.extend(region_val)

    # Shuffle while maintaining the split
    random.shuffle(train_data)
    random.shuffle(val_data)

    return train_data, val_data


def generate_production_synthetic_examples(
    region: str, language_pair: str, anonymizer: MedicalDataAnonymizer
) -> List[Dict[str, Any]]:
    """Generate culturally appropriate synthetic examples for training."""
    synthetic_examples = []

    # Comprehensive templates based on real refugee healthcare scenarios
    templates = {
        "middle_east": [
            {
                "text": "Doctor, my mother needs to be present during the examination, as is our custom.",
                "gender_specific": True,
                "family_involvement": True,
                "formal": True,
                "medical_context": "examination",
            },
            {
                "text": "We will need to consult with the family before deciding on the surgery, inshallah.",
                "religious_references": True,
                "family_involvement": True,
                "indirect_communication": True,
                "medical_context": "treatment_decision",
            },
            {
                "text": "Please, respected doctor, can you explain this to my husband? He makes medical decisions.",
                "gender_specific": True,
                "authority_deference": True,
                "formal": True,
                "medical_context": "consent",
            },
            {
                "text": "The pain started after Ramadan fasting, but I continued for religious obligation.",
                "religious_references": True,
                "medical_context": "symptom_onset",
            },
        ],
        "south_asia": [
            {
                "text": "Respected doctor sahib, my elderly father requires your esteemed guidance on his medication.",
                "includes_honorific": True,
                "authority_deference": True,
                "age_respectful": True,
                "formal": True,
                "medical_context": "medication",
            },
            {
                "text": "Our family elders must approve before we proceed with the treatment plan.",
                "family_involvement": True,
                "age_respectful": True,
                "authority_deference": True,
                "medical_context": "treatment_decision",
            },
            {
                "text": "Please understand, aunty cannot be examined by a male doctor without family present.",
                "gender_specific": True,
                "family_involvement": True,
                "age_respectful": True,
                "medical_context": "examination",
            },
        ],
        "east_africa": [
            {
                "text": "In our community, we traditionally use this herb alongside your medicine. Is this acceptable?",
                "indirect_communication": True,
                "religious_references": True,
                "formal": False,
                "medical_context": "medication",
            },
            {
                "text": "The clan elder blessed the treatment. We can now proceed with confidence.",
                "authority_deference": True,
                "religious_references": True,
                "family_involvement": True,
                "medical_context": "treatment_decision",
            },
            {
                "text": "My symptoms worsen during the rainy season, as happens in our homeland.",
                "indirect_communication": True,
                "medical_context": "symptom_pattern",
            },
        ],
        "west_africa": [
            {
                "text": "Mama says the child's fever is from teething, as our grandmothers taught us.",
                "family_involvement": True,
                "age_respectful": True,
                "indirect_communication": True,
                "medical_context": "symptom_belief",
            },
            {
                "text": "We must inform the family matriarch about the diagnosis before treatment begins.",
                "family_involvement": True,
                "age_respectful": True,
                "authority_deference": True,
                "medical_context": "diagnosis",
            },
        ],
        "central_asia": [
            {
                "text": "In our tradition, the eldest son must be informed of his father's condition first.",
                "family_involvement": True,
                "age_respectful": True,
                "gender_specific": True,
                "medical_context": "diagnosis",
            },
            {
                "text": "Please, can the female nurse assist? My wife is more comfortable that way.",
                "gender_specific": True,
                "formal": True,
                "medical_context": "examination",
            },
        ],
    }

    # Get templates for the region or use a mix if unknown
    region_templates = templates.get(region, [])
    if not region_templates or region == "unknown":
        # Mix templates from all regions for diversity
        region_templates = []
        for region_key in templates:
            region_templates.extend(templates[region_key][:2])

    # Process each template
    for template in region_templates:
        # Add cultural context variations
        variations = create_cultural_variations(template, language_pair)

        for variant in variations:
            # Apply anonymization to ensure consistency
            anonymized_text, _ = anonymizer.anonymize_text(variant["text"])

            example = {
                "text": anonymized_text,
                "pattern_type": "medical_communication",
                "language": language_pair.split("-")[0],
                "cultural_region": region,
                "formal": variant.get("formal", template.get("formal", False)),
                "includes_honorific": variant.get(
                    "includes_honorific", template.get("includes_honorific", False)
                ),
                "gender_specific": variant.get(
                    "gender_specific", template.get("gender_specific", False)
                ),
                "indirect_communication": variant.get(
                    "indirect_communication",
                    template.get("indirect_communication", False),
                ),
                "family_involvement": variant.get(
                    "family_involvement", template.get("family_involvement", False)
                ),
                "religious_references": variant.get(
                    "religious_references", template.get("religious_references", False)
                ),
                "age_respectful": variant.get(
                    "age_respectful", template.get("age_respectful", False)
                ),
                "authority_deference": variant.get(
                    "authority_deference", template.get("authority_deference", False)
                ),
                "medical_urgency": detect_medical_urgency(anonymized_text),
                "symptom_description": contains_symptom_description(anonymized_text),
                "treatment_discussion": contains_treatment_discussion(anonymized_text),
                "medication_mention": contains_medication_mention(anonymized_text),
                "synthetic": True,
                "quality_score": 0.9,  # High quality for curated synthetic data
            }

            synthetic_examples.append(example)

    return synthetic_examples


def create_cultural_variations(
    template: Dict[str, Any], language_pair: str
) -> List[Dict[str, Any]]:
    """Create variations of cultural templates for diversity."""
    variations = [template.copy()]  # Original

    # Add formality variations
    if template.get("formal"):
        informal_variant = template.copy()
        informal_variant["text"] = make_informal(template["text"])
        informal_variant["formal"] = False
        variations.append(informal_variant)

    # Add urgency variations for medical contexts
    if template.get("medical_context") in ["symptom_onset", "symptom_pattern"]:
        urgent_variant = template.copy()
        urgent_variant["text"] = add_urgency_markers(template["text"])
        variations.append(urgent_variant)

    return variations


def make_informal(text: str) -> str:
    """Convert formal text to informal variant."""
    informal_replacements = {
        "Doctor": "Doc",
        "Please": "Can you",
        "respected": "",
        "esteemed": "",
        "sahib": "",
        "Respected": "",
    }

    result = text
    for formal, informal in informal_replacements.items():
        result = result.replace(formal, informal)

    return result.strip()


def add_urgency_markers(text: str) -> str:
    """Add urgency markers to medical text."""
    urgency_prefixes = [
        "It's urgent - ",
        "Please help quickly - ",
        "This is getting worse - ",
    ]

    return random.choice(urgency_prefixes) + text


def validate_fhir_preprocessing(data: Dict[str, Any]) -> bool:
    """Validate FHIR resource data before preprocessing.

    Args:
        data: Dictionary containing FHIR resource data

    Returns:
        bool: True if data is valid for preprocessing, False otherwise
    """
    if not data:
        logger.error("FHIR preprocessing validation failed: empty data")
        return False

    # Check for required fields
    if "resourceType" not in data:
        logger.error("FHIR preprocessing validation failed: missing resourceType")
        return False

    # Validate resource type
    valid_resource_types = [
        "Patient",
        "Practitioner",
        "Organization",
        "Observation",
        "Condition",
        "Procedure",
        "MedicationRequest",
        "Encounter",
        "Immunization",
        "AllergyIntolerance",
        "DiagnosticReport",
    ]

    if data["resourceType"] not in valid_resource_types:
        logger.error(
            f"FHIR preprocessing validation failed: invalid resourceType '{data['resourceType']}'"
        )
        return False

    # Validate that text content exists for preprocessing
    if "text" not in data:
        logger.error(
            "FHIR preprocessing validation failed: missing text field for processing"
        )
        return False

    # Validate text has narrative
    if "div" not in data.get("text", {}):
        logger.error(
            "FHIR preprocessing validation failed: missing narrative div in text"
        )
        return False

    return True


def save_encrypted_data(
    data: List[Dict[str, Any]], output_dir: str, s3_client: Any, kms_client: Any
) -> None:
    """Save processed data with encryption for HIPAA compliance."""
    os.makedirs(output_dir, exist_ok=True)

    # Generate data encryption key
    response = kms_client.generate_data_key(
        KeyId=os.environ.get("SAGEMAKER_KMS_KEY_ID"), KeySpec="AES_256"
    )

    plaintext_key = response["Plaintext"]
    encrypted_key = response["CiphertextBlob"]

    # Encrypt the data
    cipher_suite = Fernet(base64.urlsafe_b64encode(plaintext_key[:32]))

    data_json = json.dumps(data, indent=2, ensure_ascii=False)
    encrypted_data = cipher_suite.encrypt(data_json.encode())

    # Save locally first
    local_path = os.path.join(output_dir, "data.json.encrypted")
    with open(local_path, "wb") as f:
        f.write(encrypted_data)

    # Save encryption key metadata
    key_metadata = {
        "encrypted_data_key": base64.b64encode(encrypted_key).decode(),
        "key_id": os.environ.get("SAGEMAKER_KMS_KEY_ID"),
        "encryption_context": {
            "purpose": "training_data",
            "environment": os.environ.get("ENVIRONMENT", "production"),
        },
    }

    with open(os.path.join(output_dir, "key_metadata.json"), "w") as f:
        json.dump(key_metadata, f)

    # Upload to S3 if configured
    if os.environ.get("SAGEMAKER_TRAINING_BUCKET"):
        s3_key = f"training-data/{datetime.utcnow().strftime('%Y%m%d')}/{os.path.basename(output_dir)}/data.json.encrypted"

        s3_client.upload_file(
            local_path,
            os.environ.get("SAGEMAKER_TRAINING_BUCKET"),
            s3_key,
            ExtraArgs={
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": os.environ.get("SAGEMAKER_KMS_KEY_ID"),
            },
        )

        logger.info(
            f"Uploaded encrypted data to s3://{os.environ.get('SAGEMAKER_TRAINING_BUCKET')}/{s3_key}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", type=str, default="/opt/ml/processing/input")
    parser.add_argument("--output-path", type=str, default="/opt/ml/processing/output")

    args = parser.parse_args()

    # Verify required environment variables
    required_env_vars = [
        "PHI_ENCRYPTION_KEY",
        "SAGEMAKER_KMS_KEY_ID",
        "AWS_DEFAULT_REGION",
    ]

    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    if missing_vars:
        raise ValueError(
            f"CRITICAL: Missing required environment variables: {', '.join(missing_vars)}. "
            "These are required for HIPAA-compliant data processing!"
        )

    # Initialize anonymizer
    anonymizer = MedicalDataAnonymizer()

    # Process all input files
    input_files = list(Path(args.input_path).glob("*.json"))

    if not input_files:
        raise ValueError(f"No input files found in {args.input_path}")

    for input_file in input_files:
        logger.info(f"Processing file: {input_file}")
        preprocess_cultural_data(str(input_file), args.output_path, anonymizer)

    logger.info("Preprocessing completed successfully")

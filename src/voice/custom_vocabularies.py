"""
Custom Medical Vocabularies Setup.

This module provides functionality for creating and managing custom medical
vocabularies that can be tailored to specific healthcare practices, specialties,
or regional terminology needs.
"""

import asyncio
import csv
import io
import json
import logging
import re
import types
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Union

import boto3
from botocore.exceptions import ClientError

from .medical_vocabularies import MedicalTerm
from .transcribe_medical import LanguageCode, MedicalSpecialty

logger = logging.getLogger(__name__)

_defusedxml_available = False
minidom: types.ModuleType
ET: types.ModuleType

try:
    import defusedxml.ElementTree
    import defusedxml.minidom

    ET = defusedxml.ElementTree
    minidom = defusedxml.minidom
    _defusedxml_available = True
except ImportError:
    # Fall back to standard library but log warning
    import xml.dom.minidom
    import xml.etree.ElementTree

    minidom = xml.dom.minidom
    ET = xml.etree.ElementTree
    logger.warning("defusedxml not available - using standard XML libraries")


class VocabularySource(Enum):
    """Source of custom vocabulary."""

    USER_UPLOAD = "user_upload"
    CLINICAL_DATABASE = "clinical_database"
    PRACTICE_SPECIFIC = "practice_specific"
    REGIONAL_DIALECT = "regional_dialect"
    DRUG_DATABASE = "drug_database"


class ValidationStatus(Enum):
    """Validation status for custom terms."""

    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class ValidationResults(TypedDict):
    """Type definition for validation results."""

    total_terms: int
    validated: int
    needs_review: int
    rejected: int
    pending: int
    errors: List[Dict[str, Any]]


class VocabularyStatistics(TypedDict):
    """Type definition for vocabulary statistics."""

    total_vocabularies: int
    total_terms: int
    by_status: Dict[str, int]
    by_source: Dict[str, int]
    by_language: Dict[str, int]
    by_specialty: Dict[str, int]


@dataclass
class CustomVocabularyTerm(MedicalTerm):
    """Extended medical term for custom vocabularies."""

    category: Optional[str] = None
    source: VocabularySource = VocabularySource.USER_UPLOAD
    added_by: Optional[str] = None
    added_date: Optional[datetime] = None
    validation_status: ValidationStatus = ValidationStatus.PENDING
    usage_count: int = 0
    confidence_threshold: float = 0.7
    context_hints: List[str] = field(default_factory=list)

    def to_transcribe_format(self) -> Dict[str, Any]:
        """Convert to Amazon Transcribe Medical format."""
        return {
            "Phrase": self.term,
            "SoundsLike": self.sounds_like,
            "DisplayAs": self.display_as or self.term,
        }

    def validate(self) -> List[str]:
        """Validate the custom term."""
        errors = []

        # Basic validation
        if not self.term or len(self.term) < 2:
            errors.append("Term must be at least 2 characters long")

        if not self.sounds_like:
            errors.append("At least one pronunciation must be provided")

        # Medical term validation
        if len(self.term) > 100:
            errors.append("Term cannot exceed 100 characters")

        # Pronunciation validation
        if self.sounds_like:
            for pronunciation in self.sounds_like:
                if not re.match(r"^[a-zA-Z\s\-]+$", pronunciation):
                    errors.append(f"Invalid pronunciation format: {pronunciation}")

        return errors


@dataclass
class CustomVocabulary:
    """Custom vocabulary collection."""

    name: str
    description: Optional[str] = None
    specialty: MedicalSpecialty = MedicalSpecialty.PRIMARYCARE
    language: LanguageCode = LanguageCode.EN_US
    terms: List[CustomVocabularyTerm] = field(default_factory=list)
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    created_by: Optional[str] = None
    is_active: bool = True
    tags: List[str] = field(default_factory=list)

    def add_term(self, term: CustomVocabularyTerm) -> None:
        """Add a term to the vocabulary."""
        self.terms.append(term)
        self.modified_date = datetime.utcnow()

    def remove_term(self, term_name: str) -> bool:
        """Remove a term from the vocabulary."""
        original_count = len(self.terms)
        self.terms = [t for t in self.terms if t.term != term_name]
        if len(self.terms) < original_count:
            self.modified_date = datetime.utcnow()
            return True
        return False

    def get_validated_terms(self) -> List[CustomVocabularyTerm]:
        """Get only validated terms."""
        return [
            t for t in self.terms if t.validation_status == ValidationStatus.VALIDATED
        ]

    def to_transcribe_payload(self) -> Dict[str, Any]:
        """Convert to Amazon Transcribe Medical vocabulary payload."""
        validated_terms = self.get_validated_terms()
        return {
            "VocabularyName": self.name,
            "LanguageCode": self.language.value,
            "Phrases": [term.to_transcribe_format() for term in validated_terms],
        }


class CustomVocabularyManager:
    """Manager for custom medical vocabularies."""

    def __init__(self, region_name: str = "us-east-1"):
        """Initialize the custom vocabulary manager."""
        self.transcribe_client = boto3.client("transcribe", region_name=region_name)
        self.region = region_name
        self.vocabularies: Dict[str, CustomVocabulary] = {}
        self.vocabulary_dir = Path("custom_vocabularies")
        self.vocabulary_dir.mkdir(exist_ok=True)

        # Load existing vocabularies
        self._load_vocabularies()

    def _load_vocabularies(self) -> None:
        """Load vocabularies from local storage."""
        for vocab_file in self.vocabulary_dir.glob("*.json"):
            try:
                with open(vocab_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    vocab = self._vocab_from_dict(data)
                    self.vocabularies[vocab.name] = vocab
            except (json.JSONDecodeError, KeyError, IOError) as e:
                logger.error("Failed to load vocabulary from %s: %s", vocab_file, e)

    def _vocab_from_dict(self, data: Dict[str, Any]) -> CustomVocabulary:
        """Create CustomVocabulary from dictionary."""
        vocab = CustomVocabulary(
            name=data["name"],
            description=data.get("description"),
            specialty=MedicalSpecialty(data.get("specialty", "PRIMARYCARE")),
            language=LanguageCode(data.get("language", "en-US")),
            created_date=(
                datetime.fromisoformat(data["created_date"])
                if data.get("created_date")
                else None
            ),
            modified_date=(
                datetime.fromisoformat(data["modified_date"])
                if data.get("modified_date")
                else None
            ),
            created_by=data.get("created_by"),
            is_active=data.get("is_active", True),
            tags=data.get("tags", []),
        )

        # Load terms
        for term_data in data.get("terms", []):
            term = CustomVocabularyTerm(
                term=term_data["term"],
                sounds_like=term_data["sounds_like"],
                display_as=term_data.get("display_as"),
                category=term_data.get("category"),
                source=VocabularySource(term_data.get("source", "user_upload")),
                added_by=term_data.get("added_by"),
                added_date=(
                    datetime.fromisoformat(term_data["added_date"])
                    if term_data.get("added_date")
                    else None
                ),
                validation_status=ValidationStatus(
                    term_data.get("validation_status", "pending")
                ),
                usage_count=term_data.get("usage_count", 0),
                confidence_threshold=term_data.get("confidence_threshold", 0.7),
                context_hints=term_data.get("context_hints", []),
            )
            vocab.terms.append(term)

        return vocab

    def _vocab_to_dict(self, vocab: CustomVocabulary) -> Dict[str, Any]:
        """Convert CustomVocabulary to dictionary."""
        return {
            "name": vocab.name,
            "description": vocab.description,
            "specialty": vocab.specialty.value,
            "language": vocab.language.value,
            "created_date": (
                vocab.created_date.isoformat() if vocab.created_date else None
            ),
            "modified_date": (
                vocab.modified_date.isoformat() if vocab.modified_date else None
            ),
            "created_by": vocab.created_by,
            "is_active": vocab.is_active,
            "tags": vocab.tags,
            "terms": [
                {
                    "term": term.term,
                    "sounds_like": term.sounds_like,
                    "display_as": term.display_as,
                    "category": term.category,
                    "source": term.source.value,
                    "added_by": term.added_by,
                    "added_date": (
                        term.added_date.isoformat() if term.added_date else None
                    ),
                    "validation_status": term.validation_status.value,
                    "usage_count": term.usage_count,
                    "confidence_threshold": term.confidence_threshold,
                    "context_hints": term.context_hints,
                }
                for term in vocab.terms
            ],
        }

    def save_vocabulary(self, vocab: CustomVocabulary) -> None:
        """Save vocabulary to local storage."""
        vocab_file = self.vocabulary_dir / f"{vocab.name}.json"
        with open(vocab_file, "w", encoding="utf-8") as f:
            json.dump(self._vocab_to_dict(vocab), f, indent=2)
        logger.info("Saved vocabulary '%s' to %s", vocab.name, vocab_file)

    def create_vocabulary(
        self,
        name: str,
        description: str,
        specialty: MedicalSpecialty = MedicalSpecialty.PRIMARYCARE,
        language: LanguageCode = LanguageCode.EN_US,
        created_by: Optional[str] = None,
    ) -> CustomVocabulary:
        """Create a new custom vocabulary."""
        if name in self.vocabularies:
            raise ValueError(f"Vocabulary '{name}' already exists")

        vocab = CustomVocabulary(
            name=name,
            description=description,
            specialty=specialty,
            language=language,
            created_date=datetime.utcnow(),
            modified_date=datetime.utcnow(),
            created_by=created_by,
        )

        self.vocabularies[name] = vocab
        self.save_vocabulary(vocab)
        return vocab

    def add_terms_from_csv(
        self, vocab_name: str, csv_path: Path, added_by: Optional[str] = None
    ) -> List[CustomVocabularyTerm]:
        """Load terms from CSV file."""
        if vocab_name not in self.vocabularies:
            raise ValueError(f"Vocabulary '{vocab_name}' not found")

        vocab = self.vocabularies[vocab_name]
        new_terms = []

        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Expected CSV columns: term, sounds_like, display_as, category
                sounds_like = row.get("sounds_like", "").split("|")
                sounds_like = [s.strip() for s in sounds_like if s.strip()]

                if not sounds_like:
                    # Generate basic pronunciation if not provided
                    sounds_like = [row["term"].lower().replace("_", " ")]

                term = CustomVocabularyTerm(
                    term=row["term"],
                    sounds_like=sounds_like,
                    display_as=row.get("display_as") or row["term"],
                    category=row.get("category"),
                    source=VocabularySource.USER_UPLOAD,
                    added_by=added_by,
                    added_date=datetime.utcnow(),
                )

                # Validate term
                errors = term.validate()
                if errors:
                    logger.warning(
                        "Validation errors for term '%s': %s", term.term, errors
                    )
                    term.validation_status = ValidationStatus.NEEDS_REVIEW
                else:
                    term.validation_status = ValidationStatus.VALIDATED

                vocab.add_term(term)
                new_terms.append(term)

        self.save_vocabulary(vocab)
        logger.info("Added %d terms to vocabulary '%s'", len(new_terms), vocab_name)
        return new_terms

    def validate_vocabulary(self, vocab_name: str) -> ValidationResults:
        """Validate all terms in a vocabulary."""
        if vocab_name not in self.vocabularies:
            raise ValueError(f"Vocabulary '{vocab_name}' not found")

        vocab = self.vocabularies[vocab_name]
        validation_results: ValidationResults = {
            "total_terms": len(vocab.terms),
            "validated": 0,
            "needs_review": 0,
            "rejected": 0,
            "pending": 0,
            "errors": [],
        }

        for term in vocab.terms:
            errors = term.validate()
            if errors:
                validation_results["errors"].append(
                    {"term": term.term, "errors": errors}
                )
                if term.validation_status == ValidationStatus.PENDING:
                    term.validation_status = ValidationStatus.NEEDS_REVIEW
            else:
                if term.validation_status == ValidationStatus.PENDING:
                    term.validation_status = ValidationStatus.VALIDATED

            # Count by status
            if term.validation_status == ValidationStatus.VALIDATED:
                validation_results["validated"] += 1
            elif term.validation_status == ValidationStatus.NEEDS_REVIEW:
                validation_results["needs_review"] += 1
            elif term.validation_status == ValidationStatus.REJECTED:
                validation_results["rejected"] += 1
            else:
                validation_results["pending"] += 1

        self.save_vocabulary(vocab)
        return validation_results

    async def upload_to_transcribe(self, vocab_name: str) -> Dict[str, Any]:
        """Upload custom vocabulary to Amazon Transcribe Medical."""
        if vocab_name not in self.vocabularies:
            raise ValueError(f"Vocabulary '{vocab_name}' not found")

        vocab = self.vocabularies[vocab_name]
        validated_terms = vocab.get_validated_terms()

        if not validated_terms:
            raise ValueError(f"No validated terms in vocabulary '{vocab_name}'")

        try:  # Create vocabulary file content
            vocab_content = []
            for term in validated_terms:
                vocab_line = f"{term.term}"
                if term.sounds_like:
                    vocab_line += "\t" + "\t".join(term.sounds_like)
                if term.display_as and term.display_as != term.term:
                    vocab_line += f"\t{term.display_as}"
                vocab_content.append(vocab_line)

            # Upload to S3 first (required by Transcribe)
            s3_client = boto3.client("s3", region_name=self.region)
            bucket_name = f"haven-health-vocabularies-{self.region}"
            key = f"custom-vocabularies/{vocab_name}.txt"

            # Ensure bucket exists
            try:
                s3_client.head_bucket(Bucket=bucket_name)
            except ClientError:
                s3_client.create_bucket(Bucket=bucket_name)

            # Upload vocabulary file
            s3_client.put_object(
                Bucket=bucket_name,
                Key=key,
                Body="\n".join(vocab_content).encode("utf-8"),
            )

            # Create or update vocabulary in Transcribe
            vocabulary_uri = f"s3://{bucket_name}/{key}"

            response = self.transcribe_client.create_medical_vocabulary(
                VocabularyName=vocab_name,
                LanguageCode=vocab.language.value,
                VocabularyFileUri=vocabulary_uri,
            )

            logger.info(
                "Uploaded vocabulary '%s' to Amazon Transcribe Medical", vocab_name
            )
            return {
                "vocabulary_name": vocab_name,
                "status": response["VocabularyState"],
                "terms_count": len(validated_terms),
                "upload_uri": vocabulary_uri,
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConflictException":
                # Vocabulary already exists, update it
                return await self.update_transcribe_vocabulary(vocab_name)
            else:
                logger.error("Failed to upload vocabulary: %s", e)
                raise

    async def update_transcribe_vocabulary(self, vocab_name: str) -> Dict[str, Any]:
        """Update existing vocabulary in Amazon Transcribe Medical."""
        if vocab_name not in self.vocabularies:
            raise ValueError(f"Vocabulary '{vocab_name}' not found")

        # Delete and recreate (Transcribe doesn't support direct updates)
        try:
            self.transcribe_client.delete_medical_vocabulary(VocabularyName=vocab_name)
            # Wait for deletion
            await asyncio.sleep(2)
        except ClientError as e:
            if e.response["Error"]["Code"] != "NotFoundException":
                raise

        # Upload new version
        return await self.upload_to_transcribe(vocab_name)

    def get_vocabulary_status(self, vocab_name: str) -> Dict[str, Any]:
        """Get status of vocabulary in Amazon Transcribe Medical."""
        try:
            response = self.transcribe_client.get_medical_vocabulary(
                VocabularyName=vocab_name
            )
            return {
                "name": response["VocabularyName"],
                "state": response["VocabularyState"],
                "language": response["LanguageCode"],
                "last_modified": response.get("LastModifiedTime"),
                "download_uri": response.get("DownloadUri"),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                return {"name": vocab_name, "state": "NOT_FOUND"}
            raise

    def search_terms(
        self,
        query: str,
        vocab_name: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[CustomVocabularyTerm]:
        """Search for terms across vocabularies."""
        results = []
        query_lower = query.lower()

        vocabularies = (
            [self.vocabularies[vocab_name]]
            if vocab_name
            else self.vocabularies.values()
        )

        for vocab in vocabularies:
            for term in vocab.terms:  # Check if term matches query
                if (
                    query_lower in term.term.lower()
                    or (
                        term.sounds_like
                        and any(
                            query_lower in sound.lower() for sound in term.sounds_like
                        )
                    )
                    or (term.display_as and query_lower in term.display_as.lower())
                ):

                    # Check category filter
                    if category and term.category != category:
                        continue

                    results.append(term)

        return results

    def export_vocabulary(
        self,
        vocab_name: str,
        output_format: str = "json",
        _include_metadata: bool = True,
    ) -> Union[str, Dict[str, Any]]:
        """Export vocabulary in specified format with optional metadata."""
        if vocab_name not in self.vocabularies:
            raise ValueError(f"Vocabulary '{vocab_name}' not found")

        # Get vocabulary for export
        # TODO: Move export methods from module level into this class
        if output_format == "json":
            return {"error": "JSON export not yet implemented"}
        elif output_format == "csv":
            return "CSV export not yet implemented"
        elif output_format == "transcribe":
            return "Transcribe export not yet implemented"
        elif output_format == "xml":
            return "XML export not yet implemented"
        else:
            raise ValueError(f"Unsupported format: {output_format}")

    def get_statistics(self, vocab_name: Optional[str] = None) -> VocabularyStatistics:
        """Get statistics about vocabularies."""
        if vocab_name:
            if vocab_name not in self.vocabularies:
                raise ValueError(f"Vocabulary '{vocab_name}' not found")
            vocabularies = [self.vocabularies[vocab_name]]
        else:
            vocabularies = list(self.vocabularies.values())

        stats: VocabularyStatistics = {
            "total_vocabularies": len(vocabularies),
            "total_terms": 0,
            "by_status": {
                "validated": 0,
                "pending": 0,
                "needs_review": 0,
                "rejected": 0,
            },
            "by_source": {},
            "by_specialty": {},
            "by_language": {},
        }

        for vocab in vocabularies:
            stats["total_terms"] += len(vocab.terms)

            # Count by specialty
            specialty = vocab.specialty.value
            stats["by_specialty"][specialty] = stats["by_specialty"].get(
                specialty, 0
            ) + len(vocab.terms)

            # Count by language
            language = vocab.language.value
            stats["by_language"][language] = stats["by_language"].get(
                language, 0
            ) + len(vocab.terms)

            for term in vocab.terms:
                # Count by status
                status = term.validation_status.value
                stats["by_status"][status] += 1

                # Count by source
                source = term.source.value
                stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

        return stats


# Example usage
if __name__ == "__main__":

    async def main() -> None:
        """Run example usage of custom vocabulary manager."""
        # Initialize manager
        manager = CustomVocabularyManager()

        # Create a custom vocabulary
        vocab = manager.create_vocabulary(
            name="cardiology_practice",
            description="Custom terms for cardiology practice",
            specialty=MedicalSpecialty.CARDIOLOGY,
            created_by="Dr. Smith",
        )
        # Add individual terms
        term = CustomVocabularyTerm(
            term="STEMI",
            sounds_like=["stem-ee", "s-t-e-m-i"],
            display_as="ST-elevation myocardial infarction (STEMI)",
            category="conditions",
            added_by="Dr. Smith",
        )
        vocab.add_term(term)

        # Validate vocabulary
        validation_results = manager.validate_vocabulary("cardiology_practice")
        print(f"Validation results: {validation_results}")

        # Upload to Amazon Transcribe Medical
        upload_result = await manager.upload_to_transcribe("cardiology_practice")
        print(f"Upload result: {upload_result}")

        # Get statistics
        stats = manager.get_statistics()
        print(f"Vocabulary statistics: {stats}")

    # Run example
    asyncio.run(main())


def _export_vocabulary_json(
    vocab: CustomVocabulary, include_metadata: bool
) -> Dict[str, Any]:
    """Export vocabulary as JSON with optional metadata."""
    export_data: Dict[str, Any] = {
        "name": vocab.name,
        "language": vocab.language.value,
        "specialty": vocab.specialty.value,
        "terms": [],
    }

    if include_metadata:
        export_data.update(
            {
                "created_date": (
                    vocab.created_date.isoformat() if vocab.created_date else None
                ),
                "modified_date": (
                    vocab.modified_date.isoformat() if vocab.modified_date else None
                ),
                "description": vocab.description,
                "version": getattr(vocab, "version", "1.0"),
                "statistics": {
                    "total_terms": len(vocab.terms),
                    "validated_terms": len(
                        [
                            t
                            for t in vocab.terms
                            if t.validation_status == ValidationStatus.VALIDATED
                        ]
                    ),
                    "pending_terms": len(
                        [
                            t
                            for t in vocab.terms
                            if t.validation_status == ValidationStatus.PENDING
                        ]
                    ),
                    "rejected_terms": len(
                        [
                            t
                            for t in vocab.terms
                            if t.validation_status == ValidationStatus.REJECTED
                        ]
                    ),
                },
                "export_metadata": {
                    "exported_at": datetime.utcnow().isoformat(),
                    "exported_by": "system",
                    "format_version": "2.0",
                    "compatible_systems": [
                        "Dragon Medical",
                        "Nuance",
                        "Haven Health",
                    ],
                },
            }
        )

    for term in vocab.terms:
        term_data: Dict[str, Any] = {
            "term": term.term,
            "phonetic": term.ipa,
            "sounds_like": term.sounds_like,
            "display_as": term.display_as,
            "category": term.category,
        }

        if include_metadata:
            term_data.update(
                {
                    "usage_count": getattr(term, "usage_count", 0),
                    "success_rate": getattr(term, "recognition_success_rate", 0.0),
                    "alternate_pronunciations": getattr(
                        term, "alternate_pronunciations", []
                    ),
                    "context_examples": getattr(term, "context_examples", [])[:5],
                    "related_terms": getattr(term, "related_terms", []),
                    "added_by": getattr(term, "added_by", "unknown"),
                    "added_date": getattr(
                        term, "added_date", datetime.utcnow()
                    ).isoformat(),
                    "last_updated": getattr(
                        term, "last_updated", datetime.utcnow()
                    ).isoformat(),
                    "validation_status": term.validation_status.value,
                    "clinical_codes": {
                        "icd10": getattr(term, "icd10_codes", []),
                        "snomed": getattr(term, "snomed_codes", []),
                        "loinc": getattr(term, "loinc_codes", []),
                        "rxnorm": getattr(term, "rxnorm_codes", []),
                    },
                    "translations": getattr(term, "translations", {}),
                    "cultural_notes": getattr(term, "cultural_notes", {}),
                    "audio_profile": {
                        "average_duration_ms": getattr(term, "avg_duration_ms", 0),
                        "frequency_range": getattr(term, "frequency_range", []),
                        "emphasis_pattern": getattr(
                            term, "emphasis_pattern", "neutral"
                        ),
                    },
                }
            )
        else:
            # Basic data only
            term_data["validation_status"] = term.validation_status.value

        export_data["terms"].append(term_data)

    return export_data


def _export_vocabulary_csv(vocab: CustomVocabulary, include_metadata: bool) -> str:
    """Export vocabulary as CSV with optional metadata."""
    output = io.StringIO()

    # Define headers based on metadata inclusion
    if include_metadata:
        headers = [
            "term",
            "sounds_like",
            "display_as",
            "category",
            "validation_status",
            "usage_count",
            "success_rate",
            "added_by",
            "added_date",
            "last_updated",
            "icd10_codes",
            "snomed_codes",
            "phonetic_spelling",
            "context_examples",
            "related_terms",
            "cultural_notes",
        ]
    else:
        headers = [
            "term",
            "sounds_like",
            "display_as",
            "category",
            "validation_status",
        ]

    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()

    for term in vocab.terms:
        row: Dict[str, Any] = {
            "term": term.term,
            "sounds_like": "|".join(term.sounds_like) if term.sounds_like else "",
            "display_as": term.display_as or "",
            "category": term.category or "",
            "validation_status": term.validation_status.value,
        }

        if include_metadata:
            row.update(
                {
                    "usage_count": getattr(term, "usage_count", 0),
                    "success_rate": f"{getattr(term, 'recognition_success_rate', 0.0):.2f}",
                    "added_by": getattr(term, "added_by", "unknown"),
                    "added_date": getattr(
                        term, "added_date", datetime.utcnow()
                    ).strftime("%Y-%m-%d"),
                    "last_updated": getattr(
                        term, "last_updated", datetime.utcnow()
                    ).strftime("%Y-%m-%d"),
                    "icd10_codes": "|".join(getattr(term, "icd10_codes", [])),
                    "snomed_codes": "|".join(getattr(term, "snomed_codes", [])),
                    "phonetic_spelling": term.ipa or "",
                    "context_examples": "|".join(
                        getattr(term, "context_examples", [])[:3]
                    ),
                    "related_terms": "|".join(getattr(term, "related_terms", [])),
                    "cultural_notes": json.dumps(getattr(term, "cultural_notes", {})),
                }
            )

        writer.writerow(row)

    return output.getvalue()


def _export_vocabulary_transcribe(
    vocab: CustomVocabulary, include_metadata: bool
) -> str:
    """Export vocabulary in Amazon Transcribe format with optional metadata."""
    lines = []

    if include_metadata:
        # Add metadata as comments
        lines.extend(
            [
                f"# Vocabulary: {vocab.name}",
                f"# Language: {vocab.language}",
                f"# Specialty: {vocab.specialty.value}",
                f"# Generated: {datetime.utcnow().isoformat()}",
                f"# Total Terms: {len(vocab.terms)}",
                "#",
            ]
        )

    # Only export validated terms for Transcribe
    for term in vocab.get_validated_terms():
        line_parts = [term.term]

        # Add pronunciation variations
        if term.sounds_like:
            line_parts.extend(term.sounds_like)

        # Add display form if different
        if term.display_as and term.display_as != term.term:
            line_parts.append(term.display_as)

        line = "\t".join(line_parts)

        if include_metadata and hasattr(term, "usage_count"):
            # Add usage count as comment
            line += f"\t# Usage: {term.usage_count}"

        lines.append(line)

    return "\n".join(lines)


def _export_vocabulary_xml(vocab: CustomVocabulary, include_metadata: bool) -> str:
    """Export vocabulary as XML with optional metadata."""
    # Use standard ElementTree for element creation
    import xml.etree.ElementTree as StdET

    root = StdET.Element("MedicalVocabulary")
    root.set("name", vocab.name)
    root.set("language", vocab.language.value)
    root.set("specialty", vocab.specialty.value)

    if include_metadata:
        # Add metadata section
        metadata_elem = StdET.SubElement(root, "Metadata")
        StdET.SubElement(metadata_elem, "CreatedAt").text = (
            vocab.created_date.isoformat() if vocab.created_date else ""
        )
        StdET.SubElement(metadata_elem, "UpdatedAt").text = (
            vocab.modified_date.isoformat() if vocab.modified_date else ""
        )
        StdET.SubElement(metadata_elem, "Version").text = getattr(
            vocab, "version", "1.0"
        )
        StdET.SubElement(metadata_elem, "ExportedAt").text = (
            datetime.utcnow().isoformat()
        )

        # Add statistics
        stats_elem = StdET.SubElement(metadata_elem, "Statistics")
        StdET.SubElement(stats_elem, "TotalTerms").text = str(len(vocab.terms))
        StdET.SubElement(stats_elem, "ValidatedTerms").text = str(
            len(
                [
                    t
                    for t in vocab.terms
                    if t.validation_status == ValidationStatus.VALIDATED
                ]
            )
        )

    # Add terms
    terms_elem = StdET.SubElement(root, "Terms")

    for term in vocab.terms:
        term_elem = StdET.SubElement(terms_elem, "Term")
        StdET.SubElement(term_elem, "Text").text = term.term
        StdET.SubElement(term_elem, "PhoneticSpelling").text = term.ipa or ""
        StdET.SubElement(term_elem, "DisplayAs").text = term.display_as or ""
        StdET.SubElement(term_elem, "Category").text = term.category or ""
        StdET.SubElement(term_elem, "ValidationStatus").text = (
            term.validation_status.value
        )

        # Add sounds like variations
        if term.sounds_like:
            sounds_elem = StdET.SubElement(term_elem, "SoundsLike")
            for sound in term.sounds_like:
                StdET.SubElement(sounds_elem, "Variation").text = sound

        if include_metadata:
            # Add extended metadata
            meta_elem = StdET.SubElement(term_elem, "Metadata")
            StdET.SubElement(meta_elem, "UsageCount").text = str(
                getattr(term, "usage_count", 0)
            )
            StdET.SubElement(meta_elem, "SuccessRate").text = (
                f"{getattr(term, 'recognition_success_rate', 0.0):.2f}"
            )
            StdET.SubElement(meta_elem, "AddedBy").text = getattr(
                term, "added_by", "unknown"
            )
            StdET.SubElement(meta_elem, "AddedDate").text = getattr(
                term, "added_date", datetime.utcnow()
            ).isoformat()

            # Add clinical codes
            codes_elem = StdET.SubElement(meta_elem, "ClinicalCodes")
            for code in getattr(term, "icd10_codes", []):
                StdET.SubElement(codes_elem, "ICD10").text = code
            for code in getattr(term, "snomed_codes", []):
                StdET.SubElement(codes_elem, "SNOMED").text = code

            # Add translations
            if hasattr(term, "translations") and term.translations:
                trans_elem = StdET.SubElement(meta_elem, "Translations")
                for lang, trans in term.translations.items():
                    elem = StdET.SubElement(trans_elem, "Translation")
                    elem.set("language", lang)
                    elem.text = trans

    # Pretty print XML
    xml_str = StdET.tostring(root, encoding="unicode")
    dom = minidom.parseString(xml_str)  # nosec B318 - defusedxml imported at top
    return str(dom.toprettyxml(indent="  "))


def import_vocabulary(
    vocab_data: Union[str, Dict[str, Any]],
    input_format: str = "json",
    merge_strategy: str = "append",  # append, replace, merge
) -> CustomVocabulary:
    """Import vocabulary with validation and merging support."""
    # TODO: Move this function into CustomVocabularyManager class
    raise NotImplementedError("Import functionality not yet implemented")


def _import_vocabulary_json(
    vocab_dict: Dict[str, Any], merge_strategy: str
) -> CustomVocabulary:
    """Import vocabulary from JSON format."""
    vocab_name = vocab_dict.get("name")
    if not vocab_name or not isinstance(vocab_name, str):
        raise ValueError("Vocabulary name must be a non-empty string")

    # This function is a module-level function, not a method
    # Using placeholder logic for vocabulary management
    vocabularies: Dict[str, CustomVocabulary] = {}

    if merge_strategy == "replace" and vocab_name in vocabularies:
        # Remove existing vocabulary
        del vocabularies[vocab_name]

    if vocab_name in vocabularies and merge_strategy == "merge":
        # Merge with existing
        existing_vocab = vocabularies[vocab_name]
        existing_terms = {t.term: t for t in existing_vocab.terms}

        for term_data in vocab_dict.get("terms", []):
            term_text = term_data["term"]
            if term_text in existing_terms:
                # Update existing term
                existing_term = existing_terms[term_text]
                if "usage_count" in term_data:
                    existing_term.usage_count = max(
                        getattr(existing_term, "usage_count", 0),
                        term_data["usage_count"],
                    )
            else:
                # Add new term
                new_term = CustomVocabularyTerm(
                    term=term_text,
                    sounds_like=term_data.get("sounds_like", []),
                    display_as=term_data.get("display_as"),
                    category=term_data.get("category"),
                )
                existing_vocab.add_term(new_term)

        return existing_vocab
    else:
        # Create new vocabulary
        vocab = CustomVocabulary(
            name=vocab_name,
            language=vocab_dict.get("language", "en-US"),
        )

        # Add terms
        for term_data in vocab_dict.get("terms", []):
            new_term = CustomVocabularyTerm(
                term=term_data["term"],
                sounds_like=term_data.get("sounds_like", []),
                display_as=term_data.get("display_as"),
                category=term_data.get("category"),
            )
            vocab.add_term(new_term)

        vocabularies[vocab_name] = vocab
        return vocab


def merge_vocabularies(
    vocab_names: List[str], target_name: str, deduplication: bool = True
) -> CustomVocabulary:
    """Merge multiple vocabularies into one."""
    # TODO: Move this function into CustomVocabularyManager class
    raise NotImplementedError("Merge functionality not yet implemented")

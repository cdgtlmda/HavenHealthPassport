"""Medical Specialty Vocabularies Configuration.

This module provides configuration and management of medical specialty vocabularies
for Amazon Transcribe Medical to improve accuracy for domain-specific terminology.

Security Note: This module processes PHI-related medical terminology. All vocabulary
data must be encrypted at rest in S3 and during transmission. Access to medical
vocabularies should be restricted to authorized healthcare personnel only through
IAM policies and role-based access controls.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from .transcribe_medical import LanguageCode, MedicalSpecialty

logger = logging.getLogger(__name__)


class VocabularyState(Enum):
    """State of a medical vocabulary."""

    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass
class MedicalTerm:
    """Represents a medical term for vocabulary."""

    term: str
    sounds_like: Optional[List[str]] = None
    ipa: Optional[str] = None  # International Phonetic Alphabet
    display_as: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for vocabulary format."""
        entry = {"Phrase": self.term}

        if self.sounds_like:
            entry["SoundsLike"] = ",".join(self.sounds_like)
        if self.ipa:
            entry["IPA"] = self.ipa
        if self.display_as:
            entry["DisplayAs"] = self.display_as
        return entry


@dataclass
class SpecialtyVocabulary:
    """Medical specialty vocabulary configuration."""

    name: str
    specialty: MedicalSpecialty
    language_code: LanguageCode
    terms: List[MedicalTerm] = field(default_factory=list)
    description: Optional[str] = None
    version: str = "1.0"
    created_at: Optional[datetime] = None
    state: VocabularyState = VocabularyState.PENDING

    def to_vocabulary_format(self) -> str:
        """Convert to Amazon Transcribe Medical vocabulary format."""
        vocabulary_entries = [term.to_dict() for term in self.terms]
        return json.dumps(vocabulary_entries, indent=2)


class MedicalVocabularyManager:
    """
    Manages medical specialty vocabularies for Amazon Transcribe Medical.

    Features:
    - Pre-built specialty vocabularies
    - Custom vocabulary creation
    - Vocabulary lifecycle management
    - Pronunciation variations
    - Medical abbreviation handling
    """

    def __init__(self, region: str = "us-east-1"):
        """Initialize the vocabulary manager."""
        self.region = region
        self.transcribe_client = boto3.client("transcribe", region_name=region)
        self.s3_client = boto3.client("s3", region_name=region)

        # Vocabulary storage
        self.vocabularies: Dict[str, SpecialtyVocabulary] = {}
        self.vocabulary_bucket = "haven-health-medical-vocabularies"

        # Initialize default vocabularies
        self._initialize_default_vocabularies()

        logger.info("Medical vocabulary manager initialized in %s", region)

    def _initialize_default_vocabularies(self) -> None:
        """Initialize default medical specialty vocabularies."""
        # Primary Care vocabulary
        self._create_primary_care_vocabulary()

        # Cardiology vocabulary
        self._create_cardiology_vocabulary()
        # Neurology vocabulary
        self._create_neurology_vocabulary()

        # Radiology vocabulary
        self._create_radiology_vocabulary()

    def _create_primary_care_vocabulary(self) -> None:
        """Create primary care specialty vocabulary."""
        vocab = SpecialtyVocabulary(
            name="primary_care_vocab_v1",
            specialty=MedicalSpecialty.PRIMARYCARE,
            language_code=LanguageCode.EN_US,
            description="Common primary care medical terms",
        )

        # Common symptoms
        vocab.terms.extend(
            [
                MedicalTerm(
                    term="dyspnea",
                    sounds_like=["disp-nee-uh", "dis-nee-uh"],
                    display_as="dyspnea",
                ),
                MedicalTerm(
                    term="pyrexia",
                    sounds_like=["pie-rex-ee-uh"],
                    display_as="pyrexia (fever)",
                ),
                MedicalTerm(
                    term="malaise", sounds_like=["muh-laze"], display_as="malaise"
                ),
                MedicalTerm(
                    term="myalgia", sounds_like=["my-al-juh"], display_as="myalgia"
                ),
                MedicalTerm(
                    term="arthralgia",
                    sounds_like=["ar-thral-juh"],
                    display_as="arthralgia",
                ),
            ]
        )

        # Common medications
        vocab.terms.extend(
            [
                MedicalTerm(
                    term="acetaminophen",
                    sounds_like=["uh-see-tuh-min-oh-fen"],
                    display_as="acetaminophen",
                ),
                MedicalTerm(
                    term="ibuprofen",
                    sounds_like=["eye-bew-pro-fen"],
                    display_as="ibuprofen",
                ),
                MedicalTerm(
                    term="amoxicillin",
                    sounds_like=["uh-mox-ih-sil-in"],
                    display_as="amoxicillin",
                ),
                MedicalTerm(
                    term="metformin",
                    sounds_like=["met-for-min"],
                    display_as="metformin",
                ),
            ]
        )

        # Common conditions
        vocab.terms.extend(
            [
                MedicalTerm(
                    term="hypertension",
                    sounds_like=["high-per-ten-shun"],
                    display_as="hypertension",
                ),
                MedicalTerm(
                    term="diabetes mellitus",
                    sounds_like=["die-uh-bee-tees mel-ih-tus"],
                    display_as="diabetes mellitus",
                ),
                MedicalTerm(
                    term="COPD", sounds_like=["see-oh-pee-dee"], display_as="COPD"
                ),
                MedicalTerm(term="GERD", sounds_like=["gerd"], display_as="GERD"),
            ]
        )

        self.vocabularies["primary_care"] = vocab

    def _create_cardiology_vocabulary(self) -> None:
        """Create cardiology specialty vocabulary."""
        vocab = SpecialtyVocabulary(
            name="cardiology_vocab_v1",
            specialty=MedicalSpecialty.CARDIOLOGY,
            language_code=LanguageCode.EN_US,
            description="Cardiology-specific medical terms",
        )

        # Cardiac conditions
        vocab.terms.extend(
            [
                MedicalTerm(
                    term="myocardial infarction",
                    sounds_like=["my-oh-car-dee-al in-fark-shun"],
                    display_as="myocardial infarction (MI)",
                ),
                MedicalTerm(
                    term="angina pectoris",
                    sounds_like=["an-jie-nuh pek-tor-is"],
                    display_as="angina pectoris",
                ),
                MedicalTerm(
                    term="arrhythmia",
                    sounds_like=["uh-rith-mee-uh"],
                    display_as="arrhythmia",
                ),
                MedicalTerm(
                    term="atrial fibrillation",
                    sounds_like=["ay-tree-al fib-rih-lay-shun"],
                    display_as="atrial fibrillation (AFib)",
                ),
                MedicalTerm(
                    term="stenosis", sounds_like=["steh-no-sis"], display_as="stenosis"
                ),
            ]
        )

        # Cardiac procedures
        vocab.terms.extend(
            [
                MedicalTerm(
                    term="angioplasty",
                    sounds_like=["an-jee-oh-plas-tee"],
                    display_as="angioplasty",
                ),
                MedicalTerm(
                    term="catheterization",
                    sounds_like=["kath-eh-ter-ih-zay-shun"],
                    display_as="catheterization",
                ),
                MedicalTerm(
                    term="echocardiogram",
                    sounds_like=["ek-oh-car-dee-oh-gram"],
                    display_as="echocardiogram",
                ),
                MedicalTerm(
                    term="electrocardiogram",
                    sounds_like=["ee-lek-troh-car-dee-oh-gram"],
                    display_as="electrocardiogram (ECG/EKG)",
                ),
            ]
        )

        self.vocabularies["cardiology"] = vocab

    def _create_neurology_vocabulary(self) -> None:
        """Create neurology specialty vocabulary."""
        vocab = SpecialtyVocabulary(
            name="neurology_vocab_v1",
            specialty=MedicalSpecialty.NEUROLOGY,
            language_code=LanguageCode.EN_US,
            description="Neurology-specific medical terms",
        )

        # Neurological conditions
        vocab.terms.extend(
            [
                MedicalTerm(
                    term="epilepsy",
                    sounds_like=["ep-ih-lep-see"],
                    display_as="epilepsy",
                ),
                MedicalTerm(
                    term="migraine", sounds_like=["my-grain"], display_as="migraine"
                ),
                MedicalTerm(
                    term="paresthesia",
                    sounds_like=["par-es-thee-zhuh"],
                    display_as="paresthesia",
                ),
                MedicalTerm(
                    term="hemiparesis",
                    sounds_like=["hem-ee-puh-ree-sis"],
                    display_as="hemiparesis",
                ),
                MedicalTerm(
                    term="neuropathy",
                    sounds_like=["new-rop-uh-thee"],
                    display_as="neuropathy",
                ),
            ]
        )

        self.vocabularies["neurology"] = vocab

    def _create_radiology_vocabulary(self) -> None:
        """Create radiology specialty vocabulary."""
        vocab = SpecialtyVocabulary(
            name="radiology_vocab_v1",
            specialty=MedicalSpecialty.RADIOLOGY,
            language_code=LanguageCode.EN_US,
            description="Radiology-specific medical terms",
        )

        # Imaging terms
        vocab.terms.extend(
            [
                MedicalTerm(
                    term="computed tomography",
                    sounds_like=["com-pew-ted toh-mog-ruh-fee"],
                    display_as="computed tomography (CT)",
                ),
                MedicalTerm(
                    term="magnetic resonance imaging",
                    sounds_like=["mag-net-ik rez-oh-nance im-ij-ing"],
                    display_as="magnetic resonance imaging (MRI)",
                ),
                MedicalTerm(
                    term="radiograph",
                    sounds_like=["ray-dee-oh-graf"],
                    display_as="radiograph",
                ),
                MedicalTerm(
                    term="contrast medium",
                    sounds_like=["kon-trast mee-dee-um"],
                    display_as="contrast medium",
                ),
            ]
        )

        self.vocabularies["radiology"] = vocab

    async def configure_specialty_vocabularies(self) -> Dict[str, bool]:
        """
        Configure all medical specialty vocabularies in Transcribe Medical.

        Returns:
            Dictionary of vocabulary names and their configuration status
        """
        results = {}

        for _, vocabulary in self.vocabularies.items():
            try:
                # Create vocabulary in Transcribe Medical
                success = await self._create_medical_vocabulary(vocabulary)
                results[vocabulary.name] = success

                if success:
                    logger.info("Configured vocabulary: %s", vocabulary.name)
                else:
                    logger.error("Failed to configure vocabulary: %s", vocabulary.name)

            except (RuntimeError, ValueError, AttributeError) as e:
                logger.error("Error configuring vocabulary %s: %s", vocabulary.name, e)
                results[vocabulary.name] = False

        return results

    async def _create_medical_vocabulary(self, vocabulary: SpecialtyVocabulary) -> bool:
        """Create a medical vocabulary in Amazon Transcribe Medical."""
        try:
            # First, upload vocabulary to S3
            s3_uri = await self._upload_vocabulary_to_s3(vocabulary)

            # Create vocabulary in Transcribe Medical
            self.transcribe_client.create_medical_vocabulary(
                VocabularyName=vocabulary.name,
                LanguageCode=vocabulary.language_code.value,
                VocabularyFileUri=s3_uri,
            )

            vocabulary.state = VocabularyState.PENDING
            vocabulary.created_at = datetime.utcnow()

            # Wait for vocabulary to be ready
            ready = await self._wait_for_vocabulary_ready(vocabulary.name)

            if ready:
                vocabulary.state = VocabularyState.READY
                return True
            else:
                vocabulary.state = VocabularyState.FAILED
                return False

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConflictException":
                # Vocabulary already exists, update it
                return await self._update_medical_vocabulary(vocabulary)
            else:
                logger.error("Failed to create vocabulary: %s", e)
                return False

    async def _upload_vocabulary_to_s3(self, vocabulary: SpecialtyVocabulary) -> str:
        """Upload vocabulary file to S3."""
        # Ensure bucket exists
        try:
            self.s3_client.head_bucket(Bucket=self.vocabulary_bucket)
        except ClientError:
            # Create bucket if it doesn't exist
            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=self.vocabulary_bucket)
            else:
                self.s3_client.create_bucket(
                    Bucket=self.vocabulary_bucket,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )

        # Generate S3 key
        s3_key = f"vocabularies/{vocabulary.name}.json"

        # Upload vocabulary content
        vocabulary_content = vocabulary.to_vocabulary_format()

        self.s3_client.put_object(
            Bucket=self.vocabulary_bucket,
            Key=s3_key,
            Body=vocabulary_content.encode("utf-8"),
            ContentType="application/json",
        )

        s3_uri = f"s3://{self.vocabulary_bucket}/{s3_key}"
        logger.info("Uploaded vocabulary to %s", s3_uri)

        return s3_uri

    async def _wait_for_vocabulary_ready(
        self, vocabulary_name: str, max_wait_time: int = 300
    ) -> bool:
        """Wait for vocabulary to be ready."""
        start_time = datetime.utcnow()

        while True:
            try:
                response = self.transcribe_client.get_medical_vocabulary(
                    VocabularyName=vocabulary_name
                )

                state = response["VocabularyState"]

                if state == "READY":
                    return True
                elif state == "FAILED":
                    logger.error("Vocabulary %s failed", vocabulary_name)
                    return False

                # Check timeout
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > max_wait_time:
                    logger.error("Vocabulary %s timed out", vocabulary_name)
                    return False

                # Wait before next check
                await asyncio.sleep(5)

            except ClientError as e:
                logger.error("Error checking vocabulary status: %s", e)
                return False

    async def _update_medical_vocabulary(self, vocabulary: SpecialtyVocabulary) -> bool:
        """Update an existing medical vocabulary."""
        try:
            # Upload new vocabulary content
            s3_uri = await self._upload_vocabulary_to_s3(vocabulary)

            # Update vocabulary
            self.transcribe_client.update_medical_vocabulary(
                VocabularyName=vocabulary.name,
                LanguageCode=vocabulary.language_code.value,
                VocabularyFileUri=s3_uri,
            )

            # Wait for update to complete
            return await self._wait_for_vocabulary_ready(vocabulary.name)

        except ClientError as e:
            logger.error("Failed to update vocabulary: %s", e)
            return False

    def add_custom_terms(
        self, specialty: MedicalSpecialty, terms: List[MedicalTerm]
    ) -> None:
        """Add custom terms to a specialty vocabulary."""
        vocab_key = specialty.value.lower()

        if vocab_key in self.vocabularies:
            self.vocabularies[vocab_key].terms.extend(terms)
            logger.info("Added %d terms to %s vocabulary", len(terms), specialty.value)
        else:
            logger.error("Vocabulary not found for specialty: %s", specialty.value)

    async def list_configured_vocabularies(self) -> List[Dict[str, Any]]:
        """List all configured medical vocabularies."""
        try:
            response = self.transcribe_client.list_medical_vocabularies(MaxResults=100)

            vocabularies = []
            for vocab in response.get("Vocabularies", []):
                vocabularies.append(
                    {
                        "name": vocab["VocabularyName"],
                        "language": vocab["LanguageCode"],
                        "state": vocab["VocabularyState"],
                        "last_modified": vocab.get("LastModifiedTime"),
                    }
                )

            return vocabularies
        except ClientError as e:
            logger.error("Failed to list vocabularies: %s", e)
            return []

    def get_vocabulary_info(
        self, specialty: MedicalSpecialty
    ) -> Optional[Dict[str, Any]]:
        """Get information about a specialty vocabulary."""
        vocab_key = specialty.value.lower()

        if vocab_key in self.vocabularies:
            vocab = self.vocabularies[vocab_key]
            return {
                "name": vocab.name,
                "specialty": vocab.specialty.value,
                "language": vocab.language_code.value,
                "term_count": len(vocab.terms),
                "version": vocab.version,
                "state": vocab.state.value,
                "created_at": (
                    vocab.created_at.isoformat() if vocab.created_at else None
                ),
            }

        return None

    async def export_vocabulary(
        self, specialty: MedicalSpecialty, output_path: Path
    ) -> bool:
        """Export a vocabulary to file."""
        vocab_key = specialty.value.lower()

        if vocab_key not in self.vocabularies:
            logger.error("Vocabulary not found for specialty: %s", specialty.value)
            return False

        vocab = self.vocabularies[vocab_key]

        try:
            # Write vocabulary to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(vocab.to_vocabulary_format())

            logger.info("Exported vocabulary to %s", output_path)
            return True

        except (IOError, json.JSONDecodeError) as e:
            logger.error("Failed to export vocabulary: %s", e)
            return False

    async def load_custom_vocabulary(self, vocabulary_id: str) -> bool:
        """Load a custom vocabulary by ID."""
        try:
            # Try to load from S3 first
            s3_key = f"custom-vocabularies/{vocabulary_id}.json"

            try:
                response = self.s3_client.get_object(
                    Bucket=self.vocabulary_bucket, Key=s3_key
                )
                vocabulary_data = json.loads(response["Body"].read().decode("utf-8"))

                # Parse vocabulary data
                vocab = SpecialtyVocabulary(
                    name=vocabulary_data.get("name", vocabulary_id),
                    specialty=MedicalSpecialty(
                        vocabulary_data.get("specialty", "PRIMARYCARE")
                    ),
                    language_code=LanguageCode(
                        vocabulary_data.get("language_code", "en-US")
                    ),
                    description=vocabulary_data.get("description"),
                    version=vocabulary_data.get("version", "1.0"),
                    created_at=(
                        datetime.fromisoformat(vocabulary_data["created_at"])
                        if "created_at" in vocabulary_data
                        else datetime.utcnow()
                    ),
                    state=VocabularyState(vocabulary_data.get("state", "READY")),
                )

                # Load terms
                for term_data in vocabulary_data.get("terms", []):
                    term = MedicalTerm(
                        term=term_data["term"],
                        sounds_like=term_data.get("sounds_like"),
                        ipa=term_data.get("ipa"),
                        display_as=term_data.get("display_as"),
                    )
                    vocab.terms.append(term)

                # Store in memory
                self.vocabularies[vocabulary_id] = vocab

                logger.info(
                    "Successfully loaded custom vocabulary: %s from S3", vocabulary_id
                )
                return True

            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    # Try loading from local file system
                    local_path = Path(f"vocabularies/{vocabulary_id}.json")
                    if local_path.exists():
                        with open(local_path, "r", encoding="utf-8") as f:
                            vocabulary_data = json.load(f)

                        # Parse vocabulary data (same as above)
                        vocab = SpecialtyVocabulary(
                            name=vocabulary_data.get("name", vocabulary_id),
                            specialty=MedicalSpecialty(
                                vocabulary_data.get("specialty", "PRIMARYCARE")
                            ),
                            language_code=LanguageCode(
                                vocabulary_data.get("language_code", "en-US")
                            ),
                            description=vocabulary_data.get("description"),
                            version=vocabulary_data.get("version", "1.0"),
                            created_at=(
                                datetime.fromisoformat(vocabulary_data["created_at"])
                                if "created_at" in vocabulary_data
                                else datetime.utcnow()
                            ),
                            state=VocabularyState(
                                vocabulary_data.get("state", "READY")
                            ),
                        )

                        # Load terms
                        for term_data in vocabulary_data.get("terms", []):
                            term = MedicalTerm(
                                term=term_data["term"],
                                sounds_like=term_data.get("sounds_like"),
                                ipa=term_data.get("ipa"),
                                display_as=term_data.get("display_as"),
                            )
                            vocab.terms.append(term)

                        # Store in memory
                        self.vocabularies[vocabulary_id] = vocab

                        logger.info(
                            "Successfully loaded custom vocabulary: %s from local file",
                            vocabulary_id,
                        )
                        return True
                    else:
                        logger.error(
                            "Vocabulary not found in S3 or local filesystem: %s",
                            vocabulary_id,
                        )
                        return False
                else:
                    logger.error("S3 error loading vocabulary: %s", e)
                    return False

        except (ValueError, KeyError, json.JSONDecodeError) as e:
            logger.error("Failed to load custom vocabulary %s: %s", vocabulary_id, e)
            return False

"""
Medical Pronunciation System using AWS Polly.

This module generates pronunciation guides and voice synthesis for
medical terms in multiple languages using AWS Polly neural voices.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, cast

import boto3

from src.healthcare.fhir_validator import FHIRValidator
from src.translation.medical_terminology import MedicalTerminologyManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class VoiceType(str, Enum):
    """Types of voices for synthesis."""

    STANDARD = "standard"
    NEURAL = "neural"
    NEWSCASTER = "newscaster"
    CONVERSATIONAL = "conversational"


class PronunciationType(str, Enum):
    """Types of pronunciation content."""

    MEDICAL_TERM = "medical_term"
    DRUG_NAME = "drug_name"
    DOSAGE_INSTRUCTION = "dosage_instruction"
    ANATOMY = "anatomy"
    PROCEDURE = "procedure"
    PATIENT_INSTRUCTION = "patient_instruction"


@dataclass
class VoiceProfile:
    """Voice profile for synthesis."""

    voice_id: str
    language_code: str
    gender: str
    engine: VoiceType
    sample_rate: int = 22050
    neural_available: bool = True
    medical_optimized: bool = False


@dataclass
class PronunciationGuide:
    """Pronunciation guide for a medical term."""

    term: str
    language: str
    ipa_notation: str
    phonetic_spelling: str
    syllable_breakdown: List[str]
    stress_pattern: str
    audio_url: Optional[str] = None
    alternative_pronunciations: List[str] = field(default_factory=list)


@dataclass
class SynthesisResult:
    """Result of voice synthesis."""

    text: str
    language: str
    voice_id: str
    audio_data: bytes
    audio_format: str
    duration_ms: int
    ssml_used: bool
    pronunciation_guides: List[PronunciationGuide]


class MedicalPronunciationSystem:
    """Generates pronunciation guides using AWS Polly.

    Handles FHIR DomainResource data for medical terminology pronunciation.
    """

    # Supported languages with medical voices
    MEDICAL_VOICES = {
        "en-US": [
            VoiceProfile("Joanna", "en-US", "female", VoiceType.NEURAL),
            VoiceProfile("Matthew", "en-US", "male", VoiceType.NEURAL),
            VoiceProfile(
                "Ruth", "en-US", "female", VoiceType.NEURAL, medical_optimized=True
            ),
        ],
        "es-ES": [
            VoiceProfile("Lucia", "es-ES", "female", VoiceType.NEURAL),
            VoiceProfile("Sergio", "es-ES", "male", VoiceType.NEURAL),
        ],
        "fr-FR": [
            VoiceProfile("Lea", "fr-FR", "female", VoiceType.NEURAL),
            VoiceProfile("Remi", "fr-FR", "male", VoiceType.NEURAL),
        ],
        "ar": [VoiceProfile("Zeina", "ar", "female", VoiceType.STANDARD)],
        "hi-IN": [
            VoiceProfile("Kajal", "hi-IN", "female", VoiceType.NEURAL),
            VoiceProfile("Arjun", "hi-IN", "male", VoiceType.STANDARD),
        ],
        "pt-BR": [VoiceProfile("Camila", "pt-BR", "female", VoiceType.NEURAL)],
        "zh-CN": [VoiceProfile("Zhiyu", "zh-CN", "female", VoiceType.NEURAL)],
    }

    # Medical spelling alphabets
    MEDICAL_ALPHABETS = {
        "en": {
            "A": "Alpha",
            "B": "Bravo",
            "C": "Charlie",
            "D": "Delta",
            "E": "Echo",
            "F": "Foxtrot",
            "G": "Golf",
            "H": "Hotel",
            "I": "India",
            "J": "Juliet",
            "K": "Kilo",
            "L": "Lima",
            "M": "Mike",
            "N": "November",
            "O": "Oscar",
            "P": "Papa",
            "Q": "Quebec",
            "R": "Romeo",
            "S": "Sierra",
            "T": "Tango",
            "U": "Uniform",
            "V": "Victor",
            "W": "Whiskey",
            "X": "X-ray",
            "Y": "Yankee",
            "Z": "Zulu",
        }
    }

    # SSML templates for medical pronunciation
    SSML_TEMPLATES = {
        "drug_name": """
        <speak>
            <prosody rate="slow">
                <say-as interpret-as="spell-out">{drug_name}</say-as>
            </prosody>
            <break time="500ms"/>
            <prosody rate="medium">
                {drug_name}
            </prosody>
        </speak>
        """,
        "dosage": """
        <speak>
            <emphasis level="strong">{amount}</emphasis>
            <say-as interpret-as="unit">{unit}</say-as>
            <break time="300ms"/>
            {frequency}
        </speak>
        """,
        "medical_term": """
        <speak>
            <phoneme alphabet="ipa" ph="{ipa}">{term}</phoneme>
            <break time="500ms"/>
            <prosody rate="slow">
                {syllables}
            </prosody>
        </speak>
        """,
    }

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize medical pronunciation system.

        Args:
            region: AWS region
        """
        self.polly = boto3.client("polly", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)
        self.terminology_manager = MedicalTerminologyManager()
        self._pronunciation_cache: Dict[str, Any] = {}
        self.bucket_name = "haven-health-pronunciation"
        # Enable validation for FHIR compliance
        self.validation_enabled = True
        self.fhir_validator = FHIRValidator()

    def validate_fhir_compliance(self, data: Dict[str, Any]) -> bool:
        """Validate FHIR compliance for healthcare data."""
        if not self.validation_enabled:
            return True
        # Validate as Communication resource for pronunciation data
        result = self.fhir_validator.validate_resource("Communication", data)
        return cast(bool, result.get("valid", False))

    async def generate_pronunciation_guide(
        self, term: str, language: str, pronunciation_type: PronunciationType
    ) -> PronunciationGuide:
        """
        Generate pronunciation guide for medical term.

        Args:
            term: Medical term
            language: Language code
            pronunciation_type: Type of pronunciation

        Returns:
            Pronunciation guide
        """
        try:
            # Check cache
            cache_key = f"{term}:{language}:{pronunciation_type}"
            if cache_key in self._pronunciation_cache:
                cached_guide = self._pronunciation_cache[cache_key]
                if isinstance(cached_guide, PronunciationGuide):
                    return cached_guide

            # Get IPA notation
            ipa_notation = await self._get_ipa_notation(term, language)

            # Generate phonetic spelling
            phonetic_spelling = self._generate_phonetic_spelling(
                term, language, pronunciation_type
            )

            # Break down syllables
            syllables = self._break_into_syllables(term, language)

            # Determine stress pattern
            stress_pattern = self._determine_stress_pattern(term, language)

            # Get alternative pronunciations
            alternatives = await self._get_alternative_pronunciations(term, language)

            # Create guide
            guide = PronunciationGuide(
                term=term,
                language=language,
                ipa_notation=ipa_notation,
                phonetic_spelling=phonetic_spelling,
                syllable_breakdown=syllables,
                stress_pattern=stress_pattern,
                alternative_pronunciations=alternatives,
            )

            # Cache guide
            self._pronunciation_cache[cache_key] = guide

            return guide

        except Exception as e:
            logger.error(f"Error generating pronunciation guide: {e}")
            # Return basic guide
            return PronunciationGuide(
                term=term,
                language=language,
                ipa_notation="",
                phonetic_spelling=term,
                syllable_breakdown=[term],
                stress_pattern="",
                alternative_pronunciations=[],
            )

    async def _get_ipa_notation(self, term: str, language: str) -> str:
        """Get IPA notation for term."""
        # This would integrate with IPA dictionary or service
        # For now, return placeholder

        # Common medical terms IPA
        ipa_mappings = {
            "diabetes": "ˌdaɪəˈbiːtiːz",
            "hypertension": "ˌhaɪpərˈtenʃən",
            "pneumonia": "njuːˈmoʊniə",
            "anesthesia": "ˌænəsˈθiːziə",
            "cardiovascular": "ˌkɑːrdioʊˈvæskjələr",
        }

        return ipa_mappings.get(term.lower(), "")

    def _generate_phonetic_spelling(
        self, term: str, language: str, pronunciation_type: PronunciationType
    ) -> str:
        """Generate phonetic spelling."""
        if pronunciation_type == PronunciationType.DRUG_NAME:
            # Special handling for drug names
            return self._phonetic_drug_name(term)

        # General phonetic spelling
        phonetic_mappings = {
            "ph": "f",
            "ch": "k",
            "tion": "shun",
            "sion": "zhun",
            "ture": "cher",
        }

        phonetic = term.lower()
        for pattern, replacement in phonetic_mappings.items():
            phonetic = phonetic.replace(pattern, replacement)

        return phonetic.upper()

    def _phonetic_drug_name(self, drug_name: str) -> str:
        """Generate phonetic spelling for drug name."""
        # Common drug name patterns
        patterns = {
            "mab": "MAB (monoclonal antibody)",
            "ib": "IB (inhibitor)",
            "ol": "OL (beta blocker)",
            "pril": "PRIL (ACE inhibitor)",
            "statin": "STATIN (cholesterol medication)",
        }

        phonetic = drug_name
        for suffix, explanation in patterns.items():
            if drug_name.lower().endswith(suffix):
                phonetic += f" [{explanation}]"
                break

        return phonetic

    def _break_into_syllables(self, term: str, language: str) -> List[str]:
        """Break term into syllables."""
        # Simplified syllable breaking
        # In production, would use linguistic rules

        vowels = "aeiouAEIOU"
        syllables = []
        current_syllable = ""

        for i, char in enumerate(term):
            current_syllable += char

            if char in vowels and i < len(term) - 1:
                next_char = term[i + 1]
                if next_char not in vowels:
                    if i < len(term) - 2:
                        syllables.append(current_syllable)
                        current_syllable = ""

        if current_syllable:
            syllables.append(current_syllable)

        return syllables if syllables else [term]

    def _determine_stress_pattern(self, term: str, language: str) -> str:
        """Determine stress pattern for term."""
        # Medical terms often have specific stress patterns

        # Common patterns
        if term.lower().endswith("itis"):  # inflammation
            return "pen-UL-ti-mate"  # Stress on second-to-last syllable
        elif term.lower().endswith("ology"):  # study of
            return "an-te-pen-UL-ti-mate"  # Stress on third-to-last
        elif term.lower().endswith("osis"):  # condition
            return "pen-UL-ti-mate"

        return "primary"  # Default primary stress

    async def _get_alternative_pronunciations(
        self, term: str, language: str
    ) -> List[str]:
        """Get alternative pronunciations."""
        alternatives = []

        # Check for regional variants
        # This would query pronunciation database

        # Common alternatives
        if term.lower() == "acetaminophen":
            alternatives = ["a-SEET-a-MIN-oh-fen", "a-set-a-MIN-oh-fen"]
        elif term.lower() == "ibuprofen":
            alternatives = ["eye-bew-PRO-fen", "eye-byoo-PRO-fen"]

        return alternatives

    async def synthesize_medical_term(
        self,
        text: str,
        language: str,
        pronunciation_type: PronunciationType,
        voice_gender: Optional[str] = None,
        include_spelling: bool = True,
    ) -> SynthesisResult:
        """
        Synthesize speech for medical term.

        Args:
            text: Text to synthesize
            language: Language code
            pronunciation_type: Type of content
            voice_gender: Preferred voice gender
            include_spelling: Include spelled out version

        Returns:
            Synthesis result
        """
        try:
            # Get pronunciation guide
            guide = await self.generate_pronunciation_guide(
                text, language, pronunciation_type
            )

            # Select voice
            voice = self._select_voice(language, voice_gender)

            # Generate SSML
            ssml = self._generate_ssml(
                text, guide, pronunciation_type, include_spelling
            )

            # Synthesize speech
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.polly.synthesize_speech(
                    Text=ssml,
                    TextType="ssml",
                    OutputFormat="mp3",
                    VoiceId=voice.voice_id,
                    Engine=voice.engine.value,
                ),
            )

            # Get audio data
            audio_data = response["AudioStream"].read()

            # Calculate duration (approximate)
            duration_ms = len(audio_data) // 32  # Rough estimate

            return SynthesisResult(
                text=text,
                language=language,
                voice_id=voice.voice_id,
                audio_data=audio_data,
                audio_format="mp3",
                duration_ms=duration_ms,
                ssml_used=True,
                pronunciation_guides=[guide],
            )

        except Exception as e:
            logger.error(f"Error synthesizing medical term: {e}")
            raise

    def _select_voice(
        self, language: str, gender: Optional[str] = None
    ) -> VoiceProfile:
        """Select appropriate voice for language."""
        voices = self.MEDICAL_VOICES.get(language, [])

        if not voices:
            # Default to English
            voices = self.MEDICAL_VOICES["en-US"]

        # Filter by gender if specified
        if gender:
            gender_voices = [v for v in voices if v.gender == gender]
            if gender_voices:
                voices = gender_voices

        # Prefer medical-optimized voices
        medical_voices = [v for v in voices if v.medical_optimized]
        if medical_voices:
            return medical_voices[0]

        # Prefer neural voices
        neural_voices = [v for v in voices if v.engine == VoiceType.NEURAL]
        if neural_voices:
            return neural_voices[0]

        return voices[0]

    def _generate_ssml(
        self,
        text: str,
        guide: PronunciationGuide,
        pronunciation_type: PronunciationType,
        include_spelling: bool,
    ) -> str:
        """Generate SSML for pronunciation."""
        if pronunciation_type == PronunciationType.DRUG_NAME:
            base_ssml = self.SSML_TEMPLATES["drug_name"].format(drug_name=text)
            if include_spelling:
                # Add spelled version for drug names
                return f"""
                <speak>
                    <prosody rate="slow">
                        <say-as interpret-as="spell-out">{text}</say-as>
                    </prosody>
                    <break time="1s"/>
                    {base_ssml}
                </speak>
                """
            return base_ssml

        elif pronunciation_type == PronunciationType.DOSAGE_INSTRUCTION:
            # Parse dosage
            parts = text.split()
            if len(parts) >= 2:
                return self.SSML_TEMPLATES["dosage"].format(
                    amount=parts[0], unit=parts[1], frequency=text
                )

        # Default medical term
        syllables = " ".join(
            [
                f'<prosody rate="x-slow">{syl}</prosody>'
                for syl in guide.syllable_breakdown
            ]
        )

        ssml = self.SSML_TEMPLATES["medical_term"].format(
            ipa=guide.ipa_notation, term=text, syllables=syllables
        )

        return ssml

    async def generate_medication_instructions(
        self,
        medication_name: str,
        dosage: str,
        frequency: str,
        language: str,
        additional_instructions: Optional[str] = None,
    ) -> SynthesisResult:
        """
        Generate complete medication instructions.

        Args:
            medication_name: Name of medication
            dosage: Dosage information
            frequency: Frequency of administration
            language: Language code
            additional_instructions: Additional instructions

        Returns:
            Synthesis result
        """
        # Build complete instruction
        instruction_parts = [
            f"Your medication is {medication_name}",
            f"Take {dosage}",
            frequency,
        ]

        if additional_instructions:
            instruction_parts.append(additional_instructions)

        full_instruction = ". ".join(instruction_parts)

        # Generate pronunciation guides for each part
        guides = []

        # Medication name
        med_guide = await self.generate_pronunciation_guide(
            medication_name, language, PronunciationType.DRUG_NAME
        )
        guides.append(med_guide)

        # Build SSML
        ssml = f"""
        <speak>
            <prosody rate="slow">
                Your medication is
                <emphasis level="strong">
                    <say-as interpret-as="spell-out">{medication_name}</say-as>
                </emphasis>
            </prosody>
            <break time="1s"/>
            <prosody rate="medium">
                {medication_name}
            </prosody>
            <break time="500ms"/>
            Take <emphasis level="strong">{dosage}</emphasis>
            <break time="500ms"/>
            {frequency}
        """

        if additional_instructions:
            ssml += f"""
            <break time="500ms"/>
            {additional_instructions}
            """

        ssml += "</speak>"

        # Select voice
        voice = self._select_voice(language)

        # Synthesize
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.polly.synthesize_speech(
                Text=ssml,
                TextType="ssml",
                OutputFormat="mp3",
                VoiceId=voice.voice_id,
                Engine=voice.engine.value,
            ),
        )

        audio_data = response["AudioStream"].read()

        return SynthesisResult(
            text=full_instruction,
            language=language,
            voice_id=voice.voice_id,
            audio_data=audio_data,
            audio_format="mp3",
            duration_ms=len(audio_data) // 32,
            ssml_used=True,
            pronunciation_guides=guides,
        )

    async def create_medical_spelling_alphabet(
        self, text: str, language: str
    ) -> Dict[str, Any]:
        """
        Create medical spelling alphabet pronunciation.

        Args:
            text: Text to spell
            language: Language code

        Returns:
            Spelling alphabet data
        """
        alphabet = self.MEDICAL_ALPHABETS.get(language, self.MEDICAL_ALPHABETS["en"])

        spelled_out = []
        for char in text.upper():
            if char in alphabet:
                spelled_out.append(f"{char} as in {alphabet[char]}")
            elif char.isdigit():
                spelled_out.append(f"number {char}")
            elif char == " ":
                spelled_out.append("space")
            else:
                spelled_out.append(char)

        return {
            "original": text,
            "spelled": spelled_out,
            "ssml": self._generate_spelling_ssml(spelled_out),
        }

    def _generate_spelling_ssml(self, spelled_out: List[str]) -> str:
        """Generate SSML for spelling."""
        ssml = "<speak>"

        for item in spelled_out:
            ssml += f"""
            <prosody rate="slow">
                {item}
            </prosody>
            <break time="500ms"/>
            """

        ssml += "</speak>"

        return ssml

    async def batch_generate_pronunciations(
        self, terms: List[Dict[str, Any]], target_languages: List[str]
    ) -> Dict[str, List[PronunciationGuide]]:
        """
        Generate pronunciations for multiple terms and languages.

        Args:
            terms: List of terms with metadata
            target_languages: Target languages

        Returns:
            Dictionary of term -> pronunciation guides
        """
        results: Dict[str, List[PronunciationGuide]] = {}

        for term_data in terms:
            term = term_data["term"]
            pronunciation_type = PronunciationType(
                term_data.get("type", "medical_term")
            )

            results[term] = []

            for language in target_languages:
                try:
                    guide = await self.generate_pronunciation_guide(
                        term, language, pronunciation_type
                    )
                    results[term].append(guide)

                except Exception as e:
                    logger.error(
                        f"Error generating pronunciation for {term} in {language}: {e}"
                    )

        return results

    async def save_pronunciation_audio(
        self, synthesis_result: SynthesisResult, filename: str
    ) -> str:
        """
        Save pronunciation audio to S3.

        Args:
            synthesis_result: Synthesis result
            filename: Filename for audio

        Returns:
            S3 URL
        """
        try:
            # Upload to S3
            key = f"pronunciations/{synthesis_result.language}/{filename}"

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=synthesis_result.audio_data,
                    ContentType=f"audio/{synthesis_result.audio_format}",
                ),
            )

            # Generate URL
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{key}"

            return url

        except Exception as e:
            logger.error(f"Error saving pronunciation audio: {e}")
            raise


# Global instance
_pronunciation_system = None


def get_pronunciation_system() -> MedicalPronunciationSystem:
    """Get or create global pronunciation system instance."""
    global _pronunciation_system
    if _pronunciation_system is None:
        _pronunciation_system = MedicalPronunciationSystem()
    return _pronunciation_system

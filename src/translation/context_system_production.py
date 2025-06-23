"""Production-ready Translation Context System.

This module implements a database-backed translation context system
that replaces the placeholder implementation with real data storage.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import sessionmaker

from src.config import get_settings
from src.models.base import Base
from src.translation.context_system import MedicalContext, TranslationContext
from src.utils.logging import get_logger


class ValidationError(Exception):
    """Validation error for translation operations."""


logger = get_logger(__name__)
settings = get_settings()


class TranslationEntry(Base):
    """Database model for translation entries."""

    __tablename__ = "translation_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), nullable=False, index=True)
    language = Column(String(10), nullable=False, index=True)
    translation = Column(Text, nullable=False)
    domain = Column(String(50), default="general")
    context = Column(String(100))
    alternatives = Column(JSONB, default=list)
    usage_notes = Column(Text)
    medically_verified = Column(Boolean, default=False)
    verified_by = Column(String(255))
    verified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    entry_metadata = Column(JSONB, default=dict)


class TranslationCache(Base):
    """Database model for translation cache."""

    __tablename__ = "translation_cache_context"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cache_key = Column(String(500), nullable=False, unique=True, index=True)
    source_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    translated_text = Column(Text, nullable=False)
    confidence_score = Column(Float)
    provider = Column(String(50))  # bedrock, sagemaker, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    accessed_at = Column(DateTime, default=datetime.utcnow)
    access_count = Column(Integer, default=1)
    cache_metadata = Column(JSONB, default=dict)


class ProductionTranslationContextSystem:
    """Production implementation of translation context system with database backing."""

    def __init__(self) -> None:
        """Initialize with database connection."""
        # Create database engine
        self.engine = create_engine(
            settings.database_url, pool_size=20, max_overflow=40, pool_pre_ping=True
        )

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Load initial data if needed
        self._ensure_base_translations()

    def _ensure_base_translations(self) -> None:
        """Ensure base medical translations exist in database."""
        base_translations = {
            "medical.blood_pressure": {
                "en": "Blood Pressure",
                "es": "Presión Arterial",
                "fr": "Pression Artérielle",
                "ar": "ضغط الدم",
                "zh": "血压",
                "hi": "रक्तचाप",
                "pt": "Pressão Arterial",
                "ru": "Артериальное давление",
                "ja": "血圧",
                "de": "Blutdruck",
            },
            "medical.heart_rate": {
                "en": "Heart Rate",
                "es": "Frecuencia Cardíaca",
                "fr": "Fréquence Cardiaque",
                "ar": "معدل ضربات القلب",
                "zh": "心率",
                "hi": "हृदय गति",
                "pt": "Frequência Cardíaca",
                "ru": "Частота сердечных сокращений",
                "ja": "心拍数",
                "de": "Herzfrequenz",
            },
            "medical.temperature": {
                "en": "Temperature",
                "es": "Temperatura",
                "fr": "Température",
                "ar": "درجة الحرارة",
                "zh": "体温",
                "hi": "तापमान",
                "pt": "Temperatura",
                "ru": "Температура",
                "ja": "体温",
                "de": "Temperatur",
            },
            "medical.chest_pain": {
                "en": "Chest Pain",
                "es": "Dolor en el Pecho",
                "fr": "Douleur Thoracique",
                "ar": "ألم في الصدر",
                "zh": "胸痛",
                "hi": "सीने में दर्द",
                "pt": "Dor no Peito",
                "ru": "Боль в груди",
                "ja": "胸痛",
                "de": "Brustschmerzen",
            },
            "medical.diabetes": {
                "en": "Diabetes",
                "es": "Diabetes",
                "fr": "Diabète",
                "ar": "مرض السكري",
                "zh": "糖尿病",
                "hi": "मधुमेह",
                "pt": "Diabetes",
                "ru": "Диабет",
                "ja": "糖尿病",
                "de": "Diabetes",
            },
        }

        with self.SessionLocal() as session:
            for key, translations in base_translations.items():
                for language, translation in translations.items():
                    # Check if translation exists
                    existing = (
                        session.query(TranslationEntry)
                        .filter_by(key=key, language=language)
                        .first()
                    )

                    if not existing:
                        entry = TranslationEntry(
                            key=key,
                            language=language,
                            translation=translation,
                            domain="medical",
                            context="general",
                            medically_verified=True,
                            verified_by="system",
                            verified_at=datetime.utcnow(),
                            entry_metadata={
                                "source": "base_translations",
                                "version": "1.0",
                            },
                        )
                        session.add(entry)

            session.commit()

    def get_base_translation(self, key: str, language: str) -> str:
        """Get base translation from database."""
        with self.SessionLocal() as session:
            entry = (
                session.query(TranslationEntry)
                .filter_by(key=key, language=language)
                .first()
            )

            if entry:
                return str(entry.translation)

            # Fallback to key if not found
            logger.warning(
                f"Translation not found for key: {key}, language: {language}"
            )
            return key

    def get_alternatives(
        self, key: str, language: str, context: TranslationContext
    ) -> List[str]:
        """Get alternative translations from database."""
        with self.SessionLocal() as session:
            # Query for entries matching key and language
            entries = (
                session.query(TranslationEntry)
                .filter_by(key=key, language=language)
                .all()
            )

            alternatives = []

            for entry in entries:
                # Add main translation
                alternatives.append(str(entry.translation))

                # Add stored alternatives
                if entry.alternatives:
                    alternatives.extend(entry.alternatives)

                # For medical context, add patient-friendly versions
                if (
                    context.domain == "medical"
                    and context.specific_context == MedicalContext.SYMPTOMS.value
                ):
                    patient_friendly = self._make_patient_friendly(
                        str(entry.translation), language
                    )
                    if patient_friendly != str(entry.translation):
                        alternatives.append(patient_friendly)

            return list(set(alternatives))  # Remove duplicates

    def _make_patient_friendly(self, term: str, language: str) -> str:
        """Convert medical term to patient-friendly version."""
        # This would be enhanced with a comprehensive medical term mapping
        patient_friendly_mappings = {
            "en": {
                "hypertension": "high blood pressure",
                "hypotension": "low blood pressure",
                "tachycardia": "fast heart rate",
                "bradycardia": "slow heart rate",
                "dyspnea": "difficulty breathing",
                "pyrexia": "fever",
                "cephalalgia": "headache",
            },
            "es": {
                "hipertensión": "presión arterial alta",
                "hipotensión": "presión arterial baja",
                "taquicardia": "ritmo cardíaco rápido",
                "bradicardia": "ritmo cardíaco lento",
                "disnea": "dificultad para respirar",
                "pirexia": "fiebre",
                "cefalea": "dolor de cabeza",
            },
        }

        mappings = patient_friendly_mappings.get(language, {})
        lower_term = term.lower()

        for medical, friendly in mappings.items():
            if medical in lower_term:
                return term.replace(medical, friendly)

        return term

    def get_usage_notes(self, key: str, context: TranslationContext) -> Optional[str]:
        """Get usage notes from database."""
        with self.SessionLocal() as session:
            entry = (
                session.query(TranslationEntry)
                .filter_by(key=key, context=context.specific_context)
                .first()
            )

            if entry and entry.usage_notes:
                return str(entry.usage_notes)

            # Check for general notes
            general_entry = (
                session.query(TranslationEntry)
                .filter_by(key=key, context="general")
                .first()
            )

            return (
                str(general_entry.usage_notes)
                if general_entry and general_entry.usage_notes
                else None
            )

    def is_medically_verified(self, key: str) -> bool:
        """Check medical verification status from database."""
        with self.SessionLocal() as session:
            entry = (
                session.query(TranslationEntry)
                .filter_by(key=key, medically_verified=True)
                .first()
            )

            return entry is not None

    def add_translation_entry(
        self,
        key: str,
        language: str,
        translation: str,
        domain: str = "general",
        context: Optional[str] = None,
        alternatives: Optional[List[str]] = None,
        usage_notes: Optional[str] = None,
        medically_verified: bool = False,
        verified_by: Optional[str] = None,
    ) -> bool:
        """Add new translation entry to database."""
        try:
            with self.SessionLocal() as session:
                entry = TranslationEntry(
                    key=key,
                    language=language,
                    translation=translation,
                    domain=domain,
                    context=context,
                    alternatives=alternatives or [],
                    usage_notes=usage_notes,
                    medically_verified=medically_verified,
                    verified_by=verified_by,
                    verified_at=datetime.utcnow() if medically_verified else None,
                )
                session.add(entry)
                session.commit()

                logger.info(f"Added translation entry: {key} ({language})")
                return True

        except (TypeError, ValueError) as e:
            logger.error(f"Error adding translation entry: {e}")
            return False

    def cache_translation(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        translated_text: str,
        confidence_score: Optional[float] = None,
        provider: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Cache a translation result."""
        try:
            # Generate cache key
            cache_key = f"{source_language}:{target_language}:{hash(source_text)}"

            with self.SessionLocal() as session:
                # Check if exists
                existing = (
                    session.query(TranslationCache)
                    .filter_by(cache_key=cache_key)
                    .first()
                )

                if existing:
                    # Update access info
                    existing.accessed_at = datetime.utcnow()
                    existing.access_count = (existing.access_count or 0) + 1
                else:
                    # Create new cache entry
                    cache_entry = TranslationCache(
                        cache_key=cache_key,
                        source_text=source_text,
                        source_language=source_language,
                        target_language=target_language,
                        translated_text=translated_text,
                        confidence_score=confidence_score,
                        provider=provider,
                        metadata=metadata or {},
                    )
                    session.add(cache_entry)

                session.commit()
                return True

        except (TypeError, ValueError) as e:
            logger.error(f"Error caching translation: {e}")
            return False

    def get_cached_translation(
        self, source_text: str, source_language: str, target_language: str
    ) -> Optional[Tuple[str, float]]:
        """Get cached translation if available."""
        try:
            cache_key = f"{source_language}:{target_language}:{hash(source_text)}"

            with self.SessionLocal() as session:
                cache_entry = (
                    session.query(TranslationCache)
                    .filter_by(cache_key=cache_key)
                    .first()
                )

                if cache_entry:
                    # Update access info
                    cache_entry.accessed_at = datetime.utcnow()
                    cache_entry.access_count = (cache_entry.access_count or 0) + 1
                    session.commit()

                    return (
                        str(cache_entry.translated_text),
                        float(cache_entry.confidence_score or 1.0),
                    )

                return None

        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error retrieving cached translation: {e}")
            return None

    def validate_medical_translation(
        self, key: str, translation: str, language: str, context: MedicalContext
    ) -> Tuple[bool, List[str]]:
        """Validate medical translation accuracy."""
        issues = []

        with self.SessionLocal() as session:
            # Get reference translation
            reference = (
                session.query(TranslationEntry)
                .filter_by(key=key, language=language, medically_verified=True)
                .first()
            )

            if not reference:
                issues.append(f"No verified reference translation found for {key}")
                return False, issues

            # Basic validation checks
            if translation.lower() == reference.translation.lower():
                return True, []

            # Check if it's an acceptable alternative
            if reference.alternatives and translation in reference.alternatives:
                return True, []

            # Check for critical medical terms that must be present
            critical_terms = {
                "en": ["pressure", "rate", "pain", "temperature"],
                "es": ["presión", "frecuencia", "dolor", "temperatura"],
                "fr": ["pression", "fréquence", "douleur", "température"],
            }

            lang_terms = critical_terms.get(language, [])
            ref_lower = reference.translation.lower()
            trans_lower = translation.lower()

            for term in lang_terms:
                if term in ref_lower and term not in trans_lower:
                    issues.append(f"Missing critical term: {term}")

            # Context-specific validation
            if context == MedicalContext.EMERGENCY.value:
                # Emergency translations must be clear and unambiguous
                if len(translation) > len(reference.translation) * 1.5:
                    issues.append("Translation too verbose for emergency context")

            return len(issues) == 0, issues

    def get_translations_by_domain(
        self, domain: str, language: str, limit: int = 100
    ) -> List[Dict[str, str]]:
        """Get all translations for a specific domain."""
        with self.SessionLocal() as session:
            entries = (
                session.query(TranslationEntry)
                .filter_by(domain=domain, language=language)
                .limit(limit)
                .all()
            )

            return [
                {
                    "key": str(entry.key),
                    "translation": str(entry.translation),
                    "context": str(entry.context or ""),
                    "verified": str(entry.medically_verified),
                }
                for entry in entries
            ]

    def export_translations(self, output_path: Path) -> bool:
        """Export all translations to JSON file."""
        try:
            with self.SessionLocal() as session:
                all_entries = session.query(TranslationEntry).all()

                export_data: Dict[str, Dict[str, Any]] = {}
                for entry in all_entries:
                    key_str = str(entry.key)
                    lang_str = str(entry.language)

                    if key_str not in export_data:
                        export_data[key_str] = {}

                    export_data[key_str][lang_str] = {
                        "translation": str(entry.translation),
                        "domain": str(entry.domain),
                        "context": str(entry.context) if entry.context else None,
                        "alternatives": entry.alternatives,
                        "verified": bool(entry.medically_verified),
                        "usage_notes": (
                            str(entry.usage_notes) if entry.usage_notes else None
                        ),
                    }

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)

                logger.info(
                    f"Exported {len(export_data)} translation keys to {output_path}"
                )
                return True

        except (OSError, TypeError, ValueError) as e:
            logger.error(f"Error exporting translations: {e}")
            return False

    def import_translations(self, input_path: Path) -> bool:
        """Import translations from JSON file."""
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)

            imported_count = 0
            with self.SessionLocal() as session:
                for key, languages in import_data.items():
                    for language, data in languages.items():
                        # Check if exists
                        existing = (
                            session.query(TranslationEntry)
                            .filter_by(key=key, language=language)
                            .first()
                        )

                        if not existing:
                            entry = TranslationEntry(
                                key=key,
                                language=language,
                                translation=data.get("translation"),
                                domain=data.get("domain", "general"),
                                context=data.get("context"),
                                alternatives=data.get("alternatives", []),
                                usage_notes=data.get("usage_notes"),
                                medically_verified=data.get("verified", False),
                                verified_by="import" if data.get("verified") else None,
                                verified_at=(
                                    datetime.utcnow() if data.get("verified") else None
                                ),
                            )
                            session.add(entry)
                            imported_count += 1

                session.commit()

            logger.info(f"Imported {imported_count} new translations from {input_path}")
            return True

        except (TypeError, ValueError) as e:
            logger.error(f"Error importing translations: {e}")
            return False


# Create global instance
translation_context_system = ProductionTranslationContextSystem()

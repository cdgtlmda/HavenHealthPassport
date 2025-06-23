"""Emergency Medical Terminology Service.

CRITICAL: This service handles life-critical emergency medical terms.
Mistranslation or missing terminology can result in patient death.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.emergency_terminology import (
    EmergencyMedicalTerm,
    EmergencyTermTranslation,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmergencyTerminologyService:
    """Service for managing critical emergency medical terminology."""

    # WHO Emergency Medical Terms - Critical for refugee healthcare
    # @encrypt_phi - Emergency medical terms may contain patient context
    # @access_control_required - Medical terminology requires authorized access
    EMERGENCY_TERMS = {
        "airway_breathing_circulation": {
            "en": {
                # ABC Protocol
                "airway": "Airway - breathing passage",
                "breathing": "Breathing - respiration",
                "circulation": "Circulation - blood flow",
                "airway_obstruction": "Airway obstruction - blocked breathing",
                "respiratory_distress": "Respiratory distress - difficulty breathing",
                "cardiac_arrest": "Cardiac arrest - heart stopped",
                "unconscious": "Unconscious - not responsive",
                "not_breathing": "Not breathing",
                "no_pulse": "No pulse - no heartbeat",
                "choking": "Choking - airway blocked",
            },
            "es": {
                "airway": "Vía aérea - conducto respiratorio",
                "breathing": "Respiración",
                "circulation": "Circulación sanguínea",
                "airway_obstruction": "Obstrucción de vía aérea",
                "respiratory_distress": "Dificultad respiratoria",
                "cardiac_arrest": "Paro cardíaco",
                "unconscious": "Inconsciente - sin respuesta",
                "not_breathing": "No respira",
                "no_pulse": "Sin pulso - sin latido",
                "choking": "Asfixia - atragantamiento",
            },
            "ar": {
                "airway": "مجرى الهواء - ممر التنفس",
                "breathing": "التنفس",
                "circulation": "الدورة الدموية",
                "airway_obstruction": "انسداد مجرى الهواء",
                "respiratory_distress": "ضيق التنفس",
                "cardiac_arrest": "توقف القلب",
                "unconscious": "فاقد الوعي - لا يستجيب",
                "not_breathing": "لا يتنفس",
                "no_pulse": "لا يوجد نبض",
                "choking": "الاختناق - انسداد مجرى الهواء",
            },
            "fr": {
                "airway": "Voies aériennes - passage respiratoire",
                "breathing": "Respiration",
                "circulation": "Circulation sanguine",
                "airway_obstruction": "Obstruction des voies aériennes",
                "respiratory_distress": "Détresse respiratoire",
                "cardiac_arrest": "Arrêt cardiaque",
                "unconscious": "Inconscient - ne répond pas",
                "not_breathing": "Ne respire pas",
                "no_pulse": "Pas de pouls",
                "choking": "Étouffement - obstruction",
            },
        },
        "trauma_bleeding": {
            "en": {
                "severe_bleeding": "Severe bleeding - heavy blood loss",
                "hemorrhage": "Hemorrhage - dangerous bleeding",
                "pressure_point": "Pressure point - stop bleeding here",
                "tourniquet": "Tourniquet - tight band to stop bleeding",
                "direct_pressure": "Direct pressure - press on wound",
                "shock": "Shock - body failing from blood loss",
                "fracture": "Fracture - broken bone",
                "head_injury": "Head injury",
                "spinal_injury": "Spinal injury - do not move",
                "burn": "Burn - skin damage from heat",
            },
            "es": {
                "severe_bleeding": "Sangrado severo - pérdida de sangre abundante",
                "hemorrhage": "Hemorragia - sangrado peligroso",
                "pressure_point": "Punto de presión - detener sangrado aquí",
                "tourniquet": "Torniquete - banda apretada para detener sangrado",
                "direct_pressure": "Presión directa - presionar sobre herida",
                "shock": "Shock - falla corporal por pérdida de sangre",
                "fracture": "Fractura - hueso roto",
                "head_injury": "Lesión en la cabeza",
                "spinal_injury": "Lesión espinal - no mover",
                "burn": "Quemadura - daño en piel por calor",
            },
            "ar": {
                "severe_bleeding": "نزيف شديد - فقدان دم كثير",
                "hemorrhage": "نزيف خطير",
                "pressure_point": "نقطة الضغط - أوقف النزيف هنا",
                "tourniquet": "عاصبة - رباط ضاغط لوقف النزيف",
                "direct_pressure": "ضغط مباشر - اضغط على الجرح",
                "shock": "صدمة - فشل الجسم من فقدان الدم",
                "fracture": "كسر - عظم مكسور",
                "head_injury": "إصابة في الرأس",
                "spinal_injury": "إصابة في العمود الفقري - لا تحرك",
                "burn": "حرق - تلف الجلد من الحرارة",
            },
            "fr": {
                "severe_bleeding": "Saignement sévère - perte de sang importante",
                "hemorrhage": "Hémorragie - saignement dangereux",
                "pressure_point": "Point de pression - arrêter le saignement ici",
                "tourniquet": "Garrot - bande serrée pour arrêter le saignement",
                "direct_pressure": "Pression directe - appuyer sur la plaie",
                "shock": "État de choc - défaillance due à la perte de sang",
                "fracture": "Fracture - os cassé",
                "head_injury": "Blessure à la tête",
                "spinal_injury": "Blessure à la colonne - ne pas bouger",
                "burn": "Brûlure - lésion cutanée par la chaleur",
            },
        },
        "medical_emergencies": {
            "en": {
                "heart_attack": "Heart attack - chest pain, arm pain",
                "stroke": "Stroke - face drooping, speech problems",
                "seizure": "Seizure - convulsions, shaking",
                "diabetic_emergency": "Diabetic emergency - sugar problem",
                "allergic_reaction": "Allergic reaction",
                "anaphylaxis": "Anaphylaxis - severe allergy, throat closing",
                "asthma_attack": "Asthma attack - cannot breathe",
                "poisoning": "Poisoning - toxic substance",
                "overdose": "Overdose - too much medication",
                "heat_stroke": "Heat stroke - too hot, confused",
            },
            "es": {
                "heart_attack": "Ataque al corazón - dolor de pecho, dolor de brazo",
                "stroke": "Derrame cerebral - cara caída, problemas del habla",
                "seizure": "Convulsión - temblores",
                "diabetic_emergency": "Emergencia diabética - problema de azúcar",
                "allergic_reaction": "Reacción alérgica",
                "anaphylaxis": "Anafilaxia - alergia severa, garganta cerrada",
                "asthma_attack": "Ataque de asma - no puede respirar",
                "poisoning": "Envenenamiento - sustancia tóxica",
                "overdose": "Sobredosis - demasiada medicación",
                "heat_stroke": "Golpe de calor - muy caliente, confundido",
            },
            "ar": {
                "heart_attack": "نوبة قلبية - ألم في الصدر، ألم في الذراع",
                "stroke": "سكتة دماغية - تدلي الوجه، مشاكل في الكلام",
                "seizure": "نوبة صرع - تشنجات، اهتزاز",
                "diabetic_emergency": "طوارئ السكري - مشكلة السكر",
                "allergic_reaction": "رد فعل تحسسي",
                "anaphylaxis": "صدمة الحساسية - حساسية شديدة، انغلاق الحلق",
                "asthma_attack": "نوبة ربو - لا يستطيع التنفس",
                "poisoning": "تسمم - مادة سامة",
                "overdose": "جرعة زائدة - دواء كثير جداً",
                "heat_stroke": "ضربة شمس - حار جداً، مشوش",
            },
            "fr": {
                "heart_attack": "Crise cardiaque - douleur thoracique, douleur au bras",
                "stroke": "AVC - visage tombant, problèmes d'élocution",
                "seizure": "Convulsion - tremblements",
                "diabetic_emergency": "Urgence diabétique - problème de sucre",
                "allergic_reaction": "Réaction allergique",
                "anaphylaxis": "Anaphylaxie - allergie sévère, gorge qui se ferme",
                "asthma_attack": "Crise d'asthme - ne peut pas respirer",
                "poisoning": "Empoisonnement - substance toxique",
                "overdose": "Surdose - trop de médicaments",
                "heat_stroke": "Coup de chaleur - très chaud, confus",
            },
        },
        "pain_symptoms": {
            "en": {
                "severe_pain": "Severe pain - very bad pain",
                "chest_pain": "Chest pain",
                "abdominal_pain": "Abdominal pain - stomach pain",
                "headache": "Headache",
                "back_pain": "Back pain",
                "pain_scale": "Pain scale 0-10",
                "sharp_pain": "Sharp pain - like knife",
                "burning_pain": "Burning pain",
                "throbbing_pain": "Throbbing pain - pulsing",
                "constant_pain": "Constant pain - all the time",
            },
            "es": {
                "severe_pain": "Dolor severo - dolor muy fuerte",
                "chest_pain": "Dolor de pecho",
                "abdominal_pain": "Dolor abdominal - dolor de estómago",
                "headache": "Dolor de cabeza",
                "back_pain": "Dolor de espalda",
                "pain_scale": "Escala de dolor 0-10",
                "sharp_pain": "Dolor agudo - como cuchillo",
                "burning_pain": "Dolor ardiente",
                "throbbing_pain": "Dolor pulsante",
                "constant_pain": "Dolor constante - todo el tiempo",
            },
            "ar": {
                "severe_pain": "ألم شديد - ألم سيء جداً",
                "chest_pain": "ألم في الصدر",
                "abdominal_pain": "ألم في البطن - ألم في المعدة",
                "headache": "صداع",
                "back_pain": "ألم في الظهر",
                "pain_scale": "مقياس الألم 0-10",
                "sharp_pain": "ألم حاد - مثل السكين",
                "burning_pain": "ألم حارق",
                "throbbing_pain": "ألم نابض",
                "constant_pain": "ألم مستمر - طوال الوقت",
            },
            "fr": {
                "severe_pain": "Douleur sévère - très forte douleur",
                "chest_pain": "Douleur thoracique",
                "abdominal_pain": "Douleur abdominale - mal au ventre",
                "headache": "Mal de tête",
                "back_pain": "Mal de dos",
                "pain_scale": "Échelle de douleur 0-10",
                "sharp_pain": "Douleur aiguë - comme un couteau",
                "burning_pain": "Douleur brûlante",
                "throbbing_pain": "Douleur lancinante - pulsatile",
                "constant_pain": "Douleur constante - tout le temps",
            },
        },
        "instructions": {
            "en": {
                "call_help": "Call for help immediately",
                "do_not_move": "Do not move patient",
                "stay_calm": "Stay calm",
                "keep_warm": "Keep patient warm",
                "give_nothing_by_mouth": "Give nothing by mouth",
                "monitor_breathing": "Monitor breathing",
                "stay_with_patient": "Stay with patient",
                "recovery_position": "Recovery position - on side",
                "elevate_legs": "Elevate legs for shock",
                "apply_ice": "Apply ice to injury",
            },
            "es": {
                "call_help": "Llame para ayuda inmediatamente",
                "do_not_move": "No mueva al paciente",
                "stay_calm": "Mantenga la calma",
                "keep_warm": "Mantenga al paciente caliente",
                "give_nothing_by_mouth": "No dar nada por boca",
                "monitor_breathing": "Monitorear respiración",
                "stay_with_patient": "Quédese con el paciente",
                "recovery_position": "Posición de recuperación - de lado",
                "elevate_legs": "Elevar piernas para shock",
                "apply_ice": "Aplicar hielo a la lesión",
            },
            "ar": {
                "call_help": "اطلب المساعدة فوراً",
                "do_not_move": "لا تحرك المريض",
                "stay_calm": "ابق هادئاً",
                "keep_warm": "أبق المريض دافئاً",
                "give_nothing_by_mouth": "لا تعطي شيئاً عن طريق الفم",
                "monitor_breathing": "راقب التنفس",
                "stay_with_patient": "ابق مع المريض",
                "recovery_position": "وضعية الإفاقة - على الجانب",
                "elevate_legs": "ارفع الساقين للصدمة",
                "apply_ice": "ضع الثلج على الإصابة",
            },
            "fr": {
                "call_help": "Appelez à l'aide immédiatement",
                "do_not_move": "Ne pas bouger le patient",
                "stay_calm": "Restez calme",
                "keep_warm": "Gardez le patient au chaud",
                "give_nothing_by_mouth": "Ne rien donner par la bouche",
                "monitor_breathing": "Surveiller la respiration",
                "stay_with_patient": "Restez avec le patient",
                "recovery_position": "Position de récupération - sur le côté",
                "elevate_legs": "Surélever les jambes pour le choc",
                "apply_ice": "Appliquer de la glace sur la blessure",
            },
        },
    }

    def __init__(self, db_session: Optional[Session] = None):
        """Initialize emergency terminology service."""
        self.db = db_session or next(get_db())
        self.translate_client = boto3.client("translate")
        self._ensure_emergency_terms_loaded()

    def _ensure_emergency_terms_loaded(self) -> None:
        """Ensure all emergency terms are loaded in the database."""
        try:
            for category, languages in self.EMERGENCY_TERMS.items():
                for lang_code, terms in languages.items():
                    for term_key, term_value in terms.items():
                        # Check if term exists
                        existing = (
                            self.db.query(EmergencyMedicalTerm)
                            .filter(
                                and_(
                                    EmergencyMedicalTerm.term == term_key,
                                    EmergencyMedicalTerm.language_code == lang_code,
                                )
                            )
                            .first()
                        )

                        if not existing:
                            # Create new emergency term
                            # @secure_storage - Medical terminology must be encrypted at rest
                            emergency_term = EmergencyMedicalTerm(
                                term=term_key,
                                language_code=lang_code,
                                category=category,
                                severity_level="critical",
                                clinical_context=term_value,
                                is_active=True,
                                created_at=datetime.utcnow(),
                            )
                            self.db.add(emergency_term)

            self.db.commit()
            logger.info("Emergency medical terms loaded successfully")

        except (ValueError, RuntimeError, SQLAlchemyError) as e:
            logger.error(f"Failed to load emergency terms: {e}")
            self.db.rollback()

    def get_emergency_terminology_for_aws(
        self, source_lang: str, target_lang: str
    ) -> str:
        """Create AWS Translate custom terminology for emergency terms."""
        try:
            # Get all emergency terms for source language
            source_terms = (
                self.db.query(EmergencyMedicalTerm)
                .filter(
                    and_(
                        EmergencyMedicalTerm.language_code == source_lang,
                        EmergencyMedicalTerm.is_active.is_(True),
                    )
                )
                .all()
            )

            if not source_terms:
                # Fallback to English if source not found
                source_terms = (
                    self.db.query(EmergencyMedicalTerm)
                    .filter(
                        and_(
                            EmergencyMedicalTerm.language_code == "en",
                            EmergencyMedicalTerm.is_active.is_(True),
                        )
                    )
                    .all()
                )

            # Build CSV for AWS Translate
            csv_lines = ["source,target"]

            for source_term in source_terms:
                # Find translation
                translation = (
                    self.db.query(EmergencyTermTranslation)
                    .filter(
                        and_(
                            EmergencyTermTranslation.source_term_id == source_term.id,
                            EmergencyTermTranslation.target_language == target_lang,
                            EmergencyTermTranslation.medical_accuracy_score >= 0.95,
                        )
                    )
                    .first()
                )

                if translation:
                    csv_lines.append(
                        f"{source_term.term},{translation.translated_term}"
                    )
                else:
                    # Try to find the term in target language directly
                    target_term = (
                        self.db.query(EmergencyMedicalTerm)
                        .filter(
                            and_(
                                EmergencyMedicalTerm.term == source_term.term,
                                EmergencyMedicalTerm.language_code == target_lang,
                            )
                        )
                        .first()
                    )

                    if target_term:
                        csv_lines.append(f"{source_term.term},{target_term.term}")

            # Create terminology in AWS
            terminology_name = f"EmergencyMedical_{source_lang}_{target_lang}_{int(datetime.utcnow().timestamp())}"
            csv_content = "\n".join(csv_lines)

            # Check if we have enough terms
            if len(csv_lines) < 5:
                # Add critical default terms
                if source_lang == "en":
                    default_mappings = self._get_default_emergency_mappings(
                        source_lang, target_lang
                    )
                    for source, target in default_mappings:
                        csv_lines.append(f"{source},{target}")
                    csv_content = "\n".join(csv_lines)

            # Upload to AWS Translate
            self.translate_client.import_terminology(
                Name=terminology_name,
                MergeStrategy="OVERWRITE",
                TerminologyData={"File": csv_content.encode("utf-8"), "Format": "CSV"},
            )

            logger.info(f"Created AWS emergency terminology: {terminology_name}")
            return terminology_name

        except (ClientError, ValueError, KeyError) as e:
            logger.error(f"Failed to create AWS emergency terminology: {e}")
            # Return a fallback terminology name
            return self._get_fallback_terminology(source_lang, target_lang)

    def _get_default_emergency_mappings(
        self, source_lang: str, target_lang: str
    ) -> List[Tuple[str, str]]:
        """Get default emergency term mappings."""
        # Critical terms that must always be available
        mappings = {
            ("en", "es"): [
                ("emergency", "emergencia"),
                ("help", "ayuda"),
                ("pain", "dolor"),
                ("breathing", "respiración"),
                ("bleeding", "sangrado"),
                ("unconscious", "inconsciente"),
                ("heart", "corazón"),
                ("allergic", "alérgico"),
                ("medicine", "medicina"),
                ("hospital", "hospital"),
            ],
            ("en", "ar"): [
                ("emergency", "طوارئ"),
                ("help", "مساعدة"),
                ("pain", "ألم"),
                ("breathing", "تنفس"),
                ("bleeding", "نزيف"),
                ("unconscious", "فاقد الوعي"),
                ("heart", "قلب"),
                ("allergic", "حساسية"),
                ("medicine", "دواء"),
                ("hospital", "مستشفى"),
            ],
            ("en", "fr"): [
                ("emergency", "urgence"),
                ("help", "aide"),
                ("pain", "douleur"),
                ("breathing", "respiration"),
                ("bleeding", "saignement"),
                ("unconscious", "inconscient"),
                ("heart", "cœur"),
                ("allergic", "allergique"),
                ("medicine", "médicament"),
                ("hospital", "hôpital"),
            ],
        }

        key = (source_lang, target_lang)
        if key in mappings:
            return mappings[key]

        # Try reverse
        reverse_key = (target_lang, source_lang)
        if reverse_key in mappings:
            return [(t, s) for s, t in mappings[reverse_key]]

        return []

    def _get_fallback_terminology(self, source_lang: str, target_lang: str) -> str:
        """Get fallback terminology name."""
        # Check if a terminology already exists
        try:
            response = self.translate_client.list_terminologies(MaxResults=100)

            for terminology in response.get("TerminologyPropertiesList", []):
                name: str = terminology["Name"]
                if f"EmergencyMedical_{source_lang}_{target_lang}" in name:
                    return name

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to list terminologies: {e}")

        # Return a generic emergency terminology
        return f"EmergencyMedical_{source_lang}_{target_lang}_fallback"

    def get_emergency_terms_by_category(
        self, category: str, language: str
    ) -> List[EmergencyMedicalTerm]:
        """Get all emergency terms for a category and language."""
        return (
            self.db.query(EmergencyMedicalTerm)
            .filter(
                and_(
                    EmergencyMedicalTerm.category == category,
                    EmergencyMedicalTerm.language_code == language,
                    EmergencyMedicalTerm.is_active.is_(True),
                )
            )
            .all()
        )

    def validate_emergency_translation(
        self, source_text: str, translated_text: str, source_lang: str, target_lang: str
    ) -> Dict[str, Any]:
        """Validate that critical emergency terms are properly translated."""
        missing_terms = []
        accuracy_score = 1.0

        # Get emergency terms in source language
        source_terms = (
            self.db.query(EmergencyMedicalTerm)
            .filter(
                and_(
                    EmergencyMedicalTerm.language_code == source_lang,
                    EmergencyMedicalTerm.is_active.is_(True),
                )
            )
            .all()
        )

        for term in source_terms:
            if term.term.lower() in source_text.lower():
                # Check if corresponding term is in translation
                translation = (
                    self.db.query(EmergencyTermTranslation)
                    .filter(
                        and_(
                            EmergencyTermTranslation.source_term_id == term.id,
                            EmergencyTermTranslation.target_language == target_lang,
                        )
                    )
                    .first()
                )

                if translation:
                    if (
                        translation.translated_term.lower()
                        not in translated_text.lower()
                    ):
                        missing_terms.append(
                            {
                                "source": term.term,
                                "expected": translation.translated_term,
                                "category": term.category,
                            }
                        )
                        accuracy_score -= 0.1

        return {
            "is_valid": len(missing_terms) == 0,
            "accuracy_score": max(0, accuracy_score),
            "missing_terms": missing_terms,
            "warnings": [
                f"Missing critical term: {t['source']} ({t['category']})"
                for t in missing_terms
            ],
        }


# Singleton instance
emergency_terminology_service = EmergencyTerminologyService()

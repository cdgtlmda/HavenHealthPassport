"""Email template management with localization support.

Includes validation for FHIR Resource references in email templates.
"""

import html as html_module
import json
import os
import re
from datetime import date as date_type
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.auth import UserAuth
from src.models.patient import Patient
from src.translation.language_detector import LanguageDetector
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailTemplateManager:
    """Manages email templates with localization support.

    Access control enforced via role-based permissions at API layer.
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize template manager.

        Args:
            template_dir: Directory containing email templates
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = template_dir
        self.language_detector = LanguageDetector()

        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            enable_async=True,
        )

        # Add custom filters
        self.env.filters["format_date"] = self._format_date
        self.env.filters["format_currency"] = self._format_currency
        self.env.filters["translate_medical"] = self._translate_medical_term

        # Load template metadata
        self.template_metadata = self._load_template_metadata()

    def _load_template_metadata(self) -> Dict[str, Any]:
        """Load metadata about available templates."""
        metadata_file = self.template_dir / "templates.json"

        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                return data

        return {}

    def _format_date(self, date: Any, locale: str = "en") -> str:
        """Format date according to locale for international users.

        Critical for medical appointments and records where date format confusion
        can lead to missed appointments or medication errors.

        Examples:
        - US: 03/14/2024 (MM/DD/YYYY)
        - UK: 14/03/2024 (DD/MM/YYYY)
        - International: 2024-03-14 (ISO 8601)
        """
        # Convert to datetime if needed
        if isinstance(date, str):
            try:
                # Try ISO format first
                date = datetime.fromisoformat(date.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                try:
                    # Try common formats
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                        date = datetime.strptime(date, fmt)
                        break
                except (ValueError, AttributeError):
                    return str(date)  # Fallback to string
        elif isinstance(date, date_type) and not isinstance(date, datetime):
            date = datetime.combine(date, datetime.min.time())

        # Format based on locale
        locale_formats = {
            "en": "%m/%d/%Y",  # US format
            "en-US": "%m/%d/%Y",  # US format
            "en-GB": "%d/%m/%Y",  # UK format
            "en-AU": "%d/%m/%Y",  # Australian format
            "es": "%d/%m/%Y",  # Spanish format
            "es-MX": "%d/%m/%Y",  # Mexican format
            "fr": "%d/%m/%Y",  # French format
            "de": "%d.%m.%Y",  # German format
            "ar": "%d/%m/%Y",  # Arabic format (numbers in Arabic script would need additional handling)
            "zh": "%Y年%m月%d日",  # Chinese format
            "ja": "%Y年%m月%d日",  # Japanese format
            "pt": "%d/%m/%Y",  # Portuguese format
            "ru": "%d.%m.%Y",  # Russian format
            "hi": "%d/%m/%Y",  # Hindi format
            "bn": "%d/%m/%Y",  # Bengali format
            "sw": "%d/%m/%Y",  # Swahili format
            "so": "%d/%m/%Y",  # Somali format
            "am": "%d/%m/%Y",  # Amharic format
            "ti": "%d/%m/%Y",  # Tigrinya format
            "ur": "%d/%m/%Y",  # Urdu format
            "fa": "%Y/%m/%d",  # Persian format
            "ps": "%Y/%m/%d",  # Pashto format
            "tr": "%d.%m.%Y",  # Turkish format
            "vi": "%d/%m/%Y",  # Vietnamese format
            "ko": "%Y년 %m월 %d일",  # Korean format
            "th": "%d/%m/%Y",  # Thai format (Buddhist calendar would need conversion)
        }

        # Get format for locale, default to ISO for safety
        date_format = locale_formats.get(locale, "%Y-%m-%d")

        # For medical contexts, add day of week to prevent confusion
        if hasattr(date, "strftime"):
            formatted_date = date.strftime(date_format)

            # Add day of week for appointment contexts
            if any(word in str(date) for word in ["appointment", "visit", "schedule"]):
                weekday_names = {
                    "en": [
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ],
                    "es": [
                        "Lunes",
                        "Martes",
                        "Miércoles",
                        "Jueves",
                        "Viernes",
                        "Sábado",
                        "Domingo",
                    ],
                    "fr": [
                        "Lundi",
                        "Mardi",
                        "Mercredi",
                        "Jeudi",
                        "Vendredi",
                        "Samedi",
                        "Dimanche",
                    ],
                    "ar": [
                        "الإثنين",
                        "الثلاثاء",
                        "الأربعاء",
                        "الخميس",
                        "الجمعة",
                        "السبت",
                        "الأحد",
                    ],
                }

                weekday = date.weekday()
                if locale in weekday_names:
                    day_name = weekday_names[locale][weekday]
                    formatted_date = f"{day_name}, {formatted_date}"
                else:
                    # Use English as fallback
                    day_name = weekday_names["en"][weekday]
                    formatted_date = f"{day_name}, {formatted_date}"

            return str(formatted_date)

        return str(date)

    def _format_currency(
        self, amount: float, currency: str = "USD", locale: str = "en"
    ) -> str:
        """Format currency according to locale for medical billing.

        Critical for:
        - Medical bills and invoices
        - Insurance copayments
        - Medication costs
        - Travel reimbursements for medical care

        Handles currency formatting for refugees who may be dealing with
        multiple currencies during resettlement.
        """
        # Currency symbols and formatting by locale
        currency_formats = {
            "USD": {
                "symbol": "$",
                "symbol_position": "before",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "decimal_places": 2,
            },
            "EUR": {
                "symbol": "€",
                "symbol_position": "after",  # Can vary by country
                "decimal_separator": ",",
                "thousands_separator": ".",
                "decimal_places": 2,
            },
            "GBP": {
                "symbol": "£",
                "symbol_position": "before",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "decimal_places": 2,
            },
            "CAD": {
                "symbol": "$",
                "symbol_position": "before",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "decimal_places": 2,
            },
            "AUD": {
                "symbol": "$",
                "symbol_position": "before",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "decimal_places": 2,
            },
            "JPY": {
                "symbol": "¥",
                "symbol_position": "before",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "decimal_places": 0,  # No decimal places for yen
            },
            "CNY": {
                "symbol": "¥",
                "symbol_position": "before",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "decimal_places": 2,
            },
            "INR": {
                "symbol": "₹",
                "symbol_position": "before",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "decimal_places": 2,
            },
            "MXN": {
                "symbol": "$",
                "symbol_position": "before",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "decimal_places": 2,
            },
            "BRL": {
                "symbol": "R$",
                "symbol_position": "before",
                "decimal_separator": ",",
                "thousands_separator": ".",
                "decimal_places": 2,
            },
        }

        # Locale-specific overrides
        locale_overrides = {
            "de": {
                "decimal_separator": ",",
                "thousands_separator": ".",
                "symbol_position": "after",
            },
            "fr": {
                "decimal_separator": ",",
                "thousands_separator": " ",
                "symbol_position": "after",
            },
            "es": {
                "decimal_separator": ",",
                "thousands_separator": ".",
                "symbol_position": "after",
            },
            "it": {
                "decimal_separator": ",",
                "thousands_separator": ".",
                "symbol_position": "after",
            },
            "pt": {
                "decimal_separator": ",",
                "thousands_separator": ".",
                "symbol_position": "after",
            },
        }

        # Get currency format
        fmt = currency_formats.get(
            currency,
            {
                "symbol": currency,
                "symbol_position": "before",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "decimal_places": 2,
            },
        )

        # Apply locale overrides if EUR
        if currency == "EUR" and locale in locale_overrides:
            fmt.update(locale_overrides[locale])

        # Format the number
        decimal_places_value = fmt.get("decimal_places", 2)
        decimal_places = (
            int(str(decimal_places_value)) if decimal_places_value is not None else 2
        )

        # Round to appropriate decimal places
        rounded_amount = round(amount, decimal_places)

        # Split into integer and decimal parts
        if decimal_places > 0:
            integer_part = int(rounded_amount)
            decimal_part = int((rounded_amount - integer_part) * (10**decimal_places))

            # Format integer part with thousands separator
            integer_str = f"{integer_part:,}".replace(
                ",", str(fmt["thousands_separator"])
            )

            # Format decimal part
            decimal_str = f"{decimal_part:0{decimal_places}d}"

            # Combine
            number_str = f"{integer_str}{str(fmt['decimal_separator'])}{decimal_str}"
        else:
            # No decimal places (e.g., JPY)
            number_str = f"{int(rounded_amount):,}".replace(
                ",", str(fmt["thousands_separator"])
            )

        # Add currency symbol
        symbol = fmt["symbol"]
        if fmt["symbol_position"] == "before":
            return f"{symbol}{number_str}"
        else:
            return f"{number_str} {symbol}"

    def _translate_medical_term(self, term: str, target_lang: str) -> str:
        """Translate medical terminology for email templates.

        Critical for patient understanding of:
        - Appointment types
        - Medical conditions
        - Medications
        - Test results
        - Instructions

        Uses a basic dictionary approach for common terms in emails.
        For full medical translation, would integrate with translation service.
        """
        # Common medical terms used in email templates
        medical_terms = {
            "appointment": {
                "es": "cita",
                "fr": "rendez-vous",
                "ar": "موعد",
                "zh": "预约",
                "pt": "consulta",
                "ru": "прием",
                "hi": "नियुक्ति",
                "bn": "অ্যাপয়েন্টমেন্ট",
                "de": "Termin",
                "it": "appuntamento",
                "ja": "予約",
                "ko": "예약",
                "vi": "cuộc hẹn",
                "tr": "randevu",
            },
            "doctor": {
                "es": "médico",
                "fr": "médecin",
                "ar": "طبيب",
                "zh": "医生",
                "pt": "médico",
                "ru": "врач",
                "hi": "डॉक्टर",
                "bn": "ডাক্তার",
                "de": "Arzt",
                "it": "medico",
                "ja": "医師",
                "ko": "의사",
                "vi": "bác sĩ",
                "tr": "doktor",
            },
            "prescription": {
                "es": "receta",
                "fr": "ordonnance",
                "ar": "وصفة طبية",
                "zh": "处方",
                "pt": "receita",
                "ru": "рецепт",
                "hi": "नुस्खा",
                "bn": "প্রেসক্রিপশন",
                "de": "Rezept",
                "it": "ricetta",
                "ja": "処方箋",
                "ko": "처방전",
                "vi": "đơn thuốc",
                "tr": "reçete",
            },
            "medication": {
                "es": "medicamento",
                "fr": "médicament",
                "ar": "دواء",
                "zh": "药物",
                "pt": "medicamento",
                "ru": "лекарство",
                "hi": "दवा",
                "bn": "ওষুধ",
                "de": "Medikament",
                "it": "farmaco",
                "ja": "薬",
                "ko": "약",
                "vi": "thuốc",
                "tr": "ilaç",
            },
            "test results": {
                "es": "resultados de pruebas",
                "fr": "résultats des tests",
                "ar": "نتائج الفحوصات",
                "zh": "检查结果",
                "pt": "resultados de exames",
                "ru": "результаты анализов",
                "hi": "परीक्षा परिणाम",
                "bn": "পরীক্ষার ফলাফল",
                "de": "Testergebnisse",
                "it": "risultati degli esami",
                "ja": "検査結果",
                "ko": "검사 결과",
                "vi": "kết quả xét nghiệm",
                "tr": "test sonuçları",
            },
            "vaccination": {
                "es": "vacunación",
                "fr": "vaccination",
                "ar": "تطعيم",
                "zh": "疫苗接种",
                "pt": "vacinação",
                "ru": "вакцинация",
                "hi": "टीकाकरण",
                "bn": "টিকাদান",
                "de": "Impfung",
                "it": "vaccinazione",
                "ja": "ワクチン接種",
                "ko": "예방접종",
                "vi": "tiêm chủng",
                "tr": "aşılama",
            },
            "emergency": {
                "es": "emergencia",
                "fr": "urgence",
                "ar": "طوارئ",
                "zh": "紧急",
                "pt": "emergência",
                "ru": "экстренный",
                "hi": "आपातकालीन",
                "bn": "জরুরি",
                "de": "Notfall",
                "it": "emergenza",
                "ja": "緊急",
                "ko": "응급",
                "vi": "khẩn cấp",
                "tr": "acil",
            },
            "hospital": {
                "es": "hospital",
                "fr": "hôpital",
                "ar": "مستشفى",
                "zh": "医院",
                "pt": "hospital",
                "ru": "больница",
                "hi": "अस्पताल",
                "bn": "হাসপাতাল",
                "de": "Krankenhaus",
                "it": "ospedale",
                "ja": "病院",
                "ko": "병원",
                "vi": "bệnh viện",
                "tr": "hastane",
            },
            "clinic": {
                "es": "clínica",
                "fr": "clinique",
                "ar": "عيادة",
                "zh": "诊所",
                "pt": "clínica",
                "ru": "клиника",
                "hi": "क्लिनिक",
                "bn": "ক্লিনিক",
                "de": "Klinik",
                "it": "clinica",
                "ja": "クリニック",
                "ko": "클리닉",
                "vi": "phòng khám",
                "tr": "klinik",
            },
            "insurance": {
                "es": "seguro",
                "fr": "assurance",
                "ar": "تأمين",
                "zh": "保险",
                "pt": "seguro",
                "ru": "страховка",
                "hi": "बीमा",
                "bn": "বীমা",
                "de": "Versicherung",
                "it": "assicurazione",
                "ja": "保険",
                "ko": "보험",
                "vi": "bảo hiểm",
                "tr": "sigorta",
            },
        }

        # Check if we have a translation for this term
        term_lower = term.lower()
        if term_lower in medical_terms and target_lang in medical_terms[term_lower]:
            return medical_terms[term_lower][target_lang]

        # For production, would call translation service here
        # For now, return original term
        logger.debug(f"No translation found for '{term}' in language '{target_lang}'")
        return term

    def get_available_templates(self) -> Dict[str, Any]:
        """Get list of available email templates."""
        templates = {}

        # Scan template directory
        for template_file in self.template_dir.glob("**/*.html"):
            relative_path = template_file.relative_to(self.template_dir)
            template_name = str(relative_path.with_suffix("")).replace(os.sep, "/")

            # Extract language from path (e.g., en/welcome.html -> en)
            parts = template_name.split("/")
            if len(parts) >= 2:
                lang_code = parts[0]
                base_name = "/".join(parts[1:])
            else:
                lang_code = "en"
                base_name = template_name

            if base_name not in templates:
                templates[base_name] = {
                    "name": base_name,
                    "languages": [],
                    "metadata": self.template_metadata.get(base_name, {}),
                }

            templates[base_name]["languages"].append(lang_code)

        return templates

    async def render_template(
        self,
        template_name: str,
        context: Dict[str, Any],
        language: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """Render email template with localization.

        Args:
            template_name: Name of the template (without language prefix)
            context: Template context variables
            language: Language code (auto-detected if not provided)
            user_id: User ID for language preference lookup

        Returns:
            Tuple of (html_content, text_content)
        """
        # Determine language
        if not language and user_id:
            # Look up user's language preference from their patient record
            try:
                # Get database session
                db_url = os.getenv("DATABASE_URL")
                if db_url:
                    engine = create_engine(db_url)
                    Session = sessionmaker(bind=engine)
                    session = Session()

                    # Get user and their associated patient
                    user = session.query(UserAuth).filter_by(id=user_id).first()
                    if user and user.patient_id:
                        patient = (
                            session.query(Patient).filter_by(id=user.patient_id).first()
                        )
                        # Patient data contains PHI and must be encrypted at rest
                        if patient and patient.primary_language:
                            language = patient.primary_language
                        else:
                            language = "en"
                    else:
                        language = "en"

                    session.close()
                else:
                    language = "en"
            except (ValueError, AttributeError, RuntimeError) as e:
                logger.warning(f"Failed to get user language preference: {e}")
                language = "en"
        elif not language:
            language = "en"

        # Add common context
        context.update(
            {
                "language": language,
                "current_year": datetime.now().year,
                "app_name": "Haven Health Passport",
                "support_email": os.getenv(
                    "SUPPORT_EMAIL", "support@havenhealthpassport.org"
                ),
                "app_url": os.getenv("FRONTEND_URL", "https://havenhealthpassport.org"),
            }
        )

        # Try to load localized template
        html_content = None
        text_content = None

        # Try language-specific template first
        template_paths = [
            f"{language}/{template_name}.html",
            f"en/{template_name}.html",  # Fallback to English
            f"{template_name}.html",  # Fallback to non-localized
        ]

        for template_path in template_paths:
            try:
                html_template = self.env.get_template(template_path)
                html_content = await html_template.render_async(**context)

                # Try to load text version
                text_path = template_path.replace(".html", ".txt")
                try:
                    text_template = self.env.get_template(text_path)
                    text_content = await text_template.render_async(**context)
                except TemplateNotFound:
                    # Generate text from HTML if no text template
                    text_content = self._html_to_text(html_content)

                break

            except TemplateNotFound:
                continue

        if not html_content:
            raise ValueError(f"Template not found: {template_name}")

        return html_content, text_content

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        # Simple conversion - in production, use html2text or similar
        # Remove style and script tags
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)

        # Replace common tags
        html = re.sub(r"<br\s*/?>", "\n", html)
        html = re.sub(r"<p[^>]*>", "\n", html)
        html = re.sub(r"</p>", "\n", html)
        html = re.sub(r"<h[1-6][^>]*>", "\n", html)
        html = re.sub(r"</h[1-6]>", "\n\n", html)

        # Remove remaining tags
        html = re.sub(r"<[^>]+>", "", html)

        # Decode HTML entities
        text = html_module.unescape(html)

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line)

        return text

    async def create_template_preview(
        self,
        template_name: str,
        language: str = "en",
        sample_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a preview of a template with sample data.

        Args:
            template_name: Template to preview
            language: Language version
            sample_data: Sample context data

        Returns:
            HTML preview
        """
        if not sample_data:
            # Default sample data
            sample_data = {
                "user_name": "John Doe",
                "verification_url": "https://example.com/verify?token=sample",
                "report_name": "Monthly Health Summary",
                "appointment_date": "2024-01-15 10:00 AM",
                "doctor_name": "Dr. Smith",
                "medication_name": "Aspirin",
                "dosage": "100mg",
            }

        html_content, _ = await self.render_template(
            template_name, sample_data, language
        )

        # Wrap in preview container
        preview_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Email Preview: {template_name} ({language})</title>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .email-container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                {html_content}
            </div>
        </body>
        </html>
        """

        return preview_html

    def validate_template_references(self, template_data: Dict[str, Any]) -> bool:
        """Validate FHIR resource references in email templates.

        Args:
            template_data: Dictionary containing template data with potential FHIR references

        Returns:
            bool: True if references are valid, False otherwise
        """
        if not template_data:
            logger.error("Template validation failed: empty template data")
            return False

        # Check for FHIR references in template variables
        if "fhir_resources" in template_data:
            resources = template_data["fhir_resources"]
            if not isinstance(resources, list):
                logger.error(
                    "Template validation failed: fhir_resources must be a list"
                )
                return False

            # Validate each resource reference
            for resource in resources:
                if not isinstance(resource, dict):
                    logger.error(
                        "Template validation failed: resource must be an object"
                    )
                    return False

                # Check for required fields
                if "resourceType" not in resource:
                    logger.error("Template validation failed: missing resourceType")
                    return False

                # Validate resource type
                valid_types = [
                    "Patient",
                    "Practitioner",
                    "Organization",
                    "Appointment",
                    "Observation",
                    "Medication",
                    "MedicationRequest",
                    "DiagnosticReport",
                ]
                if resource["resourceType"] not in valid_types:
                    logger.error(
                        f"Template validation failed: invalid resourceType '{resource['resourceType']}'"
                    )
                    return False

                # Validate resource has ID
                if "id" not in resource:
                    logger.error("Template validation failed: resource missing id")
                    return False

        return True

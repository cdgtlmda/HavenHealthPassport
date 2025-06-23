"""Extended ICD-10 Translation Configuration.

Auto-generated translations for additional ICD-10 codes.
These should be reviewed and corrected by medical translators.
"""

from src.translation.icd10_translations import ICD10Translation

# Additional ICD-10 translations
EXTENDED_ICD10_TRANSLATIONS = {
    "A00.0": ICD10Translation(
        code="A00.0",
        description_en="Cholera due to Vibrio cholerae 01, biovar cholerae",
        translations={
            "ar": "[AR] Cholera due to Vibrio cholerae 01, biovar cholerae",
            "fr": "[FR] Cholera due to Vibrio cholerae 01, biovar cholerae",
            "es": "[ES] Cholera due to Vibrio cholerae 01, biovar cholerae",
            "sw": "[SW] Cholera due to Vibrio cholerae 01, biovar cholerae",
            "fa": "[FA] Cholera due to Vibrio cholerae 01, biovar cholerae",
            "ps": "[PS] Cholera due to Vibrio cholerae 01, biovar cholerae",
            "ur": "[UR] Cholera due to Vibrio cholerae 01, biovar cholerae",
            "bn": "[BN] Cholera due to Vibrio cholerae 01, biovar cholerae",
            "hi": "[HI] Cholera due to Vibrio cholerae 01, biovar cholerae",
        },
        category="Infectious diseases",
        is_emergency=False,
    ),
    "A00.1": ICD10Translation(
        code="A00.1",
        description_en="Cholera due to Vibrio cholerae 01, biovar eltor",
        translations={
            "ar": "[AR] Cholera due to Vibrio cholerae 01, biovar eltor",
            "fr": "[FR] Cholera due to Vibrio cholerae 01, biovar eltor",
            "es": "[ES] Cholera due to Vibrio cholerae 01, biovar eltor",
            "sw": "[SW] Cholera due to Vibrio cholerae 01, biovar eltor",
            "fa": "[FA] Cholera due to Vibrio cholerae 01, biovar eltor",
            "ps": "[PS] Cholera due to Vibrio cholerae 01, biovar eltor",
            "ur": "[UR] Cholera due to Vibrio cholerae 01, biovar eltor",
            "bn": "[BN] Cholera due to Vibrio cholerae 01, biovar eltor",
            "hi": "[HI] Cholera due to Vibrio cholerae 01, biovar eltor",
        },
        category="Infectious diseases",
        is_emergency=False,
    ),
    "A00.9": ICD10Translation(
        code="A00.9",
        description_en="Cholera, unspecified",
        translations={
            "ar": "[AR] Cholera, unspecified",
            "fr": "[FR] Cholera, unspecified",
            "es": "[ES] Cholera, unspecified",
            "sw": "[SW] Cholera, unspecified",
            "fa": "[FA] Cholera, unspecified",
            "ps": "[PS] Cholera, unspecified",
            "ur": "[UR] Cholera, unspecified",
            "bn": "[BN] Cholera, unspecified",
            "hi": "[HI] Cholera, unspecified",
        },
        category="Infectious diseases",
        is_emergency=False,
    ),
    "J00": ICD10Translation(
        code="J00",
        description_en="Acute nasopharyngitis [common cold]",
        translations={
            "ar": "[AR] Acute nasopharyngitis [common cold]",
            "fr": "[FR] Acute nasopharyngitis [common cold]",
            "es": "[ES] Acute nasopharyngitis [common cold]",
            "sw": "[SW] Acute nasopharyngitis [common cold]",
            "fa": "[FA] Acute nasopharyngitis [common cold]",
            "ps": "[PS] Acute nasopharyngitis [common cold]",
            "ur": "[UR] Acute nasopharyngitis [common cold]",
            "bn": "[BN] Acute nasopharyngitis [common cold]",
            "hi": "[HI] Acute nasopharyngitis [common cold]",
        },
        category="Respiratory system",
        is_emergency=True,
    ),
    "J45.909": ICD10Translation(
        code="J45.909",
        description_en="Unspecified asthma, uncomplicated",
        translations={
            "ar": "[AR] Unspecified asthma, uncomplicated",
            "fr": "[FR] Unspecified asthma, uncomplicated",
            "es": "[ES] Unspecified asthma, uncomplicated",
            "sw": "[SW] Unspecified asthma, uncomplicated",
            "fa": "[FA] Unspecified asthma, uncomplicated",
            "ps": "[PS] Unspecified asthma, uncomplicated",
            "ur": "[UR] Unspecified asthma, uncomplicated",
            "bn": "[BN] Unspecified asthma, uncomplicated",
            "hi": "[HI] Unspecified asthma, uncomplicated",
        },
        category="Respiratory system",
        is_emergency=False,
    ),
}

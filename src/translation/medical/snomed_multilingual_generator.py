"""SNOMED CT Translation Generator with context preservation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class SNOMEDMultilingualGenerator:
    """Generates multilingual SNOMED CT concepts for refugee health."""

    def __init__(self) -> None:
        """Initialize SNOMED multilingual generator."""
        self.data_dir = Path("data/terminologies/snomed_ct")
        self.output_dir = self.data_dir / "generated"
        self.output_dir.mkdir(exist_ok=True)
        self.supported_languages = ["en", "es", "ar", "fr", "so", "ur", "fa"]
        self.refugee_health_concepts: Dict[str, Any] = {}

    def generate_refugee_health_concepts(self) -> dict:
        """Generate SNOMED CT translations for refugee health priorities."""
        # Priority SNOMED concepts for refugee health
        translations = {
            "840539006": {  # COVID-19
                "fsn": "COVID-19",
                "preferred_term": "Coronavirus disease 2019",
                "translations": {
                    "ar": {"term": "كوفيد-19", "fsn": "مرض فيروس كورونا 2019"},
                    "es": {
                        "term": "COVID-19",
                        "fsn": "Enfermedad por coronavirus 2019",
                    },
                    "fr": {"term": "COVID-19", "fsn": "Maladie à coronavirus 2019"},
                    "sw": {
                        "term": "COVID-19",
                        "fsn": "Ugonjwa wa virusi vya korona 2019",
                    },
                    "fa": {"term": "کووید-19", "fsn": "بیماری کروناویروس 2019"},
                    "ur": {"term": "کووڈ-19", "fsn": "کورونا وائرس کی بیماری 2019"},
                },
                "context": "pandemic_disease",
                "semantic_tag": "disorder",
            },
            "38341003": {  # Hypertension
                "fsn": "Hypertensive disorder, systemic arterial",
                "preferred_term": "Hypertension",
                "translations": {
                    "ar": {
                        "term": "ارتفاع ضغط الدم",
                        "fsn": "اضطراب ارتفاع ضغط الدم الشرياني",
                    },
                    "es": {
                        "term": "Hipertensión",
                        "fsn": "Trastorno hipertensivo arterial sistémico",
                    },
                    "fr": {
                        "term": "Hypertension",
                        "fsn": "Trouble hypertensif artériel systémique",
                    },
                    "sw": {
                        "term": "Shinikizo la damu",
                        "fsn": "Ugonjwa wa presha ya damu",
                    },
                    "bn": {"term": "উচ্চ রক্তচাপ", "fsn": "সিস্টেমিক ধমনী উচ্চ রক্তচাপ"},
                },
            },
        }

        # Save translations
        output_file = (
            self.output_dir
            / f"snomed_multilingual_{datetime.now().strftime('%Y%m%d')}.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(translations, f, ensure_ascii=False, indent=2)

        print(f"Generated SNOMED translations: {output_file}")
        return translations


if __name__ == "__main__":
    generator = SNOMEDMultilingualGenerator()
    generator.generate_refugee_health_concepts()

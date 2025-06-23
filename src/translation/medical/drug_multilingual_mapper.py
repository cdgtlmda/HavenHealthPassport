"""International Drug Name Mapper for refugee healthcare."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class DrugNameMultilingualMapper:
    """Maps drug names across languages and brand/generic variations."""

    def __init__(self) -> None:
        """Initialize drug name multilingual mapper."""
        self.data_dir = Path("data/terminologies/rxnorm")
        self.output_dir = self.data_dir / "generated"
        self.output_dir.mkdir(exist_ok=True)
        self.supported_languages = ["en", "es", "ar", "fr", "so", "ur", "fa"]
        self.essential_medicines: Dict[str, Any] = {}

    def generate_essential_medicines(self) -> dict:
        """Generate multilingual mappings for WHO essential medicines."""
        # WHO Essential Medicines List - key drugs for refugee populations
        medicines = {
            "paracetamol": {
                "scientific_name": "acetaminophen",
                "translations": {
                    "en": "Paracetamol",
                    "es": "Paracetamol",
                    "ar": "باراسيتامول",
                    "fr": "Paracétamol",
                    "so": "Baraseetaamool",
                    "ur": "پیراسیٹامول",
                    "fa": "پاراستامول",
                },
                "category": "analgesic",
            },
            "amoxicillin": {
                "scientific_name": "amoxicillin",
                "translations": {
                    "en": "Amoxicillin",
                    "es": "Amoxicilina",
                    "ar": "أموكسيسيلين",
                    "fr": "Amoxicilline",
                    "so": "Amoksisilliin",
                    "ur": "اموکسی سلین",
                    "fa": "آموکسی‌سیلین",
                },
                "category": "antibiotic",
            },
        }

        # Save mappings
        output_file = (
            self.output_dir / f"drug_mappings_{datetime.now().strftime('%Y%m%d')}.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(medicines, f, ensure_ascii=False, indent=2)

        print(f"Generated drug mappings: {output_file}")
        self.essential_medicines = medicines
        return medicines


if __name__ == "__main__":
    mapper = DrugNameMultilingualMapper()
    mapper.generate_essential_medicines()

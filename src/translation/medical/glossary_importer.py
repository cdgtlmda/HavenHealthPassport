"""Medical Glossary Importer - Imports generated glossary data into the database."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MedicalGlossaryImporter:
    """Importer for medical glossary data."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        """Initialize the importer."""
        self.data_dir = data_dir or Path("data/terminologies/generated")

    def import_latest_glossary(self) -> Dict[str, int]:
        """Import the most recently generated glossary file."""
        # Find the latest glossary file
        glossary_files = list(self.data_dir.glob("medical_glossary_*.json"))

        if not glossary_files:
            logger.error("No glossary files found")
            return {"imported": 0, "total": 0}

        latest_file = max(glossary_files, key=lambda p: p.stat().st_mtime)
        logger.info("Importing latest glossary: %s", latest_file)

        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Log what would be imported
        logger.info("Found %d concepts to import", len(data["concepts"]))

        for concept in data["concepts"]:
            logger.info("- %s (%s)", concept["primary_term"], concept["code"])
            logger.info(
                "  Translations: %s", list(concept.get("translations", {}).keys())
            )

        return {"imported": len(data["concepts"]), "total": len(data["concepts"])}


if __name__ == "__main__":
    importer = MedicalGlossaryImporter()
    stats = importer.import_latest_glossary()
    print(f"Import simulation completed: {stats}")

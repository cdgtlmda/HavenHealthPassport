#!/usr/bin/env python3
"""
Import medical dictionaries from data/terminologies into the system.

This script processes ICD-10, SNOMED CT, and RxNorm data files and imports them
into the Haven Health Passport medical glossary.
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.translation.medical_dictionary_importer import MedicalDictionaryImporter
from src.translation.medical_glossary import MedicalGlossaryService
from src.core.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Data directory paths
DATA_DIR = project_root / "data" / "terminologies"
ICD10_DIR = DATA_DIR / "icd10"
SNOMED_DIR = DATA_DIR / "snomed_ct"
RXNORM_DIR = DATA_DIR / "rxnorm"

# Temporary converted files directory
TEMP_DIR = project_root / "scripts" / "data_import" / "temp"


class DataConverter:
    """Convert existing data files to importer-compatible format."""

    def __init__(self):
        """Initialize the converter."""
        # Create temp directory if it doesn't exist
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def convert_icd10_data(self) -> str:
        """Convert ICD-10 data to importer format."""
        logger.info("Converting ICD-10 data...")
        
        # Load ICD-10 codes
        with open(ICD10_DIR / "icd10_codes.json", "r", encoding="utf-8") as f:
            icd10_data = json.load(f)
        
        # Load multilanguage data if available
        multilang_data = {}
        if (ICD10_DIR / "multilanguage.json").exists():
            with open(ICD10_DIR / "multilanguage.json", "r", encoding="utf-8") as f:
                multilang_data = json.load(f)
        
        # Convert to importer format
        converted_codes = []
        for code, data in icd10_data.items():
            # Skip if it's a parent category with children
            if "children" in data:
                # Still add parent categories
                converted_codes.append({
                    "code": code,
                    "description": data["description"],
                    "category": data.get("category", "General"),
                    "long_description": data.get("long_description", data["description"]),
                    "is_billable": data.get("is_billable", False)
                })
            else:
                converted_codes.append({
                    "code": code,
                    "description": data["description"],
                    "category": data.get("category", "General"),
                    "long_description": data.get("long_description", data["description"]),
                    "is_billable": data.get("is_billable", True)
                })
        
        # Save converted data
        output_file = TEMP_DIR / "icd10_converted.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"codes": converted_codes}, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Converted {len(converted_codes)} ICD-10 codes")
        return str(output_file)

    def convert_snomed_data(self) -> str:
        """Convert SNOMED CT data to importer format."""
        logger.info("Converting SNOMED CT data...")
        
        # Load SNOMED concepts
        concepts_file = SNOMED_DIR / "concepts.json"
        if not concepts_file.exists():
            logger.warning("SNOMED concepts file not found, creating sample data")
            # Create sample SNOMED data for common conditions
            sample_concepts = [
                {
                    "conceptId": "386661006",
                    "term": "Fever",
                    "fsn": "Fever (finding)",
                    "semantic_tag": "finding"
                },
                {
                    "conceptId": "22253000",
                    "term": "Pain",
                    "fsn": "Pain (finding)",
                    "semantic_tag": "finding"
                },
                {
                    "conceptId": "49727002",
                    "term": "Cough",
                    "fsn": "Cough (finding)",
                    "semantic_tag": "finding"
                },
                {
                    "conceptId": "25064002",
                    "term": "Headache",
                    "fsn": "Headache (finding)",
                    "semantic_tag": "finding"
                },
                {
                    "conceptId": "387713003",
                    "term": "Surgical procedure",
                    "fsn": "Surgical procedure (procedure)",
                    "semantic_tag": "procedure"
                },
                {
                    "conceptId": "15220000",
                    "term": "Laboratory test",
                    "fsn": "Laboratory test (procedure)",
                    "semantic_tag": "procedure"
                },
                {
                    "conceptId": "104177005",
                    "term": "Blood count",
                    "fsn": "Blood count (procedure)",
                    "semantic_tag": "procedure"
                }
            ]
            
            output_file = TEMP_DIR / "snomed_converted.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({"concepts": sample_concepts}, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created {len(sample_concepts)} sample SNOMED concepts")
            return str(output_file)
        
        # If file exists, load and convert it
        with open(concepts_file, "r", encoding="utf-8") as f:
            snomed_data = json.load(f)
        
        # Convert format if needed
        converted_concepts = []
        if isinstance(snomed_data, dict):
            for concept_id, data in snomed_data.items():
                converted_concepts.append({
                    "conceptId": concept_id,
                    "term": data.get("term", ""),
                    "fsn": data.get("fsn", data.get("term", "")),
                    "semantic_tag": data.get("semantic_tag", "finding")
                })
        else:
            # Assume it's already in the right format
            converted_concepts = snomed_data
        
        output_file = TEMP_DIR / "snomed_converted.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"concepts": converted_concepts}, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Converted {len(converted_concepts)} SNOMED concepts")
        return str(output_file)

    def convert_drug_data(self) -> str:
        """Convert RxNorm drug data to importer format."""
        logger.info("Converting drug data...")
        
        # Load RxNorm concepts
        rxnorm_file = RXNORM_DIR / "rxnorm_concepts.json"
        if not rxnorm_file.exists():
            logger.warning("RxNorm concepts file not found, creating sample data")
            # Create sample drug data
            sample_drugs = [
                {
                    "generic_name": "Paracetamol",
                    "brand_names": "Tylenol,Panadol",
                    "drug_class": "Analgesic",
                    "indication": "Pain relief and fever reduction",
                    "dosage_forms": "Tablet,Liquid,Suppository",
                    "atc_code": "N02BE01"
                },
                {
                    "generic_name": "Amoxicillin",
                    "brand_names": "Amoxil,Trimox",
                    "drug_class": "Antibiotic",
                    "indication": "Bacterial infections",
                    "dosage_forms": "Capsule,Suspension,Tablet",
                    "atc_code": "J01CA04"
                },
                {
                    "generic_name": "Ibuprofen",
                    "brand_names": "Advil,Motrin",
                    "drug_class": "NSAID",
                    "indication": "Pain, fever, and inflammation",
                    "dosage_forms": "Tablet,Liquid,Gel",
                    "atc_code": "M01AE01"
                },
                {
                    "generic_name": "Omeprazole",
                    "brand_names": "Prilosec,Losec",
                    "drug_class": "Proton pump inhibitor",
                    "indication": "Acid reflux and ulcers",
                    "dosage_forms": "Capsule,Tablet",
                    "atc_code": "A02BC01"
                },
                {
                    "generic_name": "Metformin",
                    "brand_names": "Glucophage,Fortamet",
                    "drug_class": "Antidiabetic",
                    "indication": "Type 2 diabetes",
                    "dosage_forms": "Tablet,Extended-release tablet",
                    "atc_code": "A10BA02"
                }
            ]
            
            output_file = TEMP_DIR / "drugs_converted.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({"drugs": sample_drugs}, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created {len(sample_drugs)} sample drug entries")
            return str(output_file)
        
        # If file exists, load and convert it
        with open(rxnorm_file, "r", encoding="utf-8") as f:
            rxnorm_data = json.load(f)
        
        # Load ATC mappings if available
        atc_mappings = {}
        if (RXNORM_DIR / "atc_mappings.json").exists():
            with open(RXNORM_DIR / "atc_mappings.json", "r", encoding="utf-8") as f:
                atc_mappings = json.load(f)
        
        # Convert to importer format
        converted_drugs = []
        if isinstance(rxnorm_data, dict):
            for rxcui, data in rxnorm_data.items():
                if data.get("tty") in ["SCD", "SBD", "IN"]:  # Semantic Clinical Drug, Branded Drug, Ingredient
                    converted_drugs.append({
                        "generic_name": data.get("name", ""),
                        "brand_names": ",".join(data.get("brand_names", [])),
                        "drug_class": data.get("drug_class", ""),
                        "indication": data.get("indication", ""),
                        "dosage_forms": ",".join(data.get("dosage_forms", [])),
                        "atc_code": atc_mappings.get(rxcui, "")
                    })
        else:
            # Assume it's already in the right format
            converted_drugs = rxnorm_data
        
        output_file = TEMP_DIR / "drugs_converted.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"drugs": converted_drugs}, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Converted {len(converted_drugs)} drug entries")
        return str(output_file)


def main():
    """Main function to run the import process."""
    logger.info("Starting medical dictionary import process...")
    
    # Use database session context
    with get_db() as session:
        # Initialize services
        glossary_service = MedicalGlossaryService(session)
        importer = MedicalDictionaryImporter(glossary_service)
        converter = DataConverter()
        
        # Import ICD-10 data
        try:
            logger.info("\n=== Importing ICD-10 Dictionary ===")
            icd10_file = converter.convert_icd10_data()
            stats = importer.import_icd10_dictionary(icd10_file)
            logger.info(importer.get_import_summary())
        except Exception as e:
            logger.error(f"Failed to import ICD-10 data: {e}")
        
        # Import SNOMED CT data
        try:
            logger.info("\n=== Importing SNOMED CT Dictionary ===")
            snomed_file = converter.convert_snomed_data()
            stats = importer.import_snomed_dictionary(snomed_file)
            logger.info(importer.get_import_summary())
        except Exception as e:
            logger.error(f"Failed to import SNOMED data: {e}")
        
        # Import drug data
        try:
            logger.info("\n=== Importing Drug Dictionary ===")
            drug_file = converter.convert_drug_data()
            stats = importer.import_drug_dictionary(drug_file)
            logger.info(importer.get_import_summary())
        except Exception as e:
            logger.error(f"Failed to import drug data: {e}")
        
        # Clean up temporary files
        logger.info("\nCleaning up temporary files...")
        for temp_file in TEMP_DIR.glob("*.json"):
            temp_file.unlink()
        
        logger.info("\nMedical dictionary import complete!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Expand ICD-10 translations to include all codes from the data file.

This script adds more ICD-10 codes to the translation configuration
and generates placeholder translations for multiple languages.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.translation.icd10_translations import ICD10Translation, icd10_manager
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Data file path
ICD10_DATA_FILE = project_root / "data" / "terminologies" / "icd10" / "icd10_codes.json"

# Language codes we support
SUPPORTED_LANGUAGES = ["ar", "fr", "es", "sw", "fa", "ps", "ur", "bn", "hi"]


def load_icd10_data() -> Dict:
    """Load ICD-10 data from JSON file."""
    with open(ICD10_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def categorize_icd10_code(code: str, description: str) -> str:
    """Determine category for ICD-10 code based on code prefix."""
    if code.startswith("A") or code.startswith("B"):
        return "Infectious diseases"
    elif code.startswith("C") or (code.startswith("D") and code[1] in "0123"):
        return "Neoplasms"
    elif code.startswith("E"):
        return "Nutritional disorders"
    elif code.startswith("F"):
        return "Mental health"
    elif code.startswith("G"):
        return "Nervous system"
    elif code.startswith("H"):
        return "Eye and ear"
    elif code.startswith("I"):
        return "Circulatory system"
    elif code.startswith("J"):
        return "Respiratory system"
    elif code.startswith("K"):
        return "Digestive system"
    elif code.startswith("L"):
        return "Skin conditions"
    elif code.startswith("M"):
        return "Musculoskeletal"
    elif code.startswith("N"):
        return "Genitourinary"
    elif code.startswith("O"):
        return "Maternal health"
    elif code.startswith("P"):
        return "Perinatal conditions"
    elif code.startswith("Q"):
        return "Congenital"
    elif code.startswith("R"):
        return "Symptoms"
    elif code.startswith("S") or code.startswith("T"):
        return "Injury"
    elif code.startswith("V") or code.startswith("W") or code.startswith("X") or code.startswith("Y"):
        return "External causes"
    elif code.startswith("Z"):
        return "Health status"
    else:
        return "Other"


def is_emergency_condition(code: str, description: str) -> bool:
    """Determine if condition is emergency-related."""
    emergency_keywords = [
        "hemorrhage", "acute", "severe", "emergency", "shock",
        "arrest", "failure", "crisis", "trauma", "injury",
        "poisoning", "burn", "fracture", "obstruction", "perforation"
    ]
    
    desc_lower = description.lower()
    return any(keyword in desc_lower for keyword in emergency_keywords)


def generate_translations_code() -> str:
    """Generate Python code for expanded ICD-10 translations."""
    logger.info("Loading ICD-10 data...")
    icd10_data = load_icd10_data()
    
    # Filter for billable codes (leaf nodes)
    billable_codes = {}
    for code, data in icd10_data.items():
        if data.get("is_billable", True) and "children" not in data:
            billable_codes[code] = data
    
    logger.info(f"Found {len(billable_codes)} billable ICD-10 codes")
    
    # Generate code
    code_lines = []
    code_lines.append('"""')
    code_lines.append('Extended ICD-10 Translation Configuration')
    code_lines.append('')
    code_lines.append('Auto-generated translations for additional ICD-10 codes.')
    code_lines.append('These should be reviewed and corrected by medical translators.')
    code_lines.append('"""')
    code_lines.append('')
    code_lines.append('from src.translation.icd10_translations import ICD10Translation')
    code_lines.append('')
    code_lines.append('# Additional ICD-10 translations')
    code_lines.append('EXTENDED_ICD10_TRANSLATIONS = {')
    
    # Add new codes not already in the manager
    added_count = 0
    for code, data in sorted(billable_codes.items()):
        if code not in icd10_manager.translations:
            description = data["description"]
            category = categorize_icd10_code(code, description)
            is_emergency = is_emergency_condition(code, description)
            
            # Create placeholder translations
            # In production, these would be professionally translated
            translations = {}
            for lang in SUPPORTED_LANGUAGES:
                # For now, use English with language code prefix as placeholder
                translations[lang] = f"[{lang.upper()}] {description}"
            
            code_lines.append(f'    "{code}": ICD10Translation(')
            code_lines.append(f'        code="{code}",')
            code_lines.append(f'        description_en="{description}",')
            code_lines.append('        translations={')
            
            for lang, trans in translations.items():
                code_lines.append(f'            "{lang}": "{trans}",')
            
            code_lines.append('        },')
            code_lines.append(f'        category="{category}",')
            code_lines.append(f'        is_emergency={is_emergency},')
            code_lines.append('    ),')
            
            added_count += 1
    
    code_lines.append('}')
    
    logger.info(f"Generated translations for {added_count} new ICD-10 codes")
    
    return '\n'.join(code_lines)


def main():
    """Main function to generate extended ICD-10 translations."""
    logger.info("Generating extended ICD-10 translations...")
    
    # Generate the code
    generated_code = generate_translations_code()
    
    # Save to file
    output_file = project_root / "src" / "translation" / "icd10_extended.py"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(generated_code)
    
    logger.info(f"Extended translations saved to {output_file}")
    
    # Also create a JSON file with the codes needing translation
    logger.info("Creating translation task list...")
    
    icd10_data = load_icd10_data()
    translation_tasks = []
    
    for code, data in icd10_data.items():
        if data.get("is_billable", True) and "children" not in data:
            if code not in icd10_manager.translations:
                translation_tasks.append({
                    "code": code,
                    "description_en": data["description"],
                    "category": categorize_icd10_code(code, data["description"]),
                    "is_emergency": is_emergency_condition(code, data["description"]),
                    "needs_translation": SUPPORTED_LANGUAGES
                })
    
    # Save translation tasks
    tasks_file = project_root / "data" / "terminologies" / "icd10" / "translation_tasks.json"
    with open(tasks_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_codes": len(translation_tasks),
            "languages": SUPPORTED_LANGUAGES,
            "codes": translation_tasks
        }, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Translation tasks saved to {tasks_file}")
    logger.info("ICD-10 translation configuration complete!")


if __name__ == "__main__":
    main()

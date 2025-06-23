#!/usr/bin/env python3
"""
Expand SNOMED CT translations to include all concepts from the data file.

This script adds more SNOMED concepts to the translation configuration
and generates placeholder translations for multiple languages.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.translation.snomed_translations import (
    SNOMEDTranslation, 
    SNOMEDHierarchy,
    snomed_manager
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Data file path
SNOMED_DATA_FILE = project_root / "data" / "terminologies" / "snomed_ct" / "concepts.json"

# Language codes we support
SUPPORTED_LANGUAGES = ["ar", "fr", "es", "sw", "fa", "ps", "ur", "bn", "hi"]

# Hierarchy mapping
HIERARCHY_MAP = {
    "404684003": SNOMEDHierarchy.CLINICAL_FINDING,
    "71388002": SNOMEDHierarchy.PROCEDURE,
    "123037004": SNOMEDHierarchy.BODY_STRUCTURE,
    "410607006": SNOMEDHierarchy.ORGANISM,
    "105590001": SNOMEDHierarchy.SUBSTANCE,
    "373873005": SNOMEDHierarchy.PHARMACEUTICAL,
    "123038009": SNOMEDHierarchy.SPECIMEN,
    "363787002": SNOMEDHierarchy.OBSERVABLE_ENTITY,
    "272379006": SNOMEDHierarchy.EVENT,
    "243796009": SNOMEDHierarchy.SITUATION,
}


def load_snomed_data() -> Dict:
    """Load SNOMED CT data from JSON file."""
    with open(SNOMED_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def is_emergency_concept(fsn: str, preferred_term: str) -> bool:
    """Determine if SNOMED concept is emergency-related."""
    emergency_keywords = [
        "acute", "emergency", "arrest", "shock", "failure",
        "hemorrhage", "trauma", "crisis", "critical", "severe",
        "anaphylaxis", "sepsis", "stroke", "infarction"
    ]
    
    text_lower = f"{fsn} {preferred_term}".lower()
    return any(keyword in text_lower for keyword in emergency_keywords)


def get_hierarchy(hierarchy_code: str) -> SNOMEDHierarchy:
    """Get hierarchy enum from code."""
    return HIERARCHY_MAP.get(hierarchy_code, SNOMEDHierarchy.CLINICAL_FINDING)


def generate_translations_code() -> str:
    """Generate Python code for expanded SNOMED translations."""
    logger.info("Loading SNOMED CT data...")
    snomed_data = load_snomed_data()
    
    logger.info(f"Found {len(snomed_data)} SNOMED concepts")
    
    # Generate code
    code_lines = []
    code_lines.append('"""')
    code_lines.append('Extended SNOMED CT Translation Configuration')
    code_lines.append('')
    code_lines.append('Auto-generated translations for additional SNOMED concepts.')
    code_lines.append('These should be reviewed and corrected by medical translators.')
    code_lines.append('"""')
    code_lines.append('')
    code_lines.append('from src.translation.snomed_translations import SNOMEDTranslation, SNOMEDHierarchy')
    code_lines.append('')
    code_lines.append('# Additional SNOMED translations')
    code_lines.append('EXTENDED_SNOMED_TRANSLATIONS = {')
    
    # Add new concepts not already in the manager
    added_count = 0
    for concept_id, data in sorted(snomed_data.items()):
        if concept_id not in snomed_manager.translations:
            fsn = data["fsn"]
            preferred_term = data["preferred_term"]
            hierarchy = get_hierarchy(data.get("hierarchy", "404684003"))
            is_emergency = is_emergency_concept(fsn, preferred_term)
            
            # Create placeholder translations
            translations = {}
            for lang in SUPPORTED_LANGUAGES:
                # For now, use English with language code prefix as placeholder
                translations[lang] = f"[{lang.upper()}] {preferred_term}"
            
            code_lines.append(f'    "{concept_id}": SNOMEDTranslation(')
            code_lines.append(f'        concept_id="{concept_id}",')
            code_lines.append(f'        fsn="{fsn}",')
            code_lines.append(f'        preferred_term_en="{preferred_term}",')
            code_lines.append('        translations={')
            
            for lang, trans in translations.items():
                code_lines.append(f'            "{lang}": "{trans}",')
            
            code_lines.append('        },')
            code_lines.append(f'        hierarchy=SNOMEDHierarchy.{hierarchy.name},')
            code_lines.append(f'        is_emergency={is_emergency},')
            code_lines.append('    ),')
            
            added_count += 1
    
    code_lines.append('}')
    
    logger.info(f"Generated translations for {added_count} new SNOMED concepts")
    
    return '\n'.join(code_lines)


def main():
    """Main function to generate extended SNOMED translations."""
    logger.info("Generating extended SNOMED CT translations...")
    
    # Generate the code
    generated_code = generate_translations_code()
    
    # Save to file
    output_file = project_root / "src" / "translation" / "snomed_extended.py"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(generated_code)
    
    logger.info(f"Extended translations saved to {output_file}")
    
    # Also create a JSON file with the concepts needing translation
    logger.info("Creating translation task list...")
    
    snomed_data = load_snomed_data()
    translation_tasks = []
    
    for concept_id, data in snomed_data.items():
        if concept_id not in snomed_manager.translations:
            translation_tasks.append({
                "concept_id": concept_id,
                "fsn": data["fsn"],
                "preferred_term_en": data["preferred_term"],
                "hierarchy": data.get("hierarchy", "404684003"),
                "semantic_tag": data.get("semantic_tag", ""),
                "is_emergency": is_emergency_concept(data["fsn"], data["preferred_term"]),
                "needs_translation": SUPPORTED_LANGUAGES
            })
    
    # Save translation tasks
    tasks_file = project_root / "data" / "terminologies" / "snomed_ct" / "translation_tasks.json"
    with open(tasks_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_concepts": len(translation_tasks),
            "languages": SUPPORTED_LANGUAGES,
            "concepts": translation_tasks
        }, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Translation tasks saved to {tasks_file}")
    logger.info("SNOMED CT translation configuration complete!")


if __name__ == "__main__":
    main()

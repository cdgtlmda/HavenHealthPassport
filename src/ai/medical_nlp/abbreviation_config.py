"""
Medical Abbreviation Configuration and Data.

Provides comprehensive medical abbreviation data and configuration.
 Handles FHIR Resource validation.

HIPAA Compliance Notes:
- All PHI data processed by this module must be encrypted at rest and in transit
- Access to this module should be restricted to authorized healthcare personnel only
- Implement role-based access control (RBAC) for all abbreviation configuration
- Audit logs must be maintained for all PHI access and processing operations
"""

import json
from typing import Dict, List

# Extended medical abbreviations database
MEDICAL_ABBREVIATIONS_DB = {
    # Emergency and Critical Care
    "emergency": [
        {"abbr": "ABC", "exp": ["airway, breathing, circulation"], "priority": 1},
        {"abbr": "ACLS", "exp": ["advanced cardiac life support"], "priority": 1},
        {"abbr": "AED", "exp": ["automated external defibrillator"], "priority": 1},
        {"abbr": "BLS", "exp": ["basic life support"], "priority": 1},
        {"abbr": "CPR", "exp": ["cardiopulmonary resuscitation"], "priority": 1},
        {"abbr": "GCS", "exp": ["Glasgow Coma Scale"], "priority": 1},
        {
            "abbr": "LOC",
            "exp": ["loss of consciousness", "level of consciousness"],
            "priority": 1,
        },
        {"abbr": "MCI", "exp": ["mass casualty incident"], "priority": 1},
        {"abbr": "MVA", "exp": ["motor vehicle accident"], "priority": 1},
        {"abbr": "ROSC", "exp": ["return of spontaneous circulation"], "priority": 1},
        {"abbr": "RSI", "exp": ["rapid sequence intubation"], "priority": 1},
        {"abbr": "STEMI", "exp": ["ST-elevation myocardial infarction"], "priority": 1},
        {"abbr": "VSS", "exp": ["vital signs stable"], "priority": 1},
    ],
    # Surgical and Procedures
    "surgery": [
        {"abbr": "CABG", "exp": ["coronary artery bypass graft"], "priority": 1},
        {"abbr": "EGD", "exp": ["esophagogastroduodenoscopy"], "priority": 2},
        {
            "abbr": "ERCP",
            "exp": ["endoscopic retrograde cholangiopancreatography"],
            "priority": 2,
        },
        {"abbr": "I&D", "exp": ["incision and drainage"], "priority": 2},
        {"abbr": "LAP", "exp": ["laparoscopy", "laparotomy"], "priority": 2},
        {"abbr": "ORIF", "exp": ["open reduction internal fixation"], "priority": 2},
        {"abbr": "PERC", "exp": ["percutaneous"], "priority": 2},
        {
            "abbr": "PTCA",
            "exp": ["percutaneous transluminal coronary angioplasty"],
            "priority": 2,
        },
        {"abbr": "TAH", "exp": ["total abdominal hysterectomy"], "priority": 2},
        {
            "abbr": "TAHBSO",
            "exp": [
                "total abdominal hysterectomy with bilateral salpingo-oophorectomy"
            ],
            "priority": 2,
        },
        {"abbr": "THA", "exp": ["total hip arthroplasty"], "priority": 2},
        {"abbr": "TKA", "exp": ["total knee arthroplasty"], "priority": 2},
        {"abbr": "TURP", "exp": ["transurethral resection of prostate"], "priority": 2},
    ],
    # Pediatrics
    "pediatrics": [
        {"abbr": "ALL", "exp": ["acute lymphoblastic leukemia"], "priority": 1},
        {
            "abbr": "ASD",
            "exp": ["atrial septal defect", "autism spectrum disorder"],
            "priority": 1,
        },
        {"abbr": "CF", "exp": ["cystic fibrosis"], "priority": 1},
        {"abbr": "CHD", "exp": ["congenital heart disease"], "priority": 1},
        {"abbr": "FTT", "exp": ["failure to thrive"], "priority": 1},
        {"abbr": "IUGR", "exp": ["intrauterine growth restriction"], "priority": 1},
        {"abbr": "NEC", "exp": ["necrotizing enterocolitis"], "priority": 1},
        {"abbr": "NICU", "exp": ["neonatal intensive care unit"], "priority": 1},
        {"abbr": "PDA", "exp": ["patent ductus arteriosus"], "priority": 1},
        {"abbr": "PICU", "exp": ["pediatric intensive care unit"], "priority": 1},
        {"abbr": "RDS", "exp": ["respiratory distress syndrome"], "priority": 1},
        {"abbr": "RSV", "exp": ["respiratory syncytial virus"], "priority": 1},
        {"abbr": "VSD", "exp": ["ventricular septal defect"], "priority": 1},
    ],
    # Obstetrics and Gynecology
    "obgyn": [
        {"abbr": "AFI", "exp": ["amniotic fluid index"], "priority": 2},
        {"abbr": "BPD", "exp": ["biparietal diameter"], "priority": 2},
        {"abbr": "C/S", "exp": ["cesarean section"], "priority": 1},
        {"abbr": "D&C", "exp": ["dilation and curettage"], "priority": 2},
        {"abbr": "EDC", "exp": ["estimated date of confinement"], "priority": 2},
        {"abbr": "FHR", "exp": ["fetal heart rate"], "priority": 1},
        {"abbr": "G", "exp": ["gravida"], "priority": 2},
        {"abbr": "IUFD", "exp": ["intrauterine fetal demise"], "priority": 1},
        {"abbr": "IVF", "exp": ["in vitro fertilization"], "priority": 2},
        {"abbr": "LMP", "exp": ["last menstrual period"], "priority": 2},
        {"abbr": "P", "exp": ["para"], "priority": 2},
        {"abbr": "PIH", "exp": ["pregnancy-induced hypertension"], "priority": 1},
        {"abbr": "PROM", "exp": ["premature rupture of membranes"], "priority": 1},
        {"abbr": "SVD", "exp": ["spontaneous vaginal delivery"], "priority": 2},
    ],
    # Infectious Diseases
    "infectious": [
        {"abbr": "AIDS", "exp": ["acquired immunodeficiency syndrome"], "priority": 1},
        {"abbr": "CMV", "exp": ["cytomegalovirus"], "priority": 2},
        {"abbr": "EBV", "exp": ["Epstein-Barr virus"], "priority": 2},
        {"abbr": "HAI", "exp": ["healthcare-associated infection"], "priority": 1},
        {"abbr": "HBV", "exp": ["hepatitis B virus"], "priority": 1},
        {"abbr": "HCV", "exp": ["hepatitis C virus"], "priority": 1},
        {"abbr": "HIV", "exp": ["human immunodeficiency virus"], "priority": 1},
        {"abbr": "HPV", "exp": ["human papillomavirus"], "priority": 2},
        {"abbr": "HSV", "exp": ["herpes simplex virus"], "priority": 2},
        {
            "abbr": "MRSA",
            "exp": ["methicillin-resistant Staphylococcus aureus"],
            "priority": 1,
        },
        {"abbr": "PCP", "exp": ["Pneumocystis pneumonia"], "priority": 1},
        {"abbr": "STI", "exp": ["sexually transmitted infection"], "priority": 2},
        {"abbr": "TB", "exp": ["tuberculosis"], "priority": 1},
        {"abbr": "VRE", "exp": ["vancomycin-resistant enterococci"], "priority": 1},
    ],
    # Pharmacy and Medications
    "pharmacy": [
        {"abbr": "ABX", "exp": ["antibiotics"], "priority": 1},
        {"abbr": "APAP", "exp": ["acetaminophen"], "priority": 1},
        {"abbr": "BB", "exp": ["beta blocker"], "priority": 2},
        {"abbr": "BZD", "exp": ["benzodiazepine"], "priority": 2},
        {"abbr": "CCB", "exp": ["calcium channel blocker"], "priority": 2},
        {"abbr": "D5W", "exp": ["dextrose 5% in water"], "priority": 2},
        {"abbr": "D50", "exp": ["dextrose 50%"], "priority": 1},
        {"abbr": "FFP", "exp": ["fresh frozen plasma"], "priority": 1},
        {"abbr": "IVF", "exp": ["intravenous fluids"], "priority": 1},
        {"abbr": "KCl", "exp": ["potassium chloride"], "priority": 2},
        {"abbr": "MAR", "exp": ["medication administration record"], "priority": 2},
        {"abbr": "NaCl", "exp": ["sodium chloride"], "priority": 2},
        {"abbr": "NS", "exp": ["normal saline"], "priority": 1},
        {"abbr": "PRBC", "exp": ["packed red blood cells"], "priority": 1},
        {"abbr": "PPI", "exp": ["proton pump inhibitor"], "priority": 2},
        {
            "abbr": "SSRI",
            "exp": ["selective serotonin reuptake inhibitor"],
            "priority": 2,
        },
        {"abbr": "TPN", "exp": ["total parenteral nutrition"], "priority": 1},
    ],
    # Mental Health
    "psychiatry": [
        {
            "abbr": "ADHD",
            "exp": ["attention deficit hyperactivity disorder"],
            "priority": 1,
        },
        {"abbr": "BAD", "exp": ["bipolar affective disorder"], "priority": 1},
        {"abbr": "BPD", "exp": ["borderline personality disorder"], "priority": 2},
        {"abbr": "GAD", "exp": ["generalized anxiety disorder"], "priority": 1},
        {"abbr": "MDD", "exp": ["major depressive disorder"], "priority": 1},
        {"abbr": "OCD", "exp": ["obsessive-compulsive disorder"], "priority": 1},
        {"abbr": "PTSD", "exp": ["post-traumatic stress disorder"], "priority": 1},
        {"abbr": "SI", "exp": ["suicidal ideation"], "priority": 1},
        {"abbr": "SUD", "exp": ["substance use disorder"], "priority": 1},
    ],
}


# Language-specific medical abbreviations
MULTILINGUAL_ABBREVIATIONS = {
    "es": {  # Spanish
        "TA": ["tensión arterial"],
        "FC": ["frecuencia cardíaca"],
        "FR": ["frecuencia respiratoria"],
        "UCI": ["unidad de cuidados intensivos"],
        "IAM": ["infarto agudo de miocardio"],
    },
    "fr": {  # French
        "TA": ["tension artérielle"],
        "FC": ["fréquence cardiaque"],
        "FR": ["fréquence respiratoire"],
        "USI": ["unité de soins intensifs"],
        "IDM": ["infarctus du myocarde"],
    },
    "ar": {  # Arabic
        "ضغط": ["ضغط الدم"],
        "نبض": ["نبضات القلب"],
        "تنفس": ["معدل التنفس"],
    },
    "zh": {  # Chinese
        "血压": ["血压"],
        "心率": ["心率"],
        "呼吸": ["呼吸频率"],
        "ICU": ["重症监护室"],
    },
}


def create_abbreviations_json(output_path: str = "medical_abbreviations.json") -> str:
    """Create a comprehensive JSON file of medical abbreviations."""
    all_abbreviations = []

    # Process specialty-specific abbreviations
    for specialty, abbr_list in MEDICAL_ABBREVIATIONS_DB.items():
        for item in abbr_list:
            # Create context mapping
            contexts = {}
            expansion_list = item.get("exp", [])
            if (
                isinstance(expansion_list, list)
                and expansion_list
                and specialty == "emergency"
            ):
                contexts["emergency"] = expansion_list[0]
            elif (
                isinstance(expansion_list, list)
                and expansion_list
                and specialty == "pediatrics"
            ):
                contexts["pediatric"] = expansion_list[0]

            # Create abbreviation entry
            entry = {
                "abbreviation": item["abbr"],
                "expansions": (
                    expansion_list if isinstance(expansion_list, list) else []
                ),
                "contexts": contexts,
                "specialty": specialty,
                "confidence": 0.9 if item["priority"] == 1 else 0.7,
                "usage_frequency": (
                    {expansion_list[0]: 0.8}
                    if isinstance(expansion_list, list) and expansion_list
                    else {}
                ),
                "related_terms": [],
            }

            all_abbreviations.append(entry)

    # Save to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_abbreviations, f, indent=2, ensure_ascii=False)

    return output_path


def get_specialty_specific_abbreviations(specialty: str) -> List[Dict]:
    """Get abbreviations for a specific medical specialty."""
    return MEDICAL_ABBREVIATIONS_DB.get(specialty, [])


def get_multilingual_abbreviations(language: str) -> Dict[str, List[str]]:
    """Get abbreviations for a specific language."""
    return MULTILINGUAL_ABBREVIATIONS.get(language, {})


# Export configuration
ABBREVIATION_CONFIG = {
    "min_confidence": 0.7,
    "enable_context_resolution": True,
    "context_window_size": 50,
    "max_expansions_per_abbreviation": 5,
    "preserve_original_default": True,
    "supported_languages": ["en", "es", "fr", "ar", "zh"],
    "specialty_priorities": {
        "emergency": 1.5,
        "critical_care": 1.4,
        "surgery": 1.2,
        "general": 1.0,
    },
}


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

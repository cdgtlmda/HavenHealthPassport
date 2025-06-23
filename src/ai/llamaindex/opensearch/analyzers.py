"""
Medical Analyzers for OpenSearch.

Provides medical-specific text analysis configurations including:
- Medical terminology handling
- Abbreviation expansion
- Multi-language medical terms
- ICD/SNOMED code recognition
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MedicalAnalyzerConfig:
    """Configuration for medical text analyzers."""

    # Medical synonyms
    medical_synonyms: Dict[str, List[str]] = field(default_factory=dict)

    # Medical abbreviations
    medical_abbreviations: Dict[str, str] = field(default_factory=dict)

    # ICD-10 patterns
    enable_icd10_recognition: bool = True

    # SNOMED CT support
    enable_snomed_recognition: bool = True

    # Drug name normalization
    enable_drug_normalization: bool = True

    def __post_init__(self) -> None:
        """Initialize with default medical terms."""
        if not self.medical_synonyms:
            self.medical_synonyms = self._get_default_synonyms()

        if not self.medical_abbreviations:
            self.medical_abbreviations = self._get_default_abbreviations()

    def _get_default_synonyms(self) -> Dict[str, List[str]]:
        """Get default medical synonyms."""
        return {
            "heart_attack": ["myocardial infarction", "MI", "cardiac arrest"],
            "high_blood_pressure": ["hypertension", "HTN", "elevated BP"],
            "diabetes": ["diabetes mellitus", "DM", "sugar disease"],
            "stroke": ["cerebrovascular accident", "CVA", "brain attack"],
            "pneumonia": ["lung infection", "chest infection"],
            "asthma": ["bronchial asthma", "reactive airway disease"],
            "copd": [
                "chronic obstructive pulmonary disease",
                "emphysema",
                "chronic bronchitis",
            ],
            "kidney_disease": ["renal disease", "nephropathy", "CKD"],
            "liver_disease": ["hepatic disease", "cirrhosis", "hepatopathy"],
            "cancer": ["malignancy", "neoplasm", "carcinoma", "tumor"],
            "infection": ["sepsis", "bacteremia", "viremia"],
            "fever": ["pyrexia", "febrile", "elevated temperature"],
            "pain": ["discomfort", "ache", "soreness", "tenderness"],
            "shortness_of_breath": ["dyspnea", "SOB", "difficulty breathing"],
            "headache": ["cephalalgia", "head pain", "migraine"],
            "nausea": ["queasiness", "upset stomach"],
            "vomiting": ["emesis", "throwing up"],
            "diarrhea": ["loose stools", "watery stools"],
            "constipation": ["difficulty passing stool", "hard stools"],
            "depression": ["major depressive disorder", "MDD", "clinical depression"],
            "anxiety": ["anxiety disorder", "panic disorder", "GAD"],
        }

    def _get_default_abbreviations(self) -> Dict[str, str]:
        """Get default medical abbreviations."""
        return {
            "BP": "blood pressure",
            "HR": "heart rate",
            "RR": "respiratory rate",
            "T": "temperature",
            "O2": "oxygen",
            "SpO2": "oxygen saturation",
            "BMI": "body mass index",
            "CBC": "complete blood count",
            "WBC": "white blood cell",
            "RBC": "red blood cell",
            "Hgb": "hemoglobin",
            "Hct": "hematocrit",
            "PLT": "platelet",
            "BUN": "blood urea nitrogen",
            "Cr": "creatinine",
            "Na": "sodium",
            "K": "potassium",
            "Cl": "chloride",
            "CO2": "carbon dioxide",
            "BG": "blood glucose",
            "HbA1c": "hemoglobin A1c",
            "LDL": "low-density lipoprotein",
            "HDL": "high-density lipoprotein",
            "TG": "triglycerides",
            "AST": "aspartate aminotransferase",
            "ALT": "alanine aminotransferase",
            "PT": "prothrombin time",
            "PTT": "partial thromboplastin time",
            "INR": "international normalized ratio",
            "CXR": "chest x-ray",
            "CT": "computed tomography",
            "MRI": "magnetic resonance imaging",
            "ECG": "electrocardiogram",
            "EKG": "electrocardiogram",
            "EEG": "electroencephalogram",
            "IV": "intravenous",
            "IM": "intramuscular",
            "PO": "by mouth",
            "PRN": "as needed",
            "BID": "twice daily",
            "TID": "three times daily",
            "QID": "four times daily",
            "QD": "once daily",
            "HS": "at bedtime",
            "STAT": "immediately",
            "NPO": "nothing by mouth",
            "ICU": "intensive care unit",
            "ER": "emergency room",
            "ED": "emergency department",
            "OR": "operating room",
            "PACU": "post-anesthesia care unit",
        }

    def get_analyzer_config(self) -> Dict[str, Any]:
        """Get complete analyzer configuration for OpenSearch."""
        # Convert synonyms to OpenSearch format
        synonym_rules = []
        for term, synonyms in self.medical_synonyms.items():
            rule = f"{term.replace('_', ' ')}, {', '.join(synonyms)}"
            synonym_rules.append(rule)

        # Convert abbreviations to OpenSearch format
        abbrev_rules = []
        for abbrev, expansion in self.medical_abbreviations.items():
            abbrev_rules.append(f"{abbrev} => {expansion}")

        return {
            "analyzer": {
                "medical_standard": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "medical_synonyms",
                        "medical_abbreviations",
                        "asciifolding",
                        "stop",
                    ],
                },
                "medical_code": {
                    "type": "pattern",
                    "pattern": "[A-Z][0-9]{2}\\.[0-9]{1,2}",  # ICD-10 pattern
                    "lowercase": False,
                },
                "drug_name": {
                    "type": "custom",
                    "tokenizer": "keyword",
                    "filter": ["lowercase", "drug_synonyms"],
                },
            },
            "tokenizer": {
                "medical_tokenizer": {
                    "type": "pattern",
                    "pattern": "\\W+",
                    "lowercase": True,
                }
            },
            "filter": {
                "medical_synonyms": {"type": "synonym", "synonyms": synonym_rules},
                "medical_abbreviations": {"type": "synonym", "synonyms": abbrev_rules},
                "drug_synonyms": {
                    "type": "synonym",
                    "synonyms": [
                        "acetaminophen, paracetamol, tylenol",
                        "ibuprofen, advil, motrin",
                        "aspirin, asa, acetylsalicylic acid",
                        "metformin, glucophage",
                        "lisinopril, prinivil, zestril",
                        "atorvastatin, lipitor",
                        "omeprazole, prilosec",
                        "levothyroxine, synthroid",
                        "amlodipine, norvasc",
                    ],
                },
            },
        }


def create_multilingual_analyzer() -> Dict[str, Any]:
    """Create analyzer configuration for multi-language medical content."""
    return {
        "analyzer": {
            "multilingual_medical": {
                "type": "custom",
                "tokenizer": "icu_tokenizer",
                "filter": ["icu_folding", "lowercase", "medical_synonyms", "stop"],
            }
        }
    }

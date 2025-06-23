"""
Medical NLP Configuration.

Configuration settings for medical NLP components.

HIPAA Compliance Notes:
- All PHI data processed by this module must be encrypted at rest and in transit
- Access to this module should be restricted to authorized healthcare personnel only
- Implement role-based access control (RBAC) for all configuration settings
- Audit logs must be maintained for all PHI access and processing operations
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MedicalNLPConfig:
    """Configuration for medical NLP components."""

    # Model paths
    biobert_model_path: str = "dmis-lab/biobert-v1.1"
    scibert_model_path: str = "allenai/scibert_scivocab_uncased"
    clinical_bert_path: str = "emilyalsentzer/Bio_ClinicalBERT"

    # spaCy models
    scispacy_model: str = "en_core_sci_md"
    clinical_model: str = "en_ner_bc5cdr_md"

    # API credentials
    umls_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("UMLS_API_KEY")
    )
    rxnorm_api_url: str = "https://rxnav.nlm.nih.gov/REST"

    # Terminology paths
    icd10_data_path: str = "data/terminologies/icd10"
    snomed_data_path: str = "data/terminologies/snomed"
    rxnorm_data_path: str = "data/terminologies/rxnorm"

    # Entity recognition settings
    entity_confidence_threshold: float = 0.7
    max_entity_length: int = 50
    enable_abbreviation_expansion: bool = True
    enable_negation_detection: bool = True

    # Processing settings
    batch_size: int = 32
    max_sequence_length: int = 512
    use_gpu: bool = True
    num_workers: int = 4

    # Clinical settings
    section_headers: List[str] = field(
        default_factory=lambda: [
            "chief complaint",
            "history of present illness",
            "past medical history",
            "medications",
            "allergies",
            "social history",
            "family history",
            "review of systems",
            "physical exam",
            "assessment",
            "plan",
        ]
    )

    # Temporal reasoning
    temporal_patterns: List[str] = field(
        default_factory=lambda: [
            "before",
            "after",
            "during",
            "since",
            "until",
            "for",
            "ago",
            "recently",
            "currently",
            "previously",
        ]
    )

    # Medical abbreviations
    common_abbreviations: Dict[str, str] = field(
        default_factory=lambda: {
            "htn": "hypertension",
            "dm": "diabetes mellitus",
            "cad": "coronary artery disease",
            "copd": "chronic obstructive pulmonary disease",
            "chf": "congestive heart failure",
            "mi": "myocardial infarction",
            "cva": "cerebrovascular accident",
            "sob": "shortness of breath",
            "cp": "chest pain",
            "abd": "abdominal",
            "hx": "history",
            "dx": "diagnosis",
            "tx": "treatment",
            "rx": "prescription",
            "prn": "as needed",
        }
    )

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = "logs/medical_nlp.log"


# Global configuration instance
config = MedicalNLPConfig()


def load_config(config_path: Optional[str] = None) -> MedicalNLPConfig:
    """
    Load configuration from file.

    Args:
        config_path: Path to configuration file (JSON or YAML)

    Returns:
        MedicalNLPConfig instance
    """
    if config_path and os.path.exists(config_path):
        import json  # pylint: disable=import-outside-toplevel

        import yaml  # pylint: disable=import-outside-toplevel

        with open(config_path, "r", encoding="utf-8") as f:
            if config_path.endswith(".json"):
                data = json.load(f)
            elif config_path.endswith((".yaml", ".yml")):
                data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported config format: {config_path}")

        # Update config with loaded data
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)

    return config


def save_config(config_path: str) -> None:
    """
    Save configuration to file.

    Args:
        config_path: Path to save configuration
    """
    import json  # pylint: disable=import-outside-toplevel
    from dataclasses import asdict  # pylint: disable=import-outside-toplevel

    import yaml  # pylint: disable=import-outside-toplevel

    data = asdict(config)

    with open(config_path, "w", encoding="utf-8") as f:
        if config_path.endswith(".json"):
            json.dump(data, f, indent=2)
        elif config_path.endswith((".yaml", ".yml")):
            yaml.dump(data, f, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported config format: {config_path}")

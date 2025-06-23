"""Negation Patterns and Triggers.

Comprehensive collection of negation patterns for medical text with encrypted storage and access control.
"""

from typing import List, Set, Tuple

from .negation_types import NegationScope, NegationTrigger


def get_english_negation_triggers() -> List[NegationTrigger]:
    """Get English negation triggers."""
    triggers = []

    # Pre-negation triggers
    pre_negations = [
        ("no", 5),
        ("not", 5),
        ("without", 5),
        ("denies", 5),
        ("denied", 5),
        ("negative for", 7),
        ("no evidence of", 7),
        ("no sign of", 7),
        ("absence of", 5),
        ("absent", 5),
        ("none", 3),
        ("neither", 5),
        ("never", 5),
        ("unremarkable for", 5),
        ("failed to reveal", 7),
        ("fails to reveal", 7),
        ("did not reveal", 7),
        ("cannot see", 5),
        ("not demonstrate", 5),
        ("not appear", 5),
        ("not appreciated", 5),
        ("not associated", 5),
        ("not to be", 5),
        ("no new", 5),
        ("no increase in", 5),
        ("no significant", 5),
        ("no suspicious", 5),
        ("no definite", 5),
        ("rather than", 5),
        ("ruled out", 5),
        ("rule out", 5),
        ("r/o", 5),
        ("free of", 5),
        ("negative", 5),
        ("without evidence of", 7),
        ("no acute", 5),
        ("no chronic", 5),
        ("nothing to suggest", 7),
        ("resolution of", 5),
        ("resolved", 5),
    ]

    for text, scope in pre_negations:
        triggers.append(
            NegationTrigger(
                text=text,
                scope_type=NegationScope.PRE_NEGATION,
                max_scope=scope,
                priority=2 if len(text.split()) > 1 else 1,
            )
        )

    # Post-negation triggers
    post_negations = [
        ("unlikely", 3),
        ("was ruled out", 3),
        ("were ruled out", 3),
        ("has been ruled out", 3),
        ("have been ruled out", 3),
        ("are ruled out", 3),
        ("is ruled out", 3),
        ("not present", 3),
        ("not detected", 3),
        ("not identified", 3),
        ("not found", 3),
        ("was negative", 3),
        ("were negative", 3),
        ("absent", 3),
        ("was not seen", 3),
        ("were not seen", 3),
        ("resolved", 3),
    ]

    for text, scope in post_negations:
        triggers.append(
            NegationTrigger(
                text=text,
                scope_type=NegationScope.POST_NEGATION,
                max_scope=scope,
                priority=2,
            )
        )

    # Conditional triggers
    conditionals = [
        ("if", 5),
        ("in case of", 5),
        ("should there be", 5),
        ("if there is", 5),
        ("if there are", 5),
        ("watch for", 5),
        ("return if", 5),
        ("call if", 5),
        ("ed precautions for", 7),
        ("monitor for", 5),
        ("instructions to return if", 7),
        ("unless", 5),
        ("except", 5),
        ("provided that", 5),
    ]

    for text, scope in conditionals:
        triggers.append(
            NegationTrigger(
                text=text,
                scope_type=NegationScope.CONDITIONAL,
                max_scope=scope,
                priority=1,
            )
        )

    # Uncertainty triggers
    uncertainties = [
        ("possible", 3),
        ("possibly", 3),
        ("probable", 3),
        ("probably", 3),
        ("might be", 3),
        ("may be", 3),
        ("could be", 3),
        ("questionable", 3),
        ("question of", 3),
        ("uncertain", 3),
        ("unclear", 3),
        ("equivocal", 3),
        ("suspicious for", 5),
        ("concerning for", 5),
        ("cannot exclude", 5),
        ("cannot rule out", 5),
        ("differential includes", 5),
        ("suggest", 3),
        ("consider", 3),
        ("evaluate for", 5),
        ("assess for", 5),
    ]

    for text, scope in uncertainties:
        triggers.append(
            NegationTrigger(
                text=text,
                scope_type=NegationScope.UNCERTAIN,
                max_scope=scope,
                priority=1,
            )
        )

    return triggers


def get_scope_terminators() -> Set[str]:
    """Get scope termination patterns."""
    return {
        # Conjunctions
        "but",
        "however",
        "nevertheless",
        "yet",
        "though",
        "although",
        "except",
        "besides",
        "aside from",
        "apart from",
        "other than",
        # Punctuation
        ".",
        ";",
        ":",
        ",",
        # Relative pronouns
        "which",
        "who",
        "whom",
        "that",
        # Affirmative indicators
        "revealing",
        "shows",
        "demonstrates",
        "visible",
        "evident",
        "positive for",
        "presence of",
        "consistent with",
        "compatible with",
        "suggestive of",
        "indicative of",
        "in favor of",
        # Special medical cases
        "gram positive",
        "gram negative",  # Bacterial classification
        # Section headers
        "history:",
        "exam:",
        "assessment:",
        "plan:",
        "labs:",
        "imaging:",
    }


def get_pseudo_negation_patterns() -> List[Tuple[str, str]]:
    """Get pseudo-negation patterns (appear negative but aren't)."""
    return [
        # Pattern, reason
        (r"no increase", "stable finding"),
        (r"no change", "stable finding"),
        (r"no new", "previous finding exists"),
        (r"not only.*but also", "affirmative construction"),
        (r"not drain.*", "instruction"),
        (r"not to be confused", "clarification"),
        (r"no further", "completion"),
        (r"no significant change", "stable"),
        (r"without difficulty", "positive ability"),
        (r"not necessarily", "possibility"),
        (r"gram negative", "bacterial classification"),
        (r"double negative", "grammatical term"),
        (r"no more than", "quantity limit"),
        (r"not uncommon", "double negative meaning common"),
        (r"no sooner", "temporal expression"),
        (r"no better", "comparison"),
        (r"no different", "comparison"),
        (r"not limited to", "inclusive phrase"),
        (r"nothing but", "emphatic positive"),
    ]


def get_multilingual_triggers(language: str) -> List[NegationTrigger]:
    """Get negation triggers for other languages."""
    triggers = []

    if language == "es":  # Spanish
        spanish_triggers = [
            ("no", 5),
            ("sin", 5),
            ("niega", 5),
            ("negativo para", 7),
            ("ausencia de", 5),
            ("libre de", 5),
            ("descarta", 5),
            ("descartado", 5),
            ("ningún", 5),
            ("ninguno", 5),
            ("tampoco", 3),
        ]
        for text, scope in spanish_triggers:
            triggers.append(
                NegationTrigger(
                    text=text, scope_type=NegationScope.PRE_NEGATION, max_scope=scope
                )
            )

    elif language == "fr":  # French
        french_triggers = [
            ("pas", 5),
            ("non", 5),
            ("sans", 5),
            ("aucun", 5),
            ("négatif pour", 7),
            ("absence de", 5),
            ("nie", 5),
            ("jamais", 5),
            ("ni", 3),
            ("plus", 3),
        ]
        for text, scope in french_triggers:
            triggers.append(
                NegationTrigger(
                    text=text, scope_type=NegationScope.PRE_NEGATION, max_scope=scope
                )
            )

    elif language == "de":  # German
        german_triggers = [
            ("kein", 5),
            ("nicht", 5),
            ("ohne", 5),
            ("negativ für", 7),
            ("fehlt", 5),
            ("verneint", 5),
            ("niemals", 5),
            ("weder", 5),
        ]
        for text, scope in german_triggers:
            triggers.append(
                NegationTrigger(
                    text=text, scope_type=NegationScope.PRE_NEGATION, max_scope=scope
                )
            )

    return triggers


# Medical concept indicators
MEDICAL_CONCEPT_INDICATORS = [
    # Symptoms
    "pain",
    "ache",
    "fever",
    "cough",
    "nausea",
    "vomit",
    "dizz",
    "swell",
    "rash",
    "itch",
    "burn",
    "numb",
    "weak",
    "fatigue",
    "tired",
    "malaise",
    "chills",
    "sweat",
    "tremor",
    "cramp",
    "stiff",
    "tender",
    "sore",
    "discharge",
    "bleed",
    "bruise",
    # Conditions
    "disease",
    "disorder",
    "syndrome",
    "condition",
    "symptom",
    "infection",
    "inflammation",
    "cancer",
    "tumor",
    "lesion",
    "injury",
    "fracture",
    "strain",
    "sprain",
    "tear",
    "rupture",
    "stenosis",
    "occlusion",
    "thrombosis",
    "embolism",
    "ischemia",
    "infarction",
    "hemorrhage",
    "aneurysm",
    "abscess",
    "ulcer",
    # Medical terms
    "abnormal",
    "deficit",
    "impair",
    "dysfunction",
    "failure",
    "insufficiency",
    "deficiency",
    "excess",
    "elevated",
    "decreased",
    "positive",
    "negative",
    "present",
    "absent",
    "normal",
    "stable",
    # Body parts
    "heart",
    "lung",
    "liver",
    "kidney",
    "brain",
    "bone",
    "muscle",
    "nerve",
    "vessel",
    "artery",
    "vein",
    "joint",
    "spine",
    "chest",
    "abdomen",
    "head",
    "neck",
    "back",
    "extremity",
    "skin",
]


# Clinical section patterns
CLINICAL_SECTIONS = {
    "chief_complaint": [
        "chief complaint",
        "cc",
        "presenting complaint",
        "reason for visit",
    ],
    "history_present_illness": ["history of present illness", "hpi", "present illness"],
    "past_medical_history": [
        "past medical history",
        "pmh",
        "medical history",
        "past history",
    ],
    "review_of_systems": ["review of systems", "ros", "systems review"],
    "physical_exam": [
        "physical exam",
        "physical examination",
        "pe",
        "exam",
        "examination",
    ],
    "allergies": ["allergies", "nkda", "nka", "allergic to", "allergy"],
    "medications": ["medications", "meds", "current medications", "home medications"],
    "assessment": ["assessment", "impression", "assessment and plan", "a/p", "a&p"],
    "plan": ["plan", "treatment plan", "recommendations", "disposition"],
}

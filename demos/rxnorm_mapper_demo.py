#!/usr/bin/env python3
"""
RxNorm Mapper Demonstration

This script demonstrates the capabilities of the RxNorm drug mapping system.
"""

import asyncio
from datetime import datetime

from src.ai.medical_nlp.terminology.rxnorm_mapper import create_rxnorm_mapper


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}\n")


def print_concept(concept, indent=0):
    """Print a formatted RxNorm concept"""
    prefix = "  " * indent
    print(f"{prefix}RxCUI: {concept.rxcui}")
    print(f"{prefix}Name: {concept.name}")
    print(f"{prefix}Type: {concept.tty.value}")
    if concept.strength:
        print(f"{prefix}Strength: {concept.strength}")
    if concept.dose_form:
        print(f"{prefix}Dose Form: {concept.dose_form}")
    if concept.ingredients:
        print(f"{prefix}Ingredients: {concept.ingredients}")
    print(f"{prefix}Prescribable: {'Yes' if concept.prescribable else 'No'}")
    print()


def print_interaction(interaction):
    """Print a formatted drug interaction"""
    print(f"  Drug 1: {interaction.drug1_name} (RxCUI: {interaction.drug1_rxcui})")
    print(f"  Drug 2: {interaction.drug2_name} (RxCUI: {interaction.drug2_rxcui})")
    print(f"  Severity: {interaction.severity.upper()}")
    print(f"  Description: {interaction.description}")
    if interaction.management:
        print(f"  Management: {interaction.management}")
    print()


async def main():
    """Main demonstration function"""
    print("RxNorm Drug Mapper Demonstration")
    print("================================")

    # Initialize mapper
    print("\nInitializing RxNorm mapper...")
    mapper = create_rxnorm_mapper(enable_fuzzy_matching=True, check_interactions=True)
    # Get statistics
    stats = mapper.get_statistics()
    print(f"\nMapper initialized with {stats['total_concepts']} concepts")
    print(f"Ingredient concepts: {stats['ingredient_concepts']}")
    print(f"Brand concepts: {stats['brand_concepts']}")
    print(f"Clinical drug concepts: {stats['clinical_drug_concepts']}")

    # Example 1: Search by drug name
    print_section("Example 1: Search by Drug Name")
    result = mapper.search("aspirin")
    print(f"Search query: 'aspirin'")
    print(f"Found {len(result.concepts)} result(s):")
    for concept in result.concepts[:3]:
        print_concept(concept)

    # Example 2: Search by RxCUI
    print_section("Example 2: Search by RxCUI")
    result = mapper.search("5640")
    print(f"Search query: '5640' (Ibuprofen RxCUI)")
    if result.concepts:
        print_concept(result.concepts[0])

    # Example 3: Search with strength
    print_section("Example 3: Search with Strength")
    result = mapper.search("metformin 500 mg")
    print(f"Search query: 'metformin 500 mg'")
    print(f"Found {len(result.concepts)} result(s):")
    for concept in result.concepts[:2]:
        print_concept(concept)

    # Example 4: Brand name search
    print_section("Example 4: Brand Name Search")
    result = mapper.search("tylenol", search_type="brand")
    print(f"Search query: 'tylenol' (brand only)")
    if result.concepts:
        print_concept(result.concepts[0])

    # Example 5: Fuzzy search with typo
    print_section("Example 5: Fuzzy Search (Typo Handling)")
    result = mapper.search("ibuprofin")  # Note the typo
    print(f"Search query: 'ibuprofin' (typo)")
    print(f"Found {len(result.concepts)} result(s):")
    if result.concepts:
        print(f"Approximate match: {result.approximate_match}")
        print_concept(result.concepts[0])
    # Example 6: Drug interactions
    print_section("Example 6: Drug-Drug Interactions")
    drug_list = ["1191", "5640", "6809"]  # Aspirin, Ibuprofen, Metformin
    print(f"Checking interactions between:")
    for rxcui in drug_list:
        concept = mapper.get_concept(rxcui)
        if concept:
            print(f"  - {concept.name} (RxCUI: {rxcui})")

    interactions = mapper.check_drug_interactions(drug_list)
    print(f"\nFound {len(interactions)} interaction(s):")
    for interaction in interactions:
        print_interaction(interaction)

    # Example 7: NDC lookup
    print_section("Example 7: NDC Code Lookup")
    ndc = "0363-0160-01"
    print(f"Looking up NDC: {ndc}")
    drug = mapper.find_by_ndc(ndc)
    if drug:
        print_concept(drug)
    else:
        print("Drug not found")

    # Example 8: Prescription sig parsing
    print_section("Example 8: Prescription Sig Parsing")
    sigs = [
        "Aspirin 81 mg po daily",
        "Ibuprofen 200mg tid prn for pain",
        "Metformin 500 mg PO BID with meals",
    ]

    for sig in sigs:
        print(f"Parsing: '{sig}'")
        parsed = mapper.parse_sig(sig)
        print(f"  Drug: {parsed.drug_name}")
        if parsed.rxcui:
            print(f"  RxCUI: {parsed.rxcui}")
        if parsed.dose:
            print(f"  Dose: {parsed.dose} {parsed.dose_unit}")
        if parsed.route:
            print(f"  Route: {parsed.route}")
        if parsed.frequency:
            print(f"  Frequency: {parsed.frequency}")
        if parsed.prn:
            print(f"  PRN: Yes")
        print()
    # Example 9: Find related drugs
    print_section("Example 9: Finding Related Drugs")

    # Find brand/generic equivalents
    aspirin_81_rxcui = "198440"
    print(f"Finding generic equivalents for Aspirin 81 MG Oral Tablet")
    related = mapper.find_related_drugs(aspirin_81_rxcui, "brand_generic")
    if related:
        print(f"Found {len(related)} related drug(s):")
        for drug in related[:2]:
            print_concept(drug, indent=1)

    # Example 10: Batch search
    print_section("Example 10: Batch Search")
    queries = [
        "aspirin",
        "acetaminophen",
        "blood pressure medication",
        "diabetes drug",
        "antibiotic",
    ]

    print(f"Performing batch search for {len(queries)} queries...")
    batch_results = await mapper.batch_search(queries, max_results=2)

    for query, result in batch_results.items():
        print(f"\nQuery: '{query}'")
        if result.concepts:
            print(f"  Top results:")
            for concept in result.concepts[:2]:
                print(f"    - {concept.name} (RxCUI: {concept.rxcui})")
        else:
            print("  No results found")

    # Example 11: Get brand names
    print_section("Example 11: Get Brand Names for Generic")
    generic_rxcui = "161"  # Acetaminophen
    print(f"Finding brand names for Acetaminophen (RxCUI: {generic_rxcui})")
    brands = mapper.get_brand_names(generic_rxcui)
    if brands:
        print(f"Brand names:")
        for brand in brands:
            print(f"  - {brand}")

    # Final statistics
    print_section("Final Statistics")
    print(f"Total searches performed: {len(mapper._search_cache)}")
    print(f"Fuzzy matching enabled: {mapper.enable_fuzzy_matching}")
    print(f"Unit conversion available: {mapper.enable_unit_conversion}")


if __name__ == "__main__":
    asyncio.run(main())

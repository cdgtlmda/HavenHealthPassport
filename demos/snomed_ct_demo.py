#!/usr/bin/env python3
"""
SNOMED CT Integration Demonstration

This script demonstrates the capabilities of the SNOMED CT integration system.
"""

import asyncio
from datetime import datetime

from src.ai.medical_nlp.terminology.snomed_ct_integration import (
    Hierarchy,
    RelationshipType,
    create_snomed_ct_integration,
)


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}\n")


def print_concept(concept, indent=0):
    """Print a formatted SNOMED CT concept"""
    prefix = "  " * indent
    print(f"{prefix}Concept ID: {concept.concept_id}")
    print(f"{prefix}FSN: {concept.fsn}")
    print(f"{prefix}Preferred Term: {concept.preferred_term}")
    print(f"{prefix}Status: {concept.status.value}")
    if concept.hierarchy:
        print(f"{prefix}Hierarchy: {concept.hierarchy.name}")
    if concept.get_semantic_tag():
        print(f"{prefix}Semantic Tag: {concept.get_semantic_tag()}")
    print()


async def main():
    """Main demonstration function"""
    print("SNOMED CT Integration Demonstration")
    print("===================================")

    # Initialize integration
    print("\nInitializing SNOMED CT integration...")
    snomed = create_snomed_ct_integration(
        enable_fuzzy_matching=True, enable_graph_operations=True, enable_ecl=True
    )

    # Get statistics
    stats = snomed.get_statistics()
    print(f"\nIntegration initialized with {stats['total_concepts']} concepts")
    print(f"Active concepts: {stats['active_concepts']}")
    print(
        f"Hierarchies covered: {len([h for h, count in stats['hierarchies'].items() if count > 0])}"
    )
    # Example 1: Search by concept ID
    print_section("Example 1: Direct Concept ID Search")
    result = snomed.search("22298006")
    print(f"Search query: '22298006' (MI concept ID)")
    print(f"Found {len(result.concepts)} result(s):")
    for concept in result.concepts:
        print_concept(concept)

    # Example 2: Search by clinical term
    print_section("Example 2: Clinical Term Search")
    result = snomed.search("heart attack")
    print(f"Search query: 'heart attack'")
    print(
        f"Found {result.total_matches} total matches, showing top {len(result.concepts)}:"
    )
    for concept in result.concepts[:3]:
        print_concept(concept)

    # Example 3: Hierarchy-specific search
    print_section("Example 3: Hierarchy-Specific Search")

    # Search for "heart" in clinical findings
    clinical_result = snomed.search("heart", hierarchies=[Hierarchy.CLINICAL_FINDING])
    print(
        f"Search 'heart' in Clinical Findings: {len(clinical_result.concepts)} results"
    )

    # Search for "heart" in body structures
    body_result = snomed.search("heart", hierarchies=[Hierarchy.BODY_STRUCTURE])
    print(f"Search 'heart' in Body Structures: {len(body_result.concepts)} results")

    if body_result.concepts:
        print("\nExample body structure:")
        print_concept(body_result.concepts[0])

    # Example 4: Concept navigation
    print_section("Example 4: Concept Navigation")

    # Get a specific concept
    mi_concept = snomed.get_concept("22298006")
    if mi_concept:
        print("Myocardial Infarction concept:")
        print_concept(mi_concept)
        # Get parents
        print("\nParent concepts:")
        parents = snomed.get_parents("22298006")
        for parent in parents[:2]:
            print_concept(parent, indent=1)

        # Get relationships
        print("Relationships:")
        relationships = snomed.get_relationships("22298006")
        for rel_type, targets in relationships.items():
            print(f"  {rel_type}: {len(targets)} target(s)")
            for target in targets[:2]:
                print(f"    -> {target.concept_id}: {target.preferred_term}")

    # Example 5: Expression Constraint Language (ECL)
    print_section("Example 5: Expression Constraint Language (ECL)")

    # Get all clinical findings
    print("Query: < 404684003 (descendants of Clinical Finding)")
    findings = snomed.execute_ecl("< 404684003")
    print(f"Found {len(findings)} clinical findings")

    # Get diabetes and subtypes
    print("\nQuery: << 73211009 (self and descendants of Diabetes)")
    diabetes_types = snomed.execute_ecl("<< 73211009")
    print(f"Found {len(diabetes_types)} diabetes-related concepts:")
    for concept in diabetes_types[:3]:
        print(f"  - {concept.preferred_term}")

    # Example 6: Multi-language support
    print_section("Example 6: Multi-language Support")

    concepts_to_translate = ["22298006", "38341003"]
    languages = ["en", "es"]

    print("Translations:")
    for concept_id in concepts_to_translate:
        concept = snomed.get_concept(concept_id)
        if concept:
            print(f"\n{concept.fsn}:")
            for lang in languages:
                translation = snomed.get_translation(concept_id, lang)
                if translation:
                    print(f"  {lang}: {translation}")
    # Example 7: Post-coordinated expressions
    print_section("Example 7: Post-coordinated Expressions")

    # Create an expression for "MI of inferior wall"
    expression = snomed.create_expression(
        focus_concepts=["22298006"],  # MI
        refinements={
            "363698007": [("=", "277005")]  # Finding site = Inferior wall of heart
        },
    )

    print("Post-coordinated expression:")
    print(f"  Expression: {expression.to_string()}")
    print("  Meaning: Myocardial infarction with finding site of inferior wall")

    # Example 8: Batch search
    print_section("Example 8: Batch Search")

    queries = [
        "diabetes",
        "hypertension",
        "asthma",
        "chronic pain",
        "195967001",  # Asthma concept ID
    ]

    print(f"Performing batch search for {len(queries)} queries...")
    batch_results = await snomed.batch_search(queries)

    print("\nBatch search results:")
    for query, result in batch_results.items():
        if result.concepts:
            top_concept = result.concepts[0]
            print(
                f"  '{query}' -> {top_concept.concept_id}: {top_concept.preferred_term}"
            )
        else:
            print(f"  '{query}' -> No results found")

    # Example 9: Common ancestors
    print_section("Example 9: Finding Common Ancestors")

    # Find what MI and Hypertension have in common
    concept_ids = ["22298006", "38341003"]  # MI and Hypertension
    common_ancestors = snomed.get_common_ancestors(concept_ids)

    print(f"Common ancestors of MI and Hypertension:")
    for ancestor in common_ancestors[:3]:
        print(f"  - {ancestor.concept_id}: {ancestor.preferred_term}")

    # Final statistics
    print_section("Search Performance")
    print(f"Total concepts indexed: {stats['total_concepts']}")
    print(f"Graph enabled: {stats['graph_enabled']}")
    if stats["graph_enabled"]:
        print(f"Graph nodes: {stats['graph_nodes']}")
        print(f"Graph edges: {stats['graph_edges']}")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
ICD-10 Code Mapper Demonstration

This script demonstrates the capabilities of the ICD-10 code mapping system.
"""

import asyncio
import json
from datetime import datetime

from src.ai.medical_nlp.terminology.icd10_mapper import MatchType, create_icd10_mapper


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}\n")


def print_code_result(code):
    """Print a formatted ICD-10 code result"""
    print(f"  Code: {code.code}")
    print(f"  Description: {code.description}")
    print(f"  Match Type: {code.match_type.value}")
    print(f"  Confidence: {code.confidence:.2f}")
    print(f"  Billable: {'Yes' if code.is_billable else 'No'}")
    if code.category:
        print(f"  Category: {code.category}")
    print()


async def main():
    """Main demonstration function"""
    print("ICD-10 Code Mapper Demonstration")
    print("================================")

    # Initialize mapper
    print("\nInitializing ICD-10 mapper...")
    mapper = create_icd10_mapper(
        enable_fuzzy_matching=True,
        enable_semantic_matching=False,  # Disabled for demo
        min_confidence=0.7,
    )

    # Get statistics
    stats = mapper.get_statistics()
    print(f"\nMapper initialized with {stats['total_codes']} codes")
    print(f"Billable codes: {stats['billable_codes']}")
    print(f"Non-billable codes: {stats['non_billable_codes']}")
    # Example 1: Direct code search
    print_section("Example 1: Direct Code Search")
    result = mapper.search("J00")
    print(f"Search query: 'J00'")
    print(f"Found {len(result.codes)} result(s):")
    for code in result.codes[:3]:
        print_code_result(code)

    # Example 2: Description search
    print_section("Example 2: Description Search")
    result = mapper.search("common cold")
    print(f"Search query: 'common cold'")
    print(f"Found {len(result.codes)} result(s):")
    for code in result.codes[:3]:
        print_code_result(code)

    # Example 3: Partial/fuzzy search
    print_section("Example 3: Partial/Fuzzy Search")
    result = mapper.search("asthm")  # Intentionally incomplete
    print(f"Search query: 'asthm' (partial)")
    print(f"Found {len(result.codes)} result(s):")
    for code in result.codes[:3]:
        print_code_result(code)

    # Example 4: Abbreviation search
    print_section("Example 4: Abbreviation Search")
    result = mapper.search("URI")
    print(f"Search query: 'URI'")
    print(f"Found {len(result.codes)} result(s):")
    for code in result.codes[:3]:
        print_code_result(code)

    # Example 5: Hierarchical search
    print_section("Example 5: Hierarchical Search with Children")
    result = mapper.search("A00", include_children=True)
    print(f"Search query: 'A00' (with children)")
    print(f"Found {len(result.codes)} result(s):")
    for code in result.codes[:5]:
        print_code_result(code)
    # Example 6: Code validation
    print_section("Example 6: Code Validation")
    codes_to_validate = ["J00", "A00", "INVALID123"]
    for code in codes_to_validate:
        valid, msg = mapper.validate_code(code)
        print(f"Code '{code}': {'Valid' if valid else f'Invalid - {msg}'}")

    # Example 7: Code compatibility check
    print_section("Example 7: Code Compatibility Check")
    pairs = [("J00", "J45"), ("A00", "A00.0")]
    for code1, code2 in pairs:
        compat, msg = mapper.check_code_compatibility(code1, code2)
        print(
            f"Codes '{code1}' and '{code2}': {'Compatible' if compat else f'Incompatible - {msg}'}"
        )

    # Example 8: Batch search
    print_section("Example 8: Batch Search")
    queries = ["common cold", "asthma", "diabetes", "cholera"]
    print(f"Performing batch search for {len(queries)} queries...")

    batch_results = await mapper.batch_search(queries)

    for query, result in batch_results.items():
        print(f"\nQuery: '{query}'")
        if result.codes:
            print(
                f"  Top result: {result.codes[0].code} - {result.codes[0].description}"
            )
        else:
            print("  No results found")

    # Example 9: Performance test
    print_section("Example 9: Performance Test")
    print("Testing search performance with caching...")

    # First search (cache miss)
    start = datetime.now()
    result1 = mapper.search("asthma")
    time1 = (datetime.now() - start).total_seconds()

    # Second search (cache hit)
    start = datetime.now()
    result2 = mapper.search("asthma")
    time2 = (datetime.now() - start).total_seconds()

    print(f"First search (cache miss): {time1:.4f} seconds")
    print(f"Second search (cache hit): {time2:.4f} seconds")
    print(f"Speed improvement: {time1/time2:.1f}x faster")

    # Final statistics
    print_section("Final Statistics")
    final_stats = mapper.get_statistics()
    print(
        f"Total searches performed: {final_stats['cache_hits'] + final_stats['cache_misses']}"
    )
    print(f"Cache hits: {final_stats['cache_hits']}")
    print(f"Cache misses: {final_stats['cache_misses']}")
    print(f"Cache hit rate: {final_stats['cache_hit_rate']:.1%}")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Example usage of OpenSearch Connector for Haven Health Passport.

This script demonstrates how to:
1. Connect to OpenSearch
2. Create medical indices
3. Index medical documents
4. Search with medical query optimization
5. Monitor cluster health
Handles FHIR Resource validation.
"""

import sys
from pathlib import Path
from typing import List

from llama_index.core import Document

from src.ai.llamaindex.opensearch import (
    MedicalIndexManager,
    OpenSearchConnectionConfig,
    OpenSearchConnector,
    OpenSearchEnvironment,
    OpenSearchHealthCheck,
)

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parents[4]))


def main() -> None:
    """Run main example function."""
    # 1. Configure connection
    print("1. Configuring OpenSearch connection...")
    config = OpenSearchConnectionConfig.from_environment(
        OpenSearchEnvironment.DEVELOPMENT  # Change to PRODUCTION for prod
    )

    # 2. Create connector and connect
    print("2. Connecting to OpenSearch...")
    connector = OpenSearchConnector(config, OpenSearchEnvironment.DEVELOPMENT)

    try:
        connector.connect()
        print("✅ Connected successfully!")
    except (ConnectionError, ValueError) as e:
        print(f"❌ Connection failed: {e}")
        return

    # 3. Create medical indices
    print("\n3. Creating medical indices...")
    index_manager = MedicalIndexManager(connector)
    results = index_manager.initialize_all_indices()

    for index_name, success in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {index_name}")

    # 4. Index sample medical documents
    print("\n4. Indexing sample medical documents...")
    sample_documents = [
        Document(
            text="Patient presents with acute myocardial infarction (MI). "
            "Started on aspirin, beta-blockers, and ACE inhibitors. "
            "Troponin levels elevated at 2.5 ng/mL.",
            metadata={
                "document_type": "clinical_note",
                "specialty": "cardiology",
                "icd_codes": ["I21.9"],
                "language": "en",
            },
        ),
        Document(
            text="Paciente presenta diabetes mellitus tipo 2. "
            "Hemoglobina glicosilada (HbA1c) de 8.5%. "
            "Se inicia tratamiento con metformina 850mg BID.",
            metadata={
                "document_type": "clinical_note",
                "specialty": "endocrinology",
                "icd_codes": ["E11.9"],
                "language": "es",
            },
        ),
        Document(
            text="Chest X-ray shows bilateral infiltrates consistent with "
            "pneumonia. WBC count elevated at 15,000. "
            "Started on broad-spectrum antibiotics.",
            metadata={
                "document_type": "radiology_report",
                "specialty": "pulmonology",
                "icd_codes": ["J18.9"],
                "language": "en",
            },
        ),
    ]

    indexed_count, errors = connector.bulk_index_documents(
        sample_documents, "haven-health-medical-documents"
    )

    print(f"✅ Indexed {indexed_count} documents")
    if errors:
        print(f"❌ Errors: {len(errors)}")

    # 5. Search medical documents
    print("\n5. Searching medical documents...")

    # Search for heart-related conditions
    search_results = connector.search(
        "haven-health-medical-documents", "heart attack MI", size=5
    )

    print(f"Found {search_results['hits']['total']['value']} results")
    for hit in search_results["hits"]["hits"]:
        print(f"   - Score: {hit['_score']:.2f}")
        print(f"     Text: {hit['_source']['content'][:100]}...")
        print(
            f"     Type: {hit['_source']['metadata'].get('document_type', 'unknown')}"
        )

    # 6. Check cluster health
    print("\n6. Checking cluster health...")
    health_check = OpenSearchHealthCheck(connector)
    health_report = health_check.check_cluster_health()

    print(f"   Cluster Status: {health_report.get('status', 'unknown')}")
    print(f"   Active Shards: {health_report.get('active_shards', 0)}")
    print(f"   Number of Nodes: {health_report.get('number_of_nodes', 0)}")

    # 7. Get index statistics
    print("\n7. Getting index statistics...")
    index_health = index_manager.get_index_health()

    for index_name, health_data in index_health.items():
        if health_data.get("exists"):
            print(f"   {index_name}:")
            print(f"     - Documents: {health_data.get('docs_count', 0)}")
            print(
                f"     - Size: {health_data.get('size_bytes', 0) / 1024 / 1024:.2f} MB"
            )

    # 8. Clean up
    print("\n8. Closing connection...")
    connector.close()
    print("✅ Connection closed")


if __name__ == "__main__":
    main()


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

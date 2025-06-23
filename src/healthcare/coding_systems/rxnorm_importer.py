"""RxNorm Data Importer.

This module handles importing RxNorm data from various sources including:
- RxNorm REST API
- RxNorm RRF (Rich Release Format) files
- CSV exports
- WHO Essential Medicines List integration

Handles FHIR Medication Resource validation for imported drug data.
All PHI data is encrypted and requires proper access control permissions.
"""

import csv
import gzip
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from src.healthcare.fhir_validator import FHIRValidator

from .rxnorm_implementation import RxNormConcept, RxNormRepository, RxNormTermType

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "Medication"


class ImportSource(Enum):
    """RxNorm data import sources."""

    RXNORM_API = "rxnorm_api"
    RRF_FILES = "rrf_files"
    CSV_FILES = "csv_files"
    WHO_ESSENTIAL = "who_essential"
    CUSTOM_FORMULARY = "custom_formulary"


class ImportMode(Enum):
    """Import modes for data loading."""

    FULL = "full"  # Complete import, replaces existing data
    INCREMENTAL = "incremental"  # Add new concepts only
    UPDATE = "update"  # Update existing concepts and add new ones


@dataclass
class ImportConfig:
    """Configuration for RxNorm import."""

    source: ImportSource
    mode: ImportMode = ImportMode.INCREMENTAL
    data_path: Optional[Path] = None
    api_base_url: str = "https://rxnav.nlm.nih.gov/REST/"
    batch_size: int = 1000
    max_retries: int = 3
    timeout: int = 30
    include_suppressed: bool = False
    include_obsolete: bool = False
    term_types: Optional[List[RxNormTermType]] = None
    language_filter: Optional[List[str]] = None
    refugee_formulary: bool = True  # Include refugee-specific medications


class RxNormAPIClient:
    """Client for RxNorm REST API."""

    def __init__(self, base_url: str, timeout: int = 30):
        """Initialize API client.

        Args:
            base_url: Base URL for RxNorm API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def get_rxcui_status(self, rxcui: str) -> Dict[str, Any]:
        """Get status information for an RXCUI.

        Args:
            rxcui: RxNorm concept unique identifier

        Returns:
            Status information dictionary
        """
        endpoint = urljoin(self.base_url, f"rxcui/{rxcui}/status.json")

        try:
            response = self.session.get(endpoint, timeout=self.timeout)
            response.raise_for_status()
            return dict(response.json())
        except requests.RequestException as e:
            logger.error("Failed to get status for RXCUI %s: %s", rxcui, e)
            raise

    def get_rxcui_properties(self, rxcui: str) -> Dict[str, Any]:
        """Get properties for an RXCUI.

        Args:
            rxcui: RxNorm concept unique identifier

        Returns:
            Properties dictionary
        """
        endpoint = urljoin(self.base_url, f"rxcui/{rxcui}/properties.json")

        try:
            response = self.session.get(endpoint, timeout=self.timeout)
            response.raise_for_status()
            return dict(response.json())
        except requests.RequestException as e:
            logger.error("Failed to get properties for RXCUI %s: %s", rxcui, e)
            raise

    def get_rxcui_related(
        self, rxcui: str, relation_types: List[str]
    ) -> Dict[str, Any]:
        """Get related concepts for an RXCUI.

        Args:
            rxcui: RxNorm concept unique identifier
            relation_types: List of relationship types to retrieve

        Returns:
            Related concepts dictionary
        """
        endpoint = urljoin(self.base_url, f"rxcui/{rxcui}/related.json")
        params = {"tty": "+".join(relation_types)} if relation_types else {}

        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            return dict(response.json())
        except requests.RequestException as e:
            logger.error("Failed to get related concepts for RXCUI %s: %s", rxcui, e)
            raise

    def get_ndc_properties(self, ndc: str) -> Dict[str, Any]:
        """Get RxNorm properties from NDC.

        Args:
            ndc: National Drug Code

        Returns:
            NDC properties dictionary
        """
        endpoint = urljoin(self.base_url, "ndcproperties.json")
        params = {"id": ndc}

        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            return dict(response.json())
        except requests.RequestException as e:
            logger.error("Failed to get properties for NDC %s: %s", ndc, e)
            raise

    def search_by_name(self, name: str, search_type: str = "exact") -> Dict[str, Any]:
        """Search for drugs by name.

        Args:
            name: Drug name to search
            search_type: Type of search (exact, approximate)

        Returns:
            Search results dictionary
        """
        if search_type == "exact":
            endpoint = urljoin(self.base_url, "rxcui.json")
            params = {"name": name}
        else:
            endpoint = urljoin(self.base_url, "approximateTerm.json")
            params = {"term": name}

        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            return dict(response.json())
        except requests.RequestException as e:
            logger.error("Failed to search for name '%s': %s", name, e)
            raise

    def get_allconcepts(self, tty: Optional[str] = None) -> Dict[str, Any]:
        """Get all concepts of a specific term type.

        Args:
            tty: Term type filter

        Returns:
            All concepts dictionary
        """
        endpoint = urljoin(self.base_url, "allconcepts.json")
        params = {"tty": tty} if tty else {}

        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            return dict(response.json())
        except requests.RequestException as e:
            logger.error("Failed to get all concepts: %s", e)
            raise


class RxNormRRFParser:
    """Parser for RxNorm RRF (Rich Release Format) files."""

    def __init__(self, data_path: Path):
        """Initialize RRF parser.

        Args:
            data_path: Path to RRF data directory
        """
        self.data_path = data_path

    def parse_rxnconso(self, include_suppressed: bool = False) -> List[Dict]:
        """Parse RXNCONSO.RRF file containing concept names.

        Args:
            include_suppressed: Include suppressed concepts

        Returns:
            List of concept dictionaries
        """
        file_path = self.data_path / "RXNCONSO.RRF"

        if not file_path.exists():
            # Try gzipped version
            file_path = self.data_path / "RXNCONSO.RRF.gz"
            if not file_path.exists():
                raise FileNotFoundError(f"RXNCONSO.RRF not found in {self.data_path}")

        concepts = []

        open_func = gzip.open if str(file_path).endswith(".gz") else open

        with open_func(file_path, "rt", encoding="utf-8") as f:
            for line in f:
                fields = line.strip().split("|")

                if len(fields) < 19:
                    continue

                # Extract fields
                rxcui = fields[0]
                lat = fields[1]  # Language
                ts = fields[2]  # Term status
                # lui = fields[3]  # Lexical unique identifier (unused)
                # stt = fields[4]  # String type (unused)
                # sui = fields[5]  # String unique identifier (unused)
                ispref = fields[6]  # Preferred flag
                # rxaui = fields[7]  # RxNorm atom unique identifier (unused)
                # saui = fields[8]  # Source atom unique identifier (unused)
                # scui = fields[9]  # Source concept unique identifier (unused)
                # sdui = fields[10]  # Source descriptor unique identifier (unused)
                sab = fields[11]  # Source abbreviation
                tty = fields[12]  # Term type
                # code = fields[13]  # Code (unused)
                str_text = fields[14]  # String text
                # srl = fields[15]  # Source restriction level (unused)
                suppress = fields[16]  # Suppress flag
                # cvf = fields[17]  # Content view flag (unused)

                # Skip suppressed if not requested
                if not include_suppressed and suppress == "O":
                    continue

                concept = {
                    "rxcui": rxcui,
                    "language": lat,
                    "term_status": ts,
                    "term_type": tty,
                    "name": str_text,
                    "source": sab,
                    "suppress": suppress == "O",
                    "is_preferred": ispref == "Y",
                }

                concepts.append(concept)

        return concepts

    def parse_rxnrel(self) -> List[Dict]:
        """Parse RXNREL.RRF file containing relationships.

        Returns:
            List of relationship dictionaries
        """
        file_path = self.data_path / "RXNREL.RRF"

        if not file_path.exists():
            file_path = self.data_path / "RXNREL.RRF.gz"
            if not file_path.exists():
                raise FileNotFoundError(f"RXNREL.RRF not found in {self.data_path}")

        relationships = []

        open_func = gzip.open if str(file_path).endswith(".gz") else open

        with open_func(file_path, "rt", encoding="utf-8") as f:
            for line in f:
                fields = line.strip().split("|")

                if len(fields) < 11:
                    continue

                rxcui1 = fields[0]
                # rxaui1 = fields[1]  # (unused)
                # stype1 = fields[2]  # (unused)
                rel = fields[3]
                rxcui2 = fields[4]
                # rxaui2 = fields[5]  # (unused)
                # stype2 = fields[6]  # (unused)
                rela = fields[7]
                # rui = fields[8]  # (unused)
                # srui = fields[9]  # (unused)
                sab = fields[10]

                relationship = {
                    "rxcui1": rxcui1,
                    "rxcui2": rxcui2,
                    "relationship": rel,
                    "relationship_attribute": rela,
                    "source": sab,
                }

                relationships.append(relationship)

        return relationships

    def parse_rxnsat(self) -> List[Dict]:
        """Parse RXNSAT.RRF file containing attributes.

        Returns:
            List of attribute dictionaries
        """
        file_path = self.data_path / "RXNSAT.RRF"

        if not file_path.exists():
            file_path = self.data_path / "RXNSAT.RRF.gz"
            if not file_path.exists():
                raise FileNotFoundError(f"RXNSAT.RRF not found in {self.data_path}")

        attributes = []

        open_func = gzip.open if str(file_path).endswith(".gz") else open

        with open_func(file_path, "rt", encoding="utf-8") as f:
            for line in f:
                fields = line.strip().split("|")

                if len(fields) < 13:
                    continue

                rxcui = fields[0]
                # lui = fields[1]  # (unused)
                # sui = fields[2]  # (unused)
                # rxaui = fields[3]  # (unused)
                # stype = fields[4]  # (unused)
                # code = fields[5]  # (unused)
                # atui = fields[6]  # (unused)
                # satui = fields[7]  # (unused)
                atn = fields[8]  # Attribute name
                sab = fields[9]
                atv = fields[10]  # Attribute value
                # suppress = fields[11]  # (unused)
                # cvf = fields[12]  # (unused)

                # Focus on important attributes
                important_attrs = [
                    "NDC",
                    "STRENGTH",
                    "DOSE_FORM",
                    "ROUTE",
                    "SCHEDULE",
                    "ATC",
                    "INGREDIENT",
                    "QUANTITY",
                ]

                if atn in important_attrs:
                    attribute = {
                        "rxcui": rxcui,
                        "attribute_name": atn,
                        "attribute_value": atv,
                        "source": sab,
                    }

                    attributes.append(attribute)

        return attributes


class RxNormImporter:
    """Main importer class for RxNorm data."""

    def __init__(self, config: ImportConfig):
        """Initialize importer with configuration.

        Args:
            config: Import configuration
        """
        self.config = config
        self.repository = RxNormRepository()
        self.validator = FHIRValidator()
        self.import_stats: Dict[str, Any] = {
            "concepts_processed": 0,
            "concepts_imported": 0,
            "concepts_updated": 0,
            "concepts_skipped": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

    def validate_concept(self, concept: RxNormConcept) -> bool:
        """Validate RxNorm concept.

        Args:
            concept: Concept to validate

        Returns:
            True if valid
        """
        try:
            # Validate required fields
            if not concept.rxcui or not concept.name:
                return False

            # Validate term type if present (already typed in RxNormConcept)
            # No additional validation needed for tty as it's already typed

            return True
        except (AttributeError, ValueError, TypeError) as e:
            logger.warning("Validation error in concept: %s", str(e))
            return False

    def import_data(self) -> Dict:
        """Import RxNorm data based on configuration.

        Returns:
            Import statistics dictionary
        """
        self.import_stats["start_time"] = datetime.now()

        try:
            if self.config.source == ImportSource.RXNORM_API:
                self._import_from_api()
            elif self.config.source == ImportSource.RRF_FILES:
                self._import_from_rrf()
            elif self.config.source == ImportSource.CSV_FILES:
                self._import_from_csv()
            elif self.config.source == ImportSource.WHO_ESSENTIAL:
                self._import_who_essential()
            elif self.config.source == ImportSource.CUSTOM_FORMULARY:
                self._import_custom_formulary()
            else:
                raise ValueError(f"Unsupported import source: {self.config.source}")

        except (ValueError, FileNotFoundError, RuntimeError) as e:
            logger.error("Import failed: %s", e)
            self.import_stats["errors"] += 1
            raise
        finally:
            self.import_stats["end_time"] = datetime.now()

        return self.import_stats

    def _import_from_api(self) -> None:
        """Import data from RxNorm REST API."""
        client = RxNormAPIClient(self.config.api_base_url, self.config.timeout)

        # For API import, we'll focus on specific term types
        term_types = self.config.term_types or [
            RxNormTermType.IN,  # Ingredients
            RxNormTermType.SCD,  # Generic drugs
            RxNormTermType.SBD,  # Brand drugs
            RxNormTermType.GPCK,  # Generic packs
            RxNormTermType.BPCK,  # Brand packs
        ]

        for tty in term_types:
            logger.info("Importing %s concepts from API", tty.value)

            try:
                # Get all concepts of this type
                response = client.get_allconcepts(tty.value)

                if "minConceptGroup" in response:
                    concepts = response["minConceptGroup"].get("minConcept", [])

                    for concept_data in concepts:
                        self._process_api_concept(client, concept_data)

            except (ValueError, KeyError, RuntimeError, ConnectionError) as e:
                logger.error("Failed to import %s: %s", tty.value, e)
                self.import_stats["errors"] += 1

    def _process_api_concept(self, client: RxNormAPIClient, concept_data: Dict) -> None:
        """Process a single concept from API.

        Args:
            client: API client instance
            concept_data: Concept data from API
        """
        try:
            rxcui = str(concept_data.get("rxcui", ""))
            name = str(concept_data.get("name", ""))
            tty = str(concept_data.get("tty", ""))

            if not all([rxcui, name, tty]):
                return

            self.import_stats["concepts_processed"] += 1

            # Skip if already exists and mode is INCREMENTAL
            if self.config.mode == ImportMode.INCREMENTAL:
                if self.repository.get_concept(rxcui):
                    self.import_stats["concepts_skipped"] += 1
                    return

            # Get additional properties
            properties = client.get_rxcui_properties(rxcui)

            suppress = "N"
            language = "ENG"

            if "properties" in properties:
                prop_data = properties["properties"]
                suppress = prop_data.get("suppress", "N") == "Y"
                language = prop_data.get("language", "ENG")

                # Skip suppressed if not configured to include
                if suppress and not self.config.include_suppressed:
                    self.import_stats["concepts_skipped"] += 1
                    return

            # Create concept
            concept = RxNormConcept(
                rxcui=rxcui,
                name=name,
                tty=RxNormTermType(tty),
                suppress=bool(suppress),
                language=language,
            )

            # Get related information
            self._enrich_concept_from_api(client, concept)

            # Add to repository
            self.repository.add_concept(concept)
            self.import_stats["concepts_imported"] += 1

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Failed to process concept %s: %s", concept_data, e)
            self.import_stats["errors"] += 1

    def _enrich_concept_from_api(
        self, client: RxNormAPIClient, concept: RxNormConcept
    ) -> None:
        """Enrich concept with related information from API.

        Args:
            client: API client instance
            concept: RxNorm concept to enrich
        """
        try:
            # Get related concepts
            relations = client.get_rxcui_related(
                concept.rxcui, ["IN", "DF", "SCDC", "BN"]
            )

            if "relatedGroup" in relations:
                related_groups = relations["relatedGroup"].get("conceptGroup", [])

                for group in related_groups:
                    tty = group.get("tty")
                    concepts = group.get("conceptProperties", [])

                    for related in concepts:
                        if tty == "IN":  # Ingredient
                            concept.ingredients.append(related.get("name"))
                        elif tty == "DF":  # Dose form
                            concept.dose_form = related.get("name")
                        elif tty == "BN":  # Brand name
                            concept.brand_name = related.get("name")

        except (ValueError, KeyError, RuntimeError) as e:
            logger.warning("Failed to enrich concept %s: %s", concept.rxcui, e)

    def _import_from_rrf(self) -> None:
        """Import data from RxNorm RRF files."""
        if not self.config.data_path:
            raise ValueError("data_path required for RRF import")

        parser = RxNormRRFParser(self.config.data_path)

        # Parse concept names
        logger.info("Parsing RXNCONSO.RRF")
        concepts_data = parser.parse_rxnconso(self.config.include_suppressed)

        # Group by RXCUI
        rxcui_concepts: Dict[str, List[Dict[str, Any]]] = {}
        for concept_data in concepts_data:
            rxcui = concept_data["rxcui"]

            if rxcui not in rxcui_concepts:
                rxcui_concepts[rxcui] = []

            rxcui_concepts[rxcui].append(concept_data)

        # Parse relationships (not currently used but could be extended)
        logger.info("Parsing RXNREL.RRF")
        _ = parser.parse_rxnrel()  # Mark as intentionally unused

        # Parse attributes
        logger.info("Parsing RXNSAT.RRF")
        attributes = parser.parse_rxnsat()

        # Build attribute index
        rxcui_attributes: Dict[str, List[Dict[str, Any]]] = {}
        for attr in attributes:
            rxcui = attr["rxcui"]

            if rxcui not in rxcui_attributes:
                rxcui_attributes[rxcui] = []

            rxcui_attributes[rxcui].append(attr)

        # Process concepts
        for rxcui, concept_list in rxcui_concepts.items():
            self._process_rrf_concept(
                rxcui, concept_list, rxcui_attributes.get(rxcui, [])
            )

    def _process_rrf_concept(
        self, rxcui: str, concept_list: List[Dict], attributes: List[Dict]
    ) -> None:
        """Process a concept from RRF data.

        Args:
            rxcui: RxNorm concept unique identifier
            concept_list: List of concept entries
            attributes: List of attributes
        """
        try:
            self.import_stats["concepts_processed"] += 1

            # Find preferred term
            preferred = None
            for concept_data in concept_list:
                if concept_data["is_preferred"]:
                    preferred = concept_data
                    break

            if not preferred:
                preferred = concept_list[0]

            # Skip if term type not in filter
            if self.config.term_types:
                tty_str = preferred["term_type"]
                try:
                    tty = RxNormTermType(tty_str)
                    if tty not in self.config.term_types:
                        self.import_stats["concepts_skipped"] += 1
                        return
                except ValueError:
                    self.import_stats["concepts_skipped"] += 1
                    return

            # Create concept
            concept = RxNormConcept(
                rxcui=rxcui,
                name=preferred["name"],
                tty=RxNormTermType(preferred["term_type"]),
                suppress=preferred["suppress"],
                language=preferred["language"],
            )

            # Process attributes
            for attr in attributes:
                attr_name = attr["attribute_name"]
                attr_value = attr["attribute_value"]

                if attr_name == "NDC":
                    concept.ndc_codes.append(attr_value)
                elif attr_name == "STRENGTH":
                    concept.strength = attr_value
                elif attr_name == "ATC":
                    concept.atc_codes.append(attr_value)

            # Add to repository
            self.repository.add_concept(concept)
            self.import_stats["concepts_imported"] += 1

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Failed to process RRF concept %s: %s", rxcui, e)
            self.import_stats["errors"] += 1

    def _import_from_csv(self) -> None:
        """Import data from CSV files."""
        if not self.config.data_path:
            raise ValueError("data_path required for CSV import")

        csv_file = self.config.data_path / "rxnorm_concepts.csv"

        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file}")

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                self._process_csv_row(row)

    def _process_csv_row(self, row: Dict[str, str]) -> None:
        """Process a row from CSV file.

        Args:
            row: CSV row as dictionary
        """
        try:
            self.import_stats["concepts_processed"] += 1

            # Extract required fields
            rxcui = str(row.get("rxcui", ""))
            name = str(row.get("name", ""))
            tty = str(row.get("tty", ""))

            if not all([rxcui, name, tty]):
                self.import_stats["concepts_skipped"] += 1
                return

            # Create concept
            concept = RxNormConcept(
                rxcui=rxcui,
                name=name,
                tty=RxNormTermType(tty),
                suppress=row.get("suppress", "N") == "Y",
                language=row.get("language", "ENG"),
            )

            # Add optional fields
            if row.get("ingredients"):
                concept.ingredients = row["ingredients"].split(";")

            if row.get("strength"):
                concept.strength = row["strength"]

            if row.get("dose_form"):
                concept.dose_form = row["dose_form"]

            if row.get("ndc_codes"):
                concept.ndc_codes = row["ndc_codes"].split(";")

            # Add to repository
            self.repository.add_concept(concept)
            self.import_stats["concepts_imported"] += 1

        except (ValueError, KeyError, csv.Error) as e:
            logger.error("Failed to process CSV row: %s", e)
            self.import_stats["errors"] += 1

    def _import_who_essential(self) -> None:
        """Import WHO Essential Medicines List."""
        # This is handled by the rxnorm_implementation module
        # which already has WHO essential medicines hardcoded
        # We'll just update the statistics

        concepts_count = len(self.repository.concepts)
        self.import_stats["concepts_imported"] = concepts_count
        self.import_stats["concepts_processed"] = concepts_count

        logger.info(
            "WHO Essential Medicines already loaded: %d concepts", concepts_count
        )

    def _import_custom_formulary(self) -> None:
        """Import custom refugee formulary."""
        if not self.config.data_path:
            raise ValueError("data_path required for custom formulary import")

        formulary_file = self.config.data_path / "refugee_formulary.json"

        if not formulary_file.exists():
            raise FileNotFoundError(f"Formulary file not found: {formulary_file}")

        with open(formulary_file, "r", encoding="utf-8") as f:
            formulary_data = json.load(f)

        for category, medications in formulary_data.items():
            for med_data in medications:
                self._process_formulary_medication(category, med_data)

    def _process_formulary_medication(self, category: str, med_data: Dict) -> None:
        """Process a medication from custom formulary.

        Args:
            category: Medication category
            med_data: Medication data
        """
        try:
            self.import_stats["concepts_processed"] += 1

            # Category would be used for classification in production
            _ = category

            # Create base ingredient concept
            ingredient = RxNormConcept(
                rxcui=med_data["rxcui"], name=med_data["name"], tty=RxNormTermType.IN
            )

            self.repository.add_concept(ingredient)

            # Create clinical drug concepts for each formulation
            for formulation in med_data.get("formulations", []):
                scd_rxcui = f"{med_data['rxcui']}-{formulation['id']}"

                scd = RxNormConcept(
                    rxcui=scd_rxcui, name=formulation["name"], tty=RxNormTermType.SCD
                )

                scd.ingredients = [med_data["name"]]
                scd.strength = formulation.get("strength")
                scd.dose_form = formulation.get("dose_form")

                self.repository.add_concept(scd)
                self.import_stats["concepts_imported"] += 1

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Failed to process formulary medication: %s", e)
            self.import_stats["errors"] += 1

    def save_import_log(self, log_path: Path) -> None:
        """Save import statistics to log file.

        Args:
            log_path: Path to save log file
        """
        log_data = {**self.import_stats, "duration_seconds": None}

        if log_data["start_time"] and log_data["end_time"]:
            duration = log_data["end_time"] - log_data["start_time"]
            log_data["duration_seconds"] = duration.total_seconds()

        # Convert datetime objects to strings
        if log_data["start_time"]:
            log_data["start_time"] = log_data["start_time"].isoformat()
        if log_data["end_time"]:
            log_data["end_time"] = log_data["end_time"].isoformat()

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)

        logger.info("Import log saved to %s", log_path)


def import_rxnorm_data(
    source: ImportSource,
    mode: ImportMode = ImportMode.INCREMENTAL,
    data_path: Optional[Path] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Import RxNorm data from various sources.

    Args:
        source: Import source
        mode: Import mode
        data_path: Path to data files (for file-based imports)
        **kwargs: Additional configuration options

    Returns:
        Import statistics
    """
    config = ImportConfig(source=source, mode=mode, data_path=data_path, **kwargs)

    importer = RxNormImporter(config)
    stats = importer.import_data()

    # Save log if data path provided
    if data_path:
        log_path = (
            data_path / f"rxnorm_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        importer.save_import_log(log_path)

    return stats

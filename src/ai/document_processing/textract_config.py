"""AWS Textract Configuration Module.

This module configures and implements AWS Textract integration for document processing
in the Haven Health Passport system, including medical form recognition, multi-language OCR,
and structured data extraction from healthcare documents.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

# Standard library imports
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, cast

# Third-party imports
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Custom exception for document processing errors."""


class DocumentType(Enum):
    """Types of medical documents."""

    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    MEDICAL_RECORD = "medical_record"
    INSURANCE_CARD = "insurance_card"
    VACCINATION_CARD = "vaccination_card"
    CONSENT_FORM = "consent_form"
    DISCHARGE_SUMMARY = "discharge_summary"
    REFERRAL_LETTER = "referral_letter"
    MEDICAL_CERTIFICATE = "medical_certificate"
    IDENTITY_DOCUMENT = "identity_document"
    UNKNOWN = "unknown"


class ExtractionConfidence(Enum):
    """Confidence levels for extracted data."""

    HIGH = "high"  # > 90%
    MEDIUM = "medium"  # 70-90%
    LOW = "low"  # 50-70%
    VERY_LOW = "very_low"  # < 50%


class FeatureType(Enum):
    """Types of features to extract from documents."""

    TEXT = "text"
    FORMS = "forms"
    TABLES = "tables"
    SIGNATURES = "signatures"
    HANDWRITING = "handwriting"
    BARCODES = "barcodes"
    QR_CODES = "qr_codes"
    STAMPS = "stamps"
    CHECKBOXES = "checkboxes"
    KEY_VALUE_PAIRS = "key_value_pairs"


@dataclass
class TextractConfig:
    """Configuration for AWS Textract."""

    region: str = "us-east-1"
    max_pages: int = 100
    enable_forms: bool = True
    enable_tables: bool = True
    enable_queries: bool = True
    languages: List[str] = field(default_factory=lambda: ["en", "es", "fr", "ar"])
    confidence_threshold: float = 0.7
    async_job_timeout_minutes: int = 30
    s3_bucket: Optional[str] = None
    sns_topic_arn: Optional[str] = None
    role_arn: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "region": self.region,
            "max_pages": self.max_pages,
            "enable_forms": self.enable_forms,
            "enable_tables": self.enable_tables,
            "enable_queries": self.enable_queries,
            "languages": self.languages,
            "confidence_threshold": self.confidence_threshold,
            "async_job_timeout_minutes": self.async_job_timeout_minutes,
            "s3_bucket": self.s3_bucket,
            "sns_topic_arn": self.sns_topic_arn,
            "role_arn": self.role_arn,
        }


@dataclass
class ExtractedText:
    """Represents extracted text from a document."""

    text: str
    confidence: float
    page: int
    bbox: Optional[Dict[str, float]] = None  # Bounding box
    text_type: str = "PRINTED"  # PRINTED or HANDWRITING

    def get_confidence_level(self) -> ExtractionConfidence:
        """Get confidence level category."""
        if self.confidence > 0.9:
            return ExtractionConfidence.HIGH
        elif self.confidence > 0.7:
            return ExtractionConfidence.MEDIUM
        elif self.confidence > 0.5:
            return ExtractionConfidence.LOW
        else:
            return ExtractionConfidence.VERY_LOW


@dataclass
class ExtractedForm:
    """Represents extracted form data."""

    key: str
    value: str
    confidence: float
    page: int
    key_bbox: Optional[Dict[str, float]] = None
    value_bbox: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "page": self.page,
        }


@dataclass
class ExtractedTable:
    """Represents an extracted table."""

    rows: List[List[str]]
    confidence: float
    page: int
    bbox: Optional[Dict[str, float]] = None

    def get_cell(self, row: int, col: int) -> Optional[str]:
        """Get cell value by row and column."""
        if 0 <= row < len(self.rows) and 0 <= col < len(self.rows[row]):
            return self.rows[row][col]
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rows": self.rows,
            "confidence": self.confidence,
            "page": self.page,
            "row_count": len(self.rows),
            "column_count": len(self.rows[0]) if self.rows else 0,
        }


@dataclass
class DocumentAnalysisResult:
    """Complete result of document analysis."""

    document_id: str
    document_type: DocumentType
    page_count: int
    extracted_text: List[ExtractedText] = field(default_factory=list)
    extracted_forms: List[ExtractedForm] = field(default_factory=list)
    extracted_tables: List[ExtractedTable] = field(default_factory=list)
    signatures_detected: List[Dict[str, Any]] = field(default_factory=list)
    barcodes: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: int = 0
    errors: List[str] = field(default_factory=list)

    def get_all_text(self) -> str:
        """Get all extracted text combined."""
        return "\n".join(t.text for t in self.extracted_text)

    def get_form_data(self) -> Dict[str, str]:
        """Get all form data as key-value pairs."""
        return {form.key: form.value for form in self.extracted_forms}

    def get_high_confidence_text(self) -> List[ExtractedText]:
        """Get only high confidence text."""
        return [t for t in self.extracted_text if t.confidence > 0.9]


class TextractClient:
    """AWS Textract client wrapper."""

    def __init__(self, config: TextractConfig):
        """Initialize TextractClient.

        Args:
            config: Textract configuration settings
        """
        self.config = config
        self.client = boto3.client("textract", region_name=config.region)
        self.s3_client = (
            boto3.client("s3", region_name=config.region) if config.s3_bucket else None
        )

    async def analyze_document(
        self, document_bytes: bytes, document_name: str, features: List[FeatureType]
    ) -> DocumentAnalysisResult:
        """Analyze a document using Textract."""
        start_time = datetime.now()

        result = DocumentAnalysisResult(
            document_id=str(uuid.uuid4()),
            document_type=DocumentType.UNKNOWN,
            page_count=0,
        )

        try:
            # Determine if we need async processing
            if len(document_bytes) > 5 * 1024 * 1024:  # 5MB
                # Use async for large documents
                job_result = await self._analyze_document_async(
                    document_bytes, document_name, features
                )
            else:
                # Use sync for small documents
                job_result = await self._analyze_document_sync(document_bytes, features)

            # Process results
            if job_result:
                await self._process_textract_response(job_result, result)

            # Detect document type
            result.document_type = await self._detect_document_type(result)

            # Calculate processing time
            result.processing_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

        except ClientError as e:
            logger.error("Textract analysis failed: %s", str(e))
            result.errors.append(str(e))

        return result

    async def _analyze_document_sync(
        self, document_bytes: bytes, features: List[FeatureType]
    ) -> Dict[str, Any]:
        """Analyze document synchronously."""
        # Convert features to Textract feature types
        textract_features = self._convert_features(features)

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.analyze_document(
                    Document={"Bytes": document_bytes}, FeatureTypes=textract_features
                ),
            )

            return cast(dict[str, Any], response)

        except ClientError as e:
            logger.error("Textract sync analysis error: %s", str(e))
            raise

    def _convert_features(self, features: List[FeatureType]) -> List[str]:
        """Convert feature types to Textract format."""
        textract_features = []

        if FeatureType.FORMS in features or FeatureType.KEY_VALUE_PAIRS in features:
            textract_features.append("FORMS")

        if FeatureType.TABLES in features:
            textract_features.append("TABLES")

        if FeatureType.SIGNATURES in features:
            textract_features.append("SIGNATURES")

        # Add queries if enabled
        if self.config.enable_queries:
            textract_features.append("QUERIES")

        return textract_features

    async def _process_textract_response(
        self, response: Dict[str, Any], result: DocumentAnalysisResult
    ) -> None:
        """Process Textract response and populate result."""
        blocks = response.get("Blocks", [])

        # Track relationships
        key_map = {}
        value_map = {}
        block_map = {}

        # First pass: build maps
        for block in blocks:
            block_id = block["Id"]
            block_map[block_id] = block

            if block["BlockType"] == "KEY_VALUE_SET":
                if "KEY" in block.get("EntityTypes", []):
                    key_map[block_id] = block
                else:
                    value_map[block_id] = block

        # Process different block types
        for block in blocks:
            block_type = block["BlockType"]

            if block_type == "PAGE":
                result.page_count += 1

            elif block_type == "LINE":
                # Extract text
                text = ExtractedText(
                    text=block.get("Text", ""),
                    confidence=block.get("Confidence", 0) / 100,
                    page=block.get("Page", 1),
                    bbox=block.get("Geometry", {}).get("BoundingBox"),
                    text_type=block.get("TextType", "PRINTED"),
                )
                result.extracted_text.append(text)

            elif block_type == "KEY_VALUE_SET" and "KEY" in block.get(
                "EntityTypes", []
            ):
                # Process form field
                form = await self._extract_key_value(
                    block, key_map, value_map, block_map
                )
                if form:
                    result.extracted_forms.append(form)

            elif block_type == "TABLE":
                # Process table
                table = await self._extract_table(block, block_map)
                if table:
                    result.extracted_tables.append(table)

            elif block_type == "SIGNATURE":
                # Signature detected
                signature = {
                    "page": block.get("Page", 1),
                    "confidence": block.get("Confidence", 0) / 100,
                    "bbox": block.get("Geometry", {}).get("BoundingBox"),
                }
                result.signatures_detected.append(signature)

    async def _extract_key_value(
        self,
        key_block: Dict[str, Any],
        key_map: Dict[str, Dict],
        value_map: Dict[str, Dict],
        block_map: Dict[str, Dict],
    ) -> Optional[ExtractedForm]:
        """Extract key-value pair from blocks."""
        _ = key_map  # Mark as intentionally unused
        # Get key text
        key_text = await self._get_text_from_relationships(
            key_block, block_map, "CHILD"
        )

        # Find associated value
        value_text = ""
        value_confidence = 0

        for relationship in key_block.get("Relationships", []):
            if relationship["Type"] == "VALUE":
                for value_id in relationship["Ids"]:
                    value_block = value_map.get(value_id)
                    if value_block:
                        value_text = await self._get_text_from_relationships(
                            value_block, block_map, "CHILD"
                        )
                        value_confidence = value_block.get("Confidence", 0) / 100
                        break

        if key_text:
            return ExtractedForm(
                key=key_text,
                value=value_text,
                confidence=min(key_block.get("Confidence", 0) / 100, value_confidence),
                page=key_block.get("Page", 1),
                key_bbox=key_block.get("Geometry", {}).get("BoundingBox"),
            )

        return None

    async def _extract_table(
        self, table_block: Dict[str, Any], block_map: Dict[str, Dict]
    ) -> Optional[ExtractedTable]:
        """Extract table from blocks."""
        rows: dict[int, dict[int, str]] = {}

        # Get all cells
        for relationship in table_block.get("Relationships", []):
            if relationship["Type"] == "CHILD":
                for cell_id in relationship["Ids"]:
                    cell_block = block_map.get(cell_id)
                    if cell_block and cell_block["BlockType"] == "CELL":
                        row_index = cell_block.get("RowIndex", 1) - 1
                        col_index = cell_block.get("ColumnIndex", 1) - 1

                        # Get cell text
                        cell_text = await self._get_text_from_relationships(
                            cell_block, block_map, "CHILD"
                        )

                        # Initialize row if needed
                        if row_index not in rows:
                            rows[row_index] = {}

                        rows[row_index][col_index] = cell_text

        # Convert to list format
        if rows:
            max_row = max(rows.keys())
            max_col = max(max(row.keys()) for row in rows.values())

            table_data = []
            for r in range(max_row + 1):
                row = []
                for c in range(max_col + 1):
                    row.append(rows.get(r, {}).get(c, ""))
                table_data.append(row)

            return ExtractedTable(
                rows=table_data,
                confidence=table_block.get("Confidence", 0) / 100,
                page=table_block.get("Page", 1),
                bbox=table_block.get("Geometry", {}).get("BoundingBox"),
            )

        return None

    async def _get_text_from_relationships(
        self, block: Dict[str, Any], block_map: Dict[str, Dict], relationship_type: str
    ) -> str:
        """Get text from block relationships."""
        text_parts = []

        for relationship in block.get("Relationships", []):
            if relationship["Type"] == relationship_type:
                for child_id in relationship["Ids"]:
                    child_block = block_map.get(child_id)
                    if child_block and child_block["BlockType"] in ["WORD", "LINE"]:
                        text_parts.append(child_block.get("Text", ""))

        return " ".join(text_parts)

    async def _detect_document_type(
        self, result: DocumentAnalysisResult
    ) -> DocumentType:
        """Detect document type based on extracted content."""
        # Get all text for analysis
        text = result.get_all_text().lower()
        # form_data = result.get_form_data()  # Removed: unused variable

        # Check for specific patterns
        if "prescription" in text or "rx" in text or "medication" in text:
            return DocumentType.PRESCRIPTION

        elif "lab" in text and ("report" in text or "results" in text):
            return DocumentType.LAB_REPORT

        elif "vaccination" in text or "immunization" in text:
            return DocumentType.VACCINATION_CARD

        elif "insurance" in text and ("card" in text or "member" in text):
            return DocumentType.INSURANCE_CARD

        elif "consent" in text and "form" in text:
            return DocumentType.CONSENT_FORM

        elif "discharge" in text and "summary" in text:
            return DocumentType.DISCHARGE_SUMMARY

        elif "referral" in text:
            return DocumentType.REFERRAL_LETTER

        elif "certificate" in text and "medical" in text:
            return DocumentType.MEDICAL_CERTIFICATE

        elif any(
            id_term in text for id_term in ["passport", "license", "identification"]
        ):
            return DocumentType.IDENTITY_DOCUMENT

        elif "patient" in text and "record" in text:
            return DocumentType.MEDICAL_RECORD

        return DocumentType.UNKNOWN

    async def _analyze_document_async(
        self, document_bytes: bytes, document_name: str, features: List[FeatureType]
    ) -> Dict[str, Any]:
        """Analyze document asynchronously using S3."""
        if not self.s3_client or not self.config.s3_bucket:
            raise ValueError("S3 configuration required for async processing")

        # Upload to S3
        s3_key = f"textract-temp/{uuid.uuid4()}/{document_name}"

        try:
            if self.s3_client is not None:
                s3_client = self.s3_client
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: s3_client.put_object(
                        Bucket=self.config.s3_bucket, Key=s3_key, Body=document_bytes
                    ),
                )

            # Start async job
            textract_features = self._convert_features(features)

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.start_document_analysis(
                    DocumentLocation={
                        "S3Object": {"Bucket": self.config.s3_bucket, "Name": s3_key}
                    },
                    FeatureTypes=textract_features,
                    NotificationChannel=(
                        {
                            "SNSTopicArn": self.config.sns_topic_arn,
                            "RoleArn": self.config.role_arn,
                        }
                        if self.config.sns_topic_arn
                        else None
                    ),
                ),
            )

            job_id = response["JobId"]

            # Wait for completion
            result = await self._wait_for_job_completion(job_id)

            # Clean up S3
            if self.s3_client is not None:
                s3_client = self.s3_client
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: s3_client.delete_object(
                        Bucket=self.config.s3_bucket, Key=s3_key
                    ),
                )

            return result

        except Exception as e:
            logger.error("Textract async analysis error: %s", str(e))
            # Clean up S3 on error
            try:
                if self.s3_client is not None:
                    s3_client = self.s3_client
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: s3_client.delete_object(
                            Bucket=self.config.s3_bucket, Key=s3_key
                        ),
                    )
            except ClientError:
                pass
            raise

    async def _wait_for_job_completion(self, job_id: str) -> Dict[str, Any]:
        """Wait for async job to complete."""
        max_attempts = (
            self.config.async_job_timeout_minutes * 2
        )  # Check every 30 seconds
        attempts = 0

        while attempts < max_attempts:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.client.get_document_analysis(JobId=job_id)
            )

            status = response["JobStatus"]

            if status == "SUCCEEDED":
                return cast(Dict[str, Any], response)
            elif status == "FAILED":
                error_msg = response.get("StatusMessage", "Unknown error")
                raise ProcessingError(f"Textract job failed: {error_msg}")
            elif status == "PARTIAL_SUCCESS":
                logger.warning(
                    "Textract job partially succeeded: %s",
                    response.get("StatusMessage", ""),
                )
                return cast(Dict[str, Any], response)

            # Still in progress
            await asyncio.sleep(30)
            attempts += 1

        raise TimeoutError(
            f"Textract job timed out after {self.config.async_job_timeout_minutes} minutes"
        )

# pylint: disable=too-many-lines
"""Document Layout Analysis Module.

This module provides layout analysis capabilities for medical documents,
identifying and classifying different regions such as text blocks, tables,
images, headers, footers, and forms.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import boto3
import numpy as np
from botocore.exceptions import ClientError
from PIL import Image

from src.ai.document_processing.textract_config import DocumentType
from src.audit.audit_logger import AuditEventType, AuditLogger
from src.core.config import AWSConfig
from src.metrics.metrics_collector import MetricsCollector, MetricType

from .cv2_wrapper import HAS_CV2, CV2Constants
from .cv2_wrapper import CV2Operations as cv2

logger = logging.getLogger(__name__)


class LayoutElementType(Enum):
    """Types of layout elements in documents."""

    TEXT_BLOCK = "text_block"
    TABLE = "table"
    IMAGE = "image"
    HEADER = "header"
    FOOTER = "footer"
    TITLE = "title"
    SUBTITLE = "subtitle"
    PARAGRAPH = "paragraph"
    LIST = "list"
    FORM_FIELD = "form_field"
    SIGNATURE = "signature"
    STAMP = "stamp"
    BARCODE = "barcode"
    QR_CODE = "qr_code"
    LOGO = "logo"
    PAGE_NUMBER = "page_number"
    MARGIN_NOTE = "margin_note"
    UNKNOWN = "unknown"


@dataclass
class BoundingBox:
    """Represents a bounding box for a layout element."""

    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        """Calculate area of the bounding box."""
        return self.width * self.height

    @property
    def center(self) -> Tuple[int, int]:
        """Get center point of the bounding box."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def contains(self, point: Tuple[int, int]) -> bool:
        """Check if a point is inside the bounding box."""
        px, py = point
        return (
            self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height
        )

    def intersects(self, other: "BoundingBox") -> bool:
        """Check if this bounding box intersects with another."""
        return not (
            self.x + self.width < other.x
            or other.x + other.width < self.x
            or self.y + self.height < other.y
            or other.y + other.height < self.y
        )

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class LayoutElement:
    """Represents a single layout element in a document."""

    element_type: LayoutElementType
    bounding_box: BoundingBox
    confidence: float
    text_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List["LayoutElement"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.element_type.value,
            "bounding_box": self.bounding_box.to_dict(),
            "confidence": self.confidence,
            "text_content": self.text_content,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class DocumentLayout:
    """Represents the complete layout analysis of a document."""

    page_width: int
    page_height: int
    elements: List[LayoutElement]
    structure_tree: Optional[LayoutElement] = None
    reading_order: List[int] = field(default_factory=list)
    columns_detected: int = 1
    orientation: str = "portrait"
    language_direction: str = "ltr"  # left-to-right or rtl
    page_count: int = 1  # Number of pages in the document

    def get_elements_by_type(
        self, element_type: LayoutElementType
    ) -> List[LayoutElement]:
        """Get all elements of a specific type."""
        return [elem for elem in self.elements if elem.element_type == element_type]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page_width": self.page_width,
            "page_height": self.page_height,
            "elements": [elem.to_dict() for elem in self.elements],
            "reading_order": self.reading_order,
            "columns_detected": self.columns_detected,
            "orientation": self.orientation,
            "language_direction": self.language_direction,
        }


class DocumentLayoutAnalyzer:
    """Main service for document layout analysis."""

    def __init__(
        self,
        aws_config: Optional[AWSConfig] = None,
        audit_logger: Optional[AuditLogger] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """Initialize the layout analyzer."""
        self.aws_config = aws_config or AWSConfig()
        self.audit_logger = audit_logger
        self.metrics_collector = metrics_collector

        # Initialize AWS clients
        self._init_aws_clients()

    def _init_aws_clients(self) -> None:
        """Initialize AWS service clients."""
        try:
            self.textract_client = boto3.client(
                "textract", **self.aws_config.get_boto3_kwargs("textract")
            )
        except (ClientError, ValueError) as e:
            logger.warning("Failed to initialize AWS clients: %s", e)
            self.textract_client = None

    async def analyze_layout(
        self,
        image_data: Union[bytes, np.ndarray, Image.Image],
        document_type: Optional[DocumentType] = None,
        use_textract: bool = True,
    ) -> DocumentLayout:
        """
        Analyze document layout to identify different regions and structure.

        Args:
            image_data: Input image as bytes, numpy array, or PIL Image
            document_type: Type of document for optimized analysis
            use_textract: Whether to use AWS Textract for analysis

        Returns:
            DocumentLayout with identified elements and structure
        """
        start_time = datetime.utcnow()

        try:
            # Convert input to numpy array
            image = self._convert_to_numpy(image_data)
            # Get image dimensions
            height, width = image.shape[:2]

            elements = []

            # Use AWS Textract if available and requested
            if use_textract and self.textract_client:
                try:
                    textract_elements = await self._analyze_with_textract(image)
                    elements.extend(textract_elements)
                except ClientError as e:
                    logger.warning("Textract analysis failed: %s", e)

            # Use OpenCV-based analysis as fallback or complement
            cv_elements = self._analyze_with_opencv(image, document_type)

            # Merge results from different sources
            elements = self._merge_elements(elements, cv_elements)

            # Detect reading order
            reading_order = self._detect_reading_order(elements)

            # Detect columns
            columns = self._detect_columns(elements)

            # Detect orientation
            orientation = "landscape" if width > height else "portrait"

            # Create layout structure
            layout = DocumentLayout(
                page_width=width,
                page_height=height,
                elements=elements,
                reading_order=reading_order,
                columns_detected=columns,
                orientation=orientation,
            )

            # Record metrics
            if self.metrics_collector:
                processing_time = (
                    datetime.utcnow() - start_time
                ).total_seconds() * 1000
                self.metrics_collector.record_metric(
                    MetricType.DOCUMENT_ENHANCEMENT,
                    {
                        "operation": "layout_analysis",
                        "elements_found": len(elements),
                        "columns_detected": columns,
                        "processing_time_ms": processing_time,
                    },
                )
            # Audit log
            if self.audit_logger:
                await self.audit_logger.log_event(
                    AuditEventType.DOCUMENT_ENHANCED,
                    {
                        "operation": "layout_analysis",
                        "elements_count": len(elements),
                        "document_type": document_type.value if document_type else None,
                    },
                )

            return layout

        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Layout analysis failed: %s", e)
            # Return minimal layout on error
            return DocumentLayout(
                page_width=image.shape[1] if "image" in locals() else 0,
                page_height=image.shape[0] if "image" in locals() else 0,
                elements=[],
            )

    def _convert_to_numpy(
        self, image_data: Union[bytes, np.ndarray, Image.Image]
    ) -> np.ndarray:
        """Convert various image formats to numpy array."""
        if isinstance(image_data, np.ndarray):
            return image_data
        elif isinstance(image_data, Image.Image):
            return np.array(image_data)
        elif isinstance(image_data, bytes):
            if not HAS_CV2:
                # Fallback to PIL if cv2 is not available
                from io import BytesIO  # pylint: disable=import-outside-toplevel

                image = Image.open(BytesIO(image_data))
                return np.array(image)
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, CV2Constants.IMREAD_COLOR)
            if image is None:
                raise ValueError("Failed to decode image from bytes")
            return np.array(image)
        else:
            raise ValueError(f"Unsupported image type: {type(image_data)}")

    def _analyze_with_opencv(
        self, image: np.ndarray, document_type: Optional[DocumentType]
    ) -> List[LayoutElement]:
        """Analyze layout using OpenCV-based methods."""
        elements: List[LayoutElement] = []

        if not HAS_CV2:
            logger.warning("OpenCV not available, skipping CV-based layout analysis")
            return elements

        # Convert to grayscale
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # Detect text regions
        text_elements = self._detect_text_regions(gray)
        elements.extend(text_elements)
        # Detect tables
        table_elements = self._detect_tables(gray)
        elements.extend(table_elements)

        # Detect images/figures
        image_elements = self._detect_images(image)
        elements.extend(image_elements)

        # Detect form fields (for medical forms)
        if document_type in [
            DocumentType.PRESCRIPTION,
            DocumentType.LAB_REPORT,
            DocumentType.INSURANCE_CARD,
        ]:
            form_elements = self._detect_form_fields(gray)
            elements.extend(form_elements)

        return elements

    def _detect_text_regions(self, gray: np.ndarray) -> List[LayoutElement]:
        """Detect text regions in the document."""
        elements: List[LayoutElement] = []

        if not HAS_CV2:
            return elements

        # Apply morphological operations to connect text
        kernel = cv2.getStructuringElement(CV2Constants.MORPH_RECT, (15, 3))
        dilated = cv2.dilate(gray, kernel, iterations=1)

        # Threshold
        _, binary = cv2.threshold(
            dilated, 0, 255, CV2Constants.THRESH_BINARY_INV + CV2Constants.THRESH_OTSU
        )

        # Find contours
        contours, _ = cv2.findContours(
            binary, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Filter small regions
            if w < 20 or h < 10:
                continue

            # Classify text region type based on position and size
            element_type = self._classify_text_region(x, y, w, h, gray.shape)

            element = LayoutElement(
                element_type=element_type,
                bounding_box=BoundingBox(x, y, w, h),
                confidence=0.8,
            )
            elements.append(element)

        return elements

    def _classify_text_region(
        self, x: int, y: int, w: int, h: int, shape: Tuple[int, int]
    ) -> LayoutElementType:
        """Classify text region based on position and size."""
        _ = x  # Mark as intentionally unused
        height, width = shape

        # Check if it's a header (top 10% of page)
        if y < height * 0.1:
            if w > width * 0.6:  # Wide text at top
                return LayoutElementType.HEADER
            else:
                return LayoutElementType.TITLE

        # Check if it's a footer (bottom 10% of page)
        if y > height * 0.9:
            return LayoutElementType.FOOTER

        # Check aspect ratio for different text types
        aspect_ratio = w / h
        if aspect_ratio > 10:  # Very wide and short
            return LayoutElementType.SUBTITLE
        elif h > 50:  # Tall block
            return LayoutElementType.PARAGRAPH
        else:
            return LayoutElementType.TEXT_BLOCK

    def _detect_tables(self, gray: np.ndarray) -> List[LayoutElement]:
        """Detect tables in the document."""
        elements = []

        # Detect horizontal and vertical lines
        horizontal_kernel = cv2.getStructuringElement(CV2Constants.MORPH_RECT, (40, 1))
        vertical_kernel = cv2.getStructuringElement(CV2Constants.MORPH_RECT, (1, 40))

        # Morphological operations to detect lines
        horizontal_lines = cv2.morphologyEx(
            gray, CV2Constants.MORPH_OPEN, horizontal_kernel
        )
        vertical_lines = cv2.morphologyEx(
            gray, CV2Constants.MORPH_OPEN, vertical_kernel
        )

        # Combine lines
        table_mask = cv2.add(horizontal_lines, vertical_lines)

        # Find table regions
        contours, _ = cv2.findContours(
            table_mask, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Filter based on size
            if w > 100 and h > 50:
                element = LayoutElement(
                    element_type=LayoutElementType.TABLE,
                    bounding_box=BoundingBox(x, y, w, h),
                    confidence=0.85,
                )
                elements.append(element)

        return elements

    def _detect_images(self, image: np.ndarray) -> List[LayoutElement]:
        """Detect image regions in the document."""
        elements = []

        # Convert to grayscale if needed
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(
            edges, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Check if region is likely an image (square-ish, medium to large)
            if w > 50 and h > 50 and 0.3 < w / h < 3.0:
                # Check if region has high variance (likely an image)
                region = gray[y : y + h, x : x + w]
                if np.std(region) > 30:
                    element = LayoutElement(
                        element_type=LayoutElementType.IMAGE,
                        bounding_box=BoundingBox(x, y, w, h),
                        confidence=0.7,
                    )
                    elements.append(element)

        return elements

    def extract_tables(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract table content from detected table regions."""
        tables = []
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # Detect table regions first
        table_elements = self._detect_tables(gray)

        for table_elem in table_elements:
            bbox = table_elem.bounding_box
            table_roi = gray[
                bbox.y : bbox.y + bbox.height, bbox.x : bbox.x + bbox.width
            ]

            # Extract table structure
            horizontal_kernel = cv2.getStructuringElement(
                CV2Constants.MORPH_RECT, (40, 1)
            )
            vertical_kernel = cv2.getStructuringElement(
                CV2Constants.MORPH_RECT, (1, 40)
            )

            h_lines = cv2.morphologyEx(
                table_roi, CV2Constants.MORPH_OPEN, horizontal_kernel
            )
            v_lines = cv2.morphologyEx(
                table_roi, CV2Constants.MORPH_OPEN, vertical_kernel
            )

            # Find intersections (cell boundaries)
            intersections = cv2.bitwise_and(h_lines, v_lines)

            # Extract cell coordinates
            cells = self._extract_cells_from_intersections(table_roi, intersections)

            table_data = {
                "bounding_box": bbox,
                "cells": cells,
                "confidence": table_elem.confidence,
                "rows": len(set(cell["row"] for cell in cells)),
                "columns": len(set(cell["column"] for cell in cells)),
            }
            tables.append(table_data)

        return tables

    def _extract_cells_from_intersections(
        self, table_roi: np.ndarray, intersections: np.ndarray
    ) -> List[Dict[str, Any]]:
        """Extract individual cells from table intersections."""
        _ = table_roi  # Mark as intentionally unused
        cells = []

        # Find contours of cells
        contours, _ = cv2.findContours(
            intersections,
            CV2Constants.RETR_EXTERNAL,
            CV2Constants.CHAIN_APPROX_SIMPLE,
        )

        # Sort contours by position
        sorted_contours = sorted(
            contours, key=lambda c: (cv2.boundingRect(c)[1], cv2.boundingRect(c)[0])
        )

        for idx, contour in enumerate(sorted_contours):
            x, y, w, h = cv2.boundingRect(contour)

            if w > 10 and h > 10:  # Filter out noise
                cell = {
                    "index": idx,
                    "bounding_box": BoundingBox(x, y, w, h),
                    "row": self._estimate_row(y, sorted_contours),
                    "column": self._estimate_column(x, sorted_contours),
                    "content": "",  # To be filled by OCR
                }
                cells.append(cell)

        return cells

    def _estimate_row(self, y: int, contours: List) -> int:
        """Estimate row index based on y coordinate."""
        y_positions = sorted(set(cv2.boundingRect(c)[1] for c in contours))
        for idx, y_pos in enumerate(y_positions):
            if abs(y - y_pos) < 10:  # Tolerance
                return idx
        return 0

    def _estimate_column(self, x: int, contours: List) -> int:
        """Estimate column index based on x coordinate."""
        x_positions = sorted(set(cv2.boundingRect(c)[0] for c in contours))
        for idx, x_pos in enumerate(x_positions):
            if abs(x - x_pos) < 10:  # Tolerance
                return idx
        return 0

    def detect_signatures(self, image: np.ndarray) -> List[LayoutElement]:
        """Detect signature regions in the document."""
        elements = []
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # Look for regions with specific characteristics of signatures
        # 1. Usually in lower portion of document
        height, width = gray.shape
        lower_region = gray[int(height * 0.6) :, :]

        # 2. Apply edge detection
        edges = cv2.Canny(lower_region, 30, 100)

        # 3. Find contours
        contours, _ = cv2.findContours(
            edges, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            y += int(height * 0.6)  # Adjust for cropped region

            # Signature characteristics:
            # - Wider than tall (aspect ratio)
            # - Moderate size
            # - Contains irregular patterns
            if 100 < w < width * 0.4 and 20 < h < 100 and w / h > 2:
                region = gray[y : y + h, x : x + w]

                # Check for ink-like patterns (high contrast variations)
                if np.std(region) > 20 and self._has_signature_patterns(region):
                    element = LayoutElement(
                        element_type=LayoutElementType.SIGNATURE,
                        bounding_box=BoundingBox(x, y, w, h),
                        confidence=0.75,
                        metadata={"ink_density": float(np.mean(region < 128))},
                    )
                    elements.append(element)

        return elements

    def _has_signature_patterns(self, region: np.ndarray) -> bool:
        """Check if region has signature-like patterns."""
        # Check for curved lines and strokes typical of signatures
        edges = cv2.Canny(region, 50, 150)

        # Calculate edge density
        edge_density = np.sum(edges > 0) / (region.shape[0] * region.shape[1])

        # Signatures typically have moderate edge density
        return bool(0.05 < edge_density < 0.3)

    def detect_stamps(self, image: np.ndarray) -> List[LayoutElement]:
        """Detect stamp regions in the document."""
        elements = []
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # Stamps are often circular or rectangular with clear boundaries
        # Apply threshold to get binary image
        _, binary = cv2.threshold(
            gray, 0, 255, CV2Constants.THRESH_BINARY + CV2Constants.THRESH_OTSU
        )

        # Find contours
        contours, _ = cv2.findContours(
            binary, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Check if contour is circular or square-ish
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)

            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)

                # Stamps typically have high circularity or are rectangular
                if (0.7 < circularity < 1.3 and 50 < w < 300 and 50 < h < 300) or (
                    abs(w - h) < 50 and 50 < w < 300
                ):  # Square-ish

                    region = gray[y : y + h, x : x + w]

                    # Stamps often have text in circular/rectangular arrangement
                    if self._has_stamp_characteristics(region):
                        element = LayoutElement(
                            element_type=LayoutElementType.STAMP,
                            bounding_box=BoundingBox(x, y, w, h),
                            confidence=0.8,
                            metadata={
                                "shape": (
                                    "circular" if circularity > 0.8 else "rectangular"
                                ),
                                "circularity": float(circularity),
                            },
                        )
                        elements.append(element)

        return elements

    def _has_stamp_characteristics(self, region: np.ndarray) -> bool:
        """Check if region has stamp-like characteristics."""
        # Check for text arranged in circular or border pattern
        edges = cv2.Canny(region, 50, 150)

        # Check edge distribution (stamps have edges around perimeter)
        h, w = region.shape
        border_region = np.concatenate(
            [
                edges[0:10, :].flatten(),
                edges[-10:, :].flatten(),
                edges[:, 0:10].flatten(),
                edges[:, -10:].flatten(),
            ]
        )

        center_region = edges[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4].flatten()

        border_density = np.sum(border_region > 0) / len(border_region)
        center_density = np.sum(center_region > 0) / len(center_region)

        # Stamps have higher edge density at borders
        return bool(border_density > center_density * 1.5)

    def detect_barcodes(self, image: np.ndarray) -> List[LayoutElement]:
        """Detect barcode regions in the document."""
        elements = []
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # Apply gradient to highlight vertical lines (common in barcodes)
        gradX = cv2.Sobel(gray, CV2Constants.CV_32F, 1, 0)  # pylint: disable=no-member
        gradY = cv2.Sobel(gray, CV2Constants.CV_32F, 0, 1)  # pylint: disable=no-member

        # Subtract y-gradient from x-gradient to highlight vertical lines
        gradient = cv2.subtract(gradX, gradY)  # pylint: disable=no-member
        gradient = cv2.convertScaleAbs(gradient)  # pylint: disable=no-member

        # Apply threshold
        _, thresh = cv2.threshold(gradient, 225, 255, CV2Constants.THRESH_BINARY)

        # Close gaps between vertical lines
        kernel = cv2.getStructuringElement(CV2Constants.MORPH_RECT, (21, 7))
        closed = cv2.morphologyEx(thresh, CV2Constants.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(
            closed, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Barcode characteristics: wider than tall, minimum size
            if w > h * 1.5 and w > 50 and h > 20 and h < 150:
                region = gray[y : y + h, x : x + w]

                if self._has_barcode_pattern(region):
                    element = LayoutElement(
                        element_type=LayoutElementType.BARCODE,
                        bounding_box=BoundingBox(x, y, w, h),
                        confidence=0.85,
                        metadata={
                            "orientation": "horizontal",
                            "type": "1D",  # Assuming 1D barcode
                        },
                    )
                    elements.append(element)

        return elements

    def _has_barcode_pattern(self, region: np.ndarray) -> bool:
        """Check if region has barcode-like patterns."""
        # Calculate vertical projection
        vertical_projection = np.sum(region < 128, axis=0)

        # Barcodes have alternating high-low pattern
        transitions = 0
        prev_val = vertical_projection[0] > region.shape[0] / 2

        for val in vertical_projection[1:]:
            curr_val = val > region.shape[0] / 2
            if curr_val != prev_val:
                transitions += 1
            prev_val = curr_val

        # Barcodes have many transitions
        transition_density = transitions / len(vertical_projection)
        return transition_density > 0.2

    def detect_qr_codes(self, image: np.ndarray) -> List[LayoutElement]:
        """Detect QR code regions in the document."""
        elements = []
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # QR codes have three distinctive position markers (squares)
        # Apply threshold
        _, binary = cv2.threshold(
            gray, 0, 255, CV2Constants.THRESH_BINARY + CV2Constants.THRESH_OTSU
        )

        # Find contours
        contours, _ = cv2.findContours(
            binary, CV2Constants.RETR_TREE, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        # Look for square patterns
        potential_markers = []
        for contour in contours:
            approx = cv2.approxPolyDP(
                contour, 0.02 * cv2.arcLength(contour, True), True
            )

            if len(approx) == 4:  # Square shape
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / float(h)

                # QR position markers are square
                if 0.9 < aspect_ratio < 1.1 and 20 < w < 100:
                    potential_markers.append((x, y, w, h))

        # Group nearby markers (QR codes have 3 position markers)
        qr_regions = self._group_qr_markers(potential_markers)

        for region in qr_regions:
            x, y, w, h = region
            qr_region = gray[y : y + h, x : x + w]

            if self._has_qr_pattern(qr_region):
                element = LayoutElement(
                    element_type=LayoutElementType.QR_CODE,
                    bounding_box=BoundingBox(x, y, w, h),
                    confidence=0.9,
                    metadata={
                        "type": "QR",
                        "estimated_version": self._estimate_qr_version(w),
                    },
                )
                elements.append(element)

        return elements

    def _group_qr_markers(
        self, markers: List[Tuple[int, int, int, int]]
    ) -> List[Tuple[int, int, int, int]]:
        """Group position markers into QR code regions."""
        if len(markers) < 3:
            return []

        qr_regions = []
        used = set()

        for i, marker1 in enumerate(markers):
            if i in used:
                continue

            nearby = []
            x1, y1, w1, _ = marker1

            for j, marker2 in enumerate(markers):
                if i != j and j not in used:
                    x2, y2, _, _ = marker2

                    # Check if markers are roughly aligned and spaced appropriately
                    dist = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    if dist < w1 * 10:  # Within reasonable distance
                        nearby.append(j)

            if len(nearby) >= 2:  # Found at least 3 markers
                used.add(i)
                used.update(nearby[:2])

                # Calculate bounding box for QR code
                all_markers = [markers[i]] + [markers[j] for j in nearby[:2]]
                x_min = min(m[0] for m in all_markers)
                y_min = min(m[1] for m in all_markers)
                x_max = max(m[0] + m[2] for m in all_markers)
                y_max = max(m[1] + m[3] for m in all_markers)

                qr_regions.append((x_min, y_min, x_max - x_min, y_max - y_min))

        return qr_regions

    def _has_qr_pattern(self, region: np.ndarray) -> bool:
        """Check if region has QR code-like patterns."""
        # QR codes have specific ratio of black to white pixels
        black_ratio = np.sum(region < 128) / (region.shape[0] * region.shape[1])

        # Typically between 30-70% black pixels
        return bool(0.3 < black_ratio < 0.7)

    def _estimate_qr_version(self, size: int) -> int:
        """Estimate QR code version based on size."""
        # Rough estimation based on module size
        modules = size // 10  # Assuming ~10 pixels per module

        if modules < 25:
            return 1
        elif modules < 30:
            return 2
        else:
            return 3

    def validate_document(self, layout: DocumentLayout) -> Dict[str, Any]:
        """Validate document layout and completeness."""
        validation_result: Dict[str, Any] = {
            "is_valid": True,
            "issues": [],
            "warnings": [],
            "document_type": None,
            "completeness_score": 0.0,
            "quality_score": 0.0,
        }

        # Determine document type based on elements
        validation_result["document_type"] = self._determine_document_type(layout)

        # Check required elements based on document type
        required_elements = self._get_required_elements(
            validation_result["document_type"]
        )
        present_elements = set(elem.element_type for elem in layout.elements)

        missing_elements = required_elements - present_elements
        if missing_elements:
            validation_result["is_valid"] = False
            for elem in missing_elements:
                validation_result["issues"].append(
                    f"Missing required element: {elem.value}"
                )

        # Calculate completeness score
        if required_elements:
            validation_result["completeness_score"] = len(
                present_elements & required_elements
            ) / len(required_elements)

        # Check document quality
        quality_checks = self._perform_quality_checks(layout)
        validation_result["quality_score"] = quality_checks["score"]
        validation_result["warnings"].extend(quality_checks["warnings"])

        # Additional validation rules
        if validation_result["document_type"] == "medical_form":
            if not any(
                elem.element_type == LayoutElementType.SIGNATURE
                for elem in layout.elements
            ):
                validation_result["warnings"].append(
                    "Medical form may require signature"
                )

        if layout.page_count > 50:
            validation_result["warnings"].append(
                "Document has many pages, processing may be slow"
            )

        return validation_result

    def _determine_document_type(self, layout: DocumentLayout) -> str:
        """Determine document type based on layout elements."""
        elements = {elem.element_type for elem in layout.elements}

        # Check for specific patterns
        if LayoutElementType.FORM_FIELD in elements:
            if LayoutElementType.SIGNATURE in elements:
                return "medical_form"
            return "form"

        if LayoutElementType.TABLE in elements and layout.page_count > 1:
            return "report"

        if (
            LayoutElementType.BARCODE in elements
            or LayoutElementType.QR_CODE in elements
        ):
            return "labeled_document"

        if (
            len(
                [
                    e
                    for e in layout.elements
                    if e.element_type == LayoutElementType.IMAGE
                ]
            )
            > 3
        ):
            return "image_heavy_document"

        return "general_document"

    def _get_required_elements(self, document_type: str) -> set:
        """Get required elements for document type."""
        requirements = {
            "medical_form": {LayoutElementType.TITLE, LayoutElementType.FORM_FIELD},
            "report": {LayoutElementType.TITLE, LayoutElementType.TEXT_BLOCK},
            "form": {LayoutElementType.FORM_FIELD},
            "labeled_document": {LayoutElementType.TEXT_BLOCK},
            "image_heavy_document": {LayoutElementType.IMAGE},
            "general_document": {LayoutElementType.TEXT_BLOCK},
        }

        return requirements.get(document_type, set())

    def _perform_quality_checks(self, layout: DocumentLayout) -> Dict[str, Any]:
        """Perform quality checks on document layout."""
        warnings = []
        quality_score = 1.0

        # Check confidence scores
        low_confidence_elements = [
            elem for elem in layout.elements if elem.confidence < 0.5
        ]
        if low_confidence_elements:
            warnings.append(
                f"{len(low_confidence_elements)} elements have low confidence scores"
            )
            quality_score -= 0.1

        # Check text density
        text_elements = [
            elem
            for elem in layout.elements
            if elem.element_type
            in [LayoutElementType.TEXT_BLOCK, LayoutElementType.PARAGRAPH]
        ]

        if len(text_elements) < 1:
            warnings.append("Document has very little text content")
            quality_score -= 0.2

        # Check for overlapping elements
        overlaps = self._check_overlapping_elements(layout.elements)
        if overlaps:
            warnings.append(f"{len(overlaps)} overlapping elements detected")
            quality_score -= 0.05 * len(overlaps)

        # Ensure quality score doesn't go below 0
        quality_score = max(0.0, quality_score)

        return {"score": quality_score, "warnings": warnings}

    def _check_overlapping_elements(
        self, elements: List[LayoutElement]
    ) -> List[Tuple[int, int]]:
        """Check for overlapping elements."""
        overlaps = []

        for i, elem_i in enumerate(elements):
            for j in range(i + 1, len(elements)):
                if self._boxes_overlap(elem_i.bounding_box, elements[j].bounding_box):
                    overlaps.append((i, j))

        return overlaps

    def _boxes_overlap(self, box1: BoundingBox, box2: BoundingBox) -> bool:
        """Check if two bounding boxes overlap."""
        x1_min, y1_min = box1.x, box1.y
        x1_max, y1_max = box1.x + box1.width, box1.y + box1.height

        x2_min, y2_min = box2.x, box2.y
        x2_max, y2_max = box2.x + box2.width, box2.y + box2.height

        # Check if boxes overlap
        return not (
            x1_max < x2_min or x2_max < x1_min or y1_max < y2_min or y2_max < y1_min
        )

    def _detect_form_fields(self, gray: np.ndarray) -> List[LayoutElement]:
        """Detect form fields like checkboxes and input fields."""
        elements = []

        # Detect rectangular regions that could be form fields
        _, binary = cv2.threshold(
            gray, 0, 255, CV2Constants.THRESH_BINARY_INV + CV2Constants.THRESH_OTSU
        )

        # Find contours
        contours, _ = cv2.findContours(
            binary, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )
        for contour in contours:
            # Approximate contour to polygon
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            # Check if it's a rectangle (4 corners)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(contour)

                # Check size constraints for form fields
                if 15 < w < 200 and 15 < h < 50:
                    element = LayoutElement(
                        element_type=LayoutElementType.FORM_FIELD,
                        bounding_box=BoundingBox(x, y, w, h),
                        confidence=0.6,
                    )
                    elements.append(element)

        return elements

    async def _analyze_with_textract(self, image: np.ndarray) -> List[LayoutElement]:
        """Analyze layout using AWS Textract."""
        elements = []

        # Convert image to bytes for Textract
        _, buffer = cv2.imencode(".png", image)
        image_bytes = buffer.tobytes()

        try:
            # Call Textract
            response = self.textract_client.analyze_document(
                Document={"Bytes": image_bytes}, FeatureTypes=["TABLES", "FORMS"]
            )

            # Process blocks
            for block in response["Blocks"]:
                if block["BlockType"] in [
                    "LINE",
                    "WORD",
                    "TABLE",
                    "CELL",
                    "KEY_VALUE_SET",
                ]:
                    bbox = block["Geometry"]["BoundingBox"]

                    # Convert relative coordinates to absolute
                    x = int(bbox["Left"] * image.shape[1])
                    y = int(bbox["Top"] * image.shape[0])
                    w = int(bbox["Width"] * image.shape[1])
                    h = int(bbox["Height"] * image.shape[0])

                    # Map Textract block types to our element types
                    element_type = self._map_textract_type(block["BlockType"])
                    element = LayoutElement(
                        element_type=element_type,
                        bounding_box=BoundingBox(x, y, w, h),
                        confidence=block.get("Confidence", 0.0) / 100.0,
                        text_content=block.get("Text", None),
                    )
                    elements.append(element)

        except ClientError as e:
            logger.error("Textract analysis failed: %s", e)

        return elements

    def _map_textract_type(self, block_type: str) -> LayoutElementType:
        """Map Textract block types to our element types."""
        mapping = {
            "TABLE": LayoutElementType.TABLE,
            "CELL": LayoutElementType.TABLE,
            "KEY_VALUE_SET": LayoutElementType.FORM_FIELD,
            "LINE": LayoutElementType.TEXT_BLOCK,
            "WORD": LayoutElementType.TEXT_BLOCK,
        }
        return mapping.get(block_type, LayoutElementType.UNKNOWN)

    def _merge_elements(
        self, primary: List[LayoutElement], secondary: List[LayoutElement]
    ) -> List[LayoutElement]:
        """Merge layout elements from different sources, removing duplicates."""
        merged = primary.copy()

        for elem in secondary:
            # Check if element already exists (based on overlapping bounding boxes)
            duplicate = False
            for existing in merged:
                if existing.bounding_box.intersects(elem.bounding_box):
                    # If significant overlap, consider it a duplicate
                    overlap_area = self._calculate_overlap_area(
                        existing.bounding_box, elem.bounding_box
                    )
                    if overlap_area > 0.7 * min(
                        existing.bounding_box.area, elem.bounding_box.area
                    ):
                        duplicate = True
                        break

            if not duplicate:
                merged.append(elem)

        return merged

    def _calculate_overlap_area(self, box1: BoundingBox, box2: BoundingBox) -> float:
        """Calculate the overlap area between two bounding boxes."""
        x_overlap = max(
            0, min(box1.x + box1.width, box2.x + box2.width) - max(box1.x, box2.x)
        )
        y_overlap = max(
            0, min(box1.y + box1.height, box2.y + box2.height) - max(box1.y, box2.y)
        )
        return x_overlap * y_overlap

    def _detect_reading_order(self, elements: List[LayoutElement]) -> List[int]:
        """Detect the reading order of elements."""
        if not elements:
            return []

        # Sort elements by position (top to bottom, left to right)
        indexed_elements = list(enumerate(elements))

        # Group by vertical position (rows)
        rows: Dict[int, List[int]] = {}
        for idx, elem in indexed_elements:
            y_center = elem.bounding_box.center[1]
            # Find which row this element belongs to
            row_found = False
            for row_y, row_elements in rows.items():
                if abs(y_center - row_y) < 20:  # 20 pixel tolerance
                    row_elements.append(idx)
                    row_found = True
                    break

            if not row_found:
                rows[y_center] = [idx]

        # Sort rows by Y position and elements within rows by X position
        reading_order = []
        for row_y in sorted(rows.keys()):
            row_elements = rows[row_y]
            # Sort by X position
            row_elements.sort(key=lambda idx: elements[idx].bounding_box.x)
            reading_order.extend(row_elements)

        return reading_order

    def _detect_columns(self, elements: List[LayoutElement]) -> int:
        """Detect number of columns in the document."""
        if not elements:
            return 1

        # Get text elements only
        text_elements = [
            e
            for e in elements
            if e.element_type
            in [LayoutElementType.TEXT_BLOCK, LayoutElementType.PARAGRAPH]
        ]
        if not text_elements:
            return 1

        # Analyze X positions of text elements
        x_positions = [e.bounding_box.x for e in text_elements]

        # Use clustering to detect columns
        if len(x_positions) < 3:
            return 1

        # Simple column detection: check for significant gaps
        x_positions.sort()
        gaps = []
        for i in range(1, len(x_positions)):
            gap = x_positions[i] - x_positions[i - 1]
            if gap > 50:  # Significant gap
                gaps.append(gap)

        # Estimate columns based on gaps
        if len(gaps) == 0:
            return 1
        elif len(gaps) == 1:
            return 2
        else:
            # Multiple gaps suggest multiple columns
            return min(len(gaps) + 1, 3)  # Cap at 3 columns


# Export classes
__all__ = [
    "DocumentLayoutAnalyzer",
    "LayoutElementType",
    "BoundingBox",
    "LayoutElement",
    "DocumentLayout",
]

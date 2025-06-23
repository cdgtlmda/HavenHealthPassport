"""Anomaly detection module for medical images."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple

import numpy as np

from ..document_processing.cv2_wrapper import (
    HAS_CV2,
    CV2Constants,
    CV2Extra,
)
from ..document_processing.cv2_wrapper import CV2Operations as cv2

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of anomalies in medical images."""

    LESION = "lesion"
    MASS = "mass"
    CALCIFICATION = "calcification"
    NODULE = "nodule"
    ARTIFACT = "artifact"
    FOREIGN_BODY = "foreign_body"
    TEXTURE_ABNORMALITY = "texture_abnormality"
    DENSITY_VARIATION = "density_variation"


@dataclass
class Anomaly:
    """Detected anomaly in medical image."""

    anomaly_type: AnomalyType
    location: Tuple[int, int]  # Center coordinates
    bounding_box: Tuple[int, int, int, int]  # x, y, width, height
    confidence: float
    size: float  # Area in pixels
    intensity_stats: Dict[str, float]
    features: Dict[str, Any]


class AnomalyDetector:
    """Detect anomalies in medical images."""

    def __init__(self, sensitivity: float = 0.7):
        """Initialize anomaly detector."""
        self.sensitivity = sensitivity
        self.min_anomaly_size = 10  # Minimum pixels
        self.max_anomaly_size = 10000  # Maximum pixels

    def detect_anomalies(
        self, image: np.ndarray, modality: str = "general"
    ) -> List[Anomaly]:
        """Detect anomalies in medical image."""
        anomalies = []

        # Convert to grayscale if needed
        if not HAS_CV2:
            if len(image.shape) == 3:
                gray = np.dot(image[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
            else:
                gray = image
        else:
            gray = (
                cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
                if len(image.shape) == 3
                else image
            )

        # Apply different detection methods based on modality
        if modality == "xray":
            anomalies.extend(self._detect_xray_anomalies(gray))
        elif modality == "mammography":
            anomalies.extend(self._detect_mammography_anomalies(gray))
        else:
            anomalies.extend(self._detect_general_anomalies(gray))

        # Filter by confidence
        anomalies = [a for a in anomalies if a.confidence >= self.sensitivity]

        # Remove duplicates
        anomalies = self._remove_duplicate_anomalies(anomalies)

        logger.info("Detected %d anomalies", len(anomalies))
        return anomalies

    def _detect_general_anomalies(self, gray: np.ndarray) -> List[Anomaly]:
        """Detect general anomalies using multiple techniques."""
        anomalies = []

        # Blob detection for masses
        anomalies.extend(self._detect_blobs(gray))

        # Edge-based detection for irregular shapes
        anomalies.extend(self._detect_edge_anomalies(gray))

        # Texture analysis for abnormal patterns
        anomalies.extend(self._detect_texture_anomalies(gray))

        return anomalies

    def _detect_xray_anomalies(self, gray: np.ndarray) -> List[Anomaly]:
        """Detect anomalies specific to X-ray images."""
        anomalies = []

        # Detect high-density regions (potential calcifications)
        high_density = self._detect_high_density_regions(gray)
        anomalies.extend(high_density)

        # Detect unusual patterns
        patterns = self._detect_pattern_anomalies(gray)
        anomalies.extend(patterns)

        return anomalies

    def _detect_mammography_anomalies(self, gray: np.ndarray) -> List[Anomaly]:
        """Detect anomalies specific to mammography."""
        anomalies = []

        # Detect micro-calcifications
        calcifications = self._detect_microcalcifications(gray)
        anomalies.extend(calcifications)

        # Detect masses
        masses = self._detect_masses(gray)
        anomalies.extend(masses)

        return anomalies

    def _detect_blobs(self, gray: np.ndarray) -> List[Anomaly]:
        """Detect blob-like anomalies."""
        anomalies: List[Anomaly] = []

        if not HAS_CV2:
            logger.warning("Blob detection requires OpenCV")
            return anomalies

        # Apply Gaussian blur
        blurred = CV2Extra.GaussianBlur(gray, (9, 9), 2)

        # Set up blob detector
        detector = CV2Extra.SimpleBlobDetector_create()

        # Detect blobs
        keypoints = detector.detect(blurred)

        for kp in keypoints:
            x, y = int(kp.pt[0]), int(kp.pt[1])
            size = kp.size

            # Extract region around blob
            roi_size = int(size * 2)
            x1 = max(0, x - roi_size // 2)
            y1 = max(0, y - roi_size // 2)
            x2 = min(gray.shape[1], x + roi_size // 2)
            y2 = min(gray.shape[0], y + roi_size // 2)

            roi = gray[y1:y2, x1:x2]

            # Calculate features
            features = self._calculate_region_features(roi)

            anomaly = Anomaly(
                anomaly_type=AnomalyType.MASS,
                location=(x, y),
                bounding_box=(x1, y1, x2 - x1, y2 - y1),
                confidence=0.7,
                size=np.pi * (size / 2) ** 2,
                intensity_stats={
                    "mean": float(np.mean(roi)),
                    "std": float(np.std(roi)),
                    "min": float(np.min(roi)),
                    "max": float(np.max(roi)),
                },
                features=features,
            )
            anomalies.append(anomaly)

        return anomalies

    def _detect_edge_anomalies(self, gray: np.ndarray) -> List[Anomaly]:
        """Detect anomalies based on edge detection."""
        anomalies: List[Anomaly] = []

        if not HAS_CV2:
            logger.warning("Edge anomaly detection requires OpenCV")
            return anomalies

        # Apply Canny edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(
            edges, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_anomaly_size <= area <= self.max_anomaly_size:
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                cx, cy = x + w // 2, y + h // 2

                # Extract ROI
                roi = gray[y : y + h, x : x + w]

                anomaly = Anomaly(
                    anomaly_type=AnomalyType.LESION,
                    location=(cx, cy),
                    bounding_box=(x, y, w, h),
                    confidence=0.6,
                    size=area,
                    intensity_stats={
                        "mean": float(np.mean(roi)),
                        "std": float(np.std(roi)),
                        "min": float(np.min(roi)),
                        "max": float(np.max(roi)),
                    },
                    features={"contour_points": len(contour)},
                )
                anomalies.append(anomaly)

        return anomalies

    def _detect_texture_anomalies(self, gray: np.ndarray) -> List[Anomaly]:
        """Detect texture-based anomalies."""
        anomalies = []

        # Apply texture analysis using Gabor filters
        # Simple placeholder implementation
        kernel = CV2Extra.getGaborKernel((21, 21), 8, np.pi / 4, 10, 0.5, 0)
        filtered = CV2Extra.filter2D(gray, CV2Constants.CV_32F, kernel)

        # Threshold to find anomalous regions
        _, thresh = cv2.threshold(
            np.abs(filtered),
            0,
            255,
            CV2Constants.THRESH_BINARY + CV2Constants.THRESH_OTSU,
        )
        thresh = thresh.astype(np.uint8)

        # Find contours
        contours, _ = cv2.findContours(
            thresh, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_anomaly_size <= area <= self.max_anomaly_size:
                x, y, w, h = cv2.boundingRect(contour)
                cx, cy = x + w // 2, y + h // 2

                anomaly = Anomaly(
                    anomaly_type=AnomalyType.TEXTURE_ABNORMALITY,
                    location=(cx, cy),
                    bounding_box=(x, y, w, h),
                    confidence=0.5,
                    size=area,
                    intensity_stats={
                        "mean": float(np.mean(gray[y : y + h, x : x + w])),
                        "std": float(np.std(gray[y : y + h, x : x + w])),
                        "min": float(np.min(gray[y : y + h, x : x + w])),
                        "max": float(np.max(gray[y : y + h, x : x + w])),
                    },
                    features={
                        "texture_response": float(
                            np.mean(filtered[y : y + h, x : x + w])
                        )
                    },
                )
                anomalies.append(anomaly)

        return anomalies

    def _detect_high_density_regions(self, gray: np.ndarray) -> List[Anomaly]:
        """Detect high density regions."""
        anomalies = []

        # Threshold for high density
        high_thresh = np.percentile(gray, 95)
        _, binary = cv2.threshold(gray, high_thresh, 255, CV2Constants.THRESH_BINARY)

        # Find contours
        contours, _ = cv2.findContours(
            binary.astype(np.uint8),
            CV2Constants.RETR_EXTERNAL,
            CV2Constants.CHAIN_APPROX_SIMPLE,
        )

        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_anomaly_size <= area <= self.max_anomaly_size:
                x, y, w, h = cv2.boundingRect(contour)
                cx, cy = x + w // 2, y + h // 2

                anomaly = Anomaly(
                    anomaly_type=AnomalyType.CALCIFICATION,
                    location=(cx, cy),
                    bounding_box=(x, y, w, h),
                    confidence=0.7,
                    size=area,
                    intensity_stats={
                        "mean": float(np.mean(gray[y : y + h, x : x + w])),
                        "std": float(np.std(gray[y : y + h, x : x + w])),
                        "min": float(np.min(gray[y : y + h, x : x + w])),
                        "max": float(np.max(gray[y : y + h, x : x + w])),
                    },
                    features={"density_percentile": 95},
                )
                anomalies.append(anomaly)

        return anomalies

    def _detect_pattern_anomalies(self, image: np.ndarray) -> List[Anomaly]:
        """Detect pattern-based anomalies.

        Args:
            image: Input image (grayscale not used in this implementation)
        """
        _ = image  # Mark as used
        return []  # Placeholder implementation

    def _detect_microcalcifications(self, gray: np.ndarray) -> List[Anomaly]:
        """Detect microcalcifications in mammography."""
        anomalies = []

        # Enhance small bright spots
        kernel = np.ones((3, 3), np.uint8)
        tophat = cv2.morphologyEx(gray, CV2Constants.MORPH_TOPHAT, kernel)

        # Threshold
        _, binary = cv2.threshold(
            tophat, 0, 255, CV2Constants.THRESH_BINARY + CV2Constants.THRESH_OTSU
        )

        # Find small bright regions
        contours, _ = cv2.findContours(
            binary, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)
            if 1 <= area <= 50:  # Small calcifications
                x, y, w, h = cv2.boundingRect(contour)
                cx, cy = x + w // 2, y + h // 2

                anomaly = Anomaly(
                    anomaly_type=AnomalyType.CALCIFICATION,
                    location=(cx, cy),
                    bounding_box=(x, y, w, h),
                    confidence=0.8,
                    size=area,
                    intensity_stats={
                        "mean": float(np.mean(gray[y : y + h, x : x + w])),
                        "std": float(np.std(gray[y : y + h, x : x + w])),
                        "min": float(np.min(gray[y : y + h, x : x + w])),
                        "max": float(np.max(gray[y : y + h, x : x + w])),
                    },
                    features={"calcification_type": "micro"},
                )
                anomalies.append(anomaly)

        return anomalies

    def _detect_masses(self, gray: np.ndarray) -> List[Anomaly]:
        """Detect masses in mammography."""
        return self._detect_blobs(gray)

    def _calculate_region_features(self, roi: np.ndarray) -> Dict[str, Any]:
        """Calculate features for a region of interest."""
        features = {
            "area": roi.shape[0] * roi.shape[1],
            "aspect_ratio": roi.shape[1] / roi.shape[0] if roi.shape[0] > 0 else 0,
            "entropy": -np.sum(roi * np.log2(roi + 1e-7)),
            "energy": np.sum(roi**2),
            "contrast": np.std(roi) ** 2,
        }
        return features

    def _remove_duplicate_anomalies(self, anomalies: List[Anomaly]) -> List[Anomaly]:
        """Remove duplicate anomalies based on overlap."""
        if len(anomalies) <= 1:
            return anomalies

        # Sort by confidence
        anomalies.sort(key=lambda a: a.confidence, reverse=True)

        kept: List[Anomaly] = []
        for anomaly in anomalies:
            # Check overlap with already kept anomalies
            overlap = False
            for kept_anomaly in kept:
                # Simple overlap check based on bounding boxes
                x1, y1, w1, h1 = anomaly.bounding_box
                x2, y2, w2, h2 = kept_anomaly.bounding_box

                # Calculate intersection
                xi1 = max(x1, x2)
                yi1 = max(y1, y2)
                xi2 = min(x1 + w1, x2 + w2)
                yi2 = min(y1 + h1, y2 + h2)

                if xi2 > xi1 and yi2 > yi1:
                    intersection = (xi2 - xi1) * (yi2 - yi1)
                    area1 = w1 * h1
                    area2 = w2 * h2
                    union = area1 + area2 - intersection

                    # If IoU > 0.5, consider duplicate
                    if intersection / union > 0.5:
                        overlap = True
                        break

            if not overlap:
                kept.append(anomaly)

        return kept

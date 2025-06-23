"""Privacy masking module for medical images."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

import numpy as np
from scipy.ndimage import gaussian_filter

from ..document_processing.cv2_wrapper import (
    HAS_CV2,
    CV2Constants,
    CV2Extra,
)
from ..document_processing.cv2_wrapper import CV2Operations as cv2

logger = logging.getLogger(__name__)


class PrivacyElementType(Enum):
    """Types of privacy-sensitive elements."""

    FACE = "face"
    TEXT = "text"
    PATIENT_INFO = "patient_info"
    INSTITUTION_INFO = "institution_info"
    IDENTIFIER = "identifier"
    TATTOO = "tattoo"
    JEWELRY = "jewelry"


@dataclass
class PrivacyElement:
    """Privacy-sensitive element in image."""

    element_type: PrivacyElementType
    location: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    masked: bool = False


class PrivacyMasker:
    """Mask privacy-sensitive information in medical images."""

    def __init__(self) -> None:
        """Initialize privacy masker."""
        if HAS_CV2:
            try:
                self.face_cascade = cv2.CascadeClassifier(  # type: ignore
                    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"  # type: ignore
                )
            except AttributeError:
                logger.warning("OpenCV face detection not available")
                self.face_cascade = None
        else:
            self.face_cascade = None

    def mask_image(
        self, image: np.ndarray, blur_strength: int = 50
    ) -> Tuple[np.ndarray, List[PrivacyElement]]:
        """Mask privacy-sensitive elements in image."""
        masked_image = image.copy()
        elements = []

        # Detect faces
        faces = self._detect_faces(image)
        elements.extend(faces)

        # Blur detected elements
        for element in elements:
            x, y, w, h = element.location
            roi = masked_image[y : y + h, x : x + w]
            if HAS_CV2:
                blurred = CV2Extra.GaussianBlur(
                    roi, (blur_strength | 1, blur_strength | 1), 0
                )
            else:
                # Simple blur without cv2
                blurred = gaussian_filter(roi, sigma=blur_strength // 10)
            masked_image[y : y + h, x : x + w] = blurred
            element.masked = True

        return masked_image, elements

    def _detect_faces(self, image: np.ndarray) -> List[PrivacyElement]:
        """Detect faces in image."""
        elements: List[PrivacyElement] = []

        if not HAS_CV2 or self.face_cascade is None:
            return elements

        # Convert to grayscale
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # Detect faces
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)

        for x, y, w, h in faces:
            element = PrivacyElement(
                element_type=PrivacyElementType.FACE,
                location=(x, y, w, h),
                confidence=0.9,
            )
            elements.append(element)

        return elements

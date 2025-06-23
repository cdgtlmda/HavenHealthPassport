# pylint: disable=no-member
"""
OpenCV Wrapper Module.

This module provides a safe wrapper around cv2 operations to handle
cases where cv2 might not be installed or available.
"""

from typing import Any, List, Optional, Tuple

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    cv2 = None  # type: ignore


class CV2Operations:
    """Wrapper class for cv2 operations with fallback handling."""

    @staticmethod
    def imdecode(buf: Any, flags: int) -> Any:
        """Wrap cv2.imdecode."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.imdecode(buf, flags)

    @staticmethod
    def cvtColor(src: Any, code: int) -> Any:
        """Wrap cv2.cvtColor."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.cvtColor(src, code)

    @staticmethod
    def getStructuringElement(shape: int, ksize: Tuple[int, int]) -> Any:
        """Wrap cv2.getStructuringElement."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.getStructuringElement(shape, ksize)

    @staticmethod
    def dilate(src: Any, kernel: Any, iterations: int = 1) -> Any:
        """Wrap cv2.dilate."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.dilate(src, kernel, iterations=iterations)

    @staticmethod
    def threshold(
        src: Any, thresh: float, maxval: float, threshold_type: int
    ) -> Tuple[float, Any]:
        """Wrap cv2.threshold."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.threshold(src, thresh, maxval, threshold_type)

    @staticmethod
    def findContours(image: Any, mode: int, method: int) -> Tuple[List[Any], Any]:
        """Wrap cv2.findContours."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.findContours(image, mode, method)

    @staticmethod
    def boundingRect(cnt: Any) -> Tuple[int, int, int, int]:
        """Wrap cv2.boundingRect."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        result = cv2.boundingRect(cnt)
        return (result[0], result[1], result[2], result[3])

    @staticmethod
    def morphologyEx(src: Any, op: int, kernel: Any) -> Any:
        """Wrap cv2.morphologyEx."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.morphologyEx(src, op, kernel)

    @staticmethod
    def add(src1: Any, src2: Any) -> Any:
        """Wrap cv2.add."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.add(src1, src2)

    @staticmethod
    def Canny(image: Any, threshold1: float, threshold2: float) -> Any:
        """Wrap cv2.Canny."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.Canny(image, threshold1, threshold2)

    @staticmethod
    def bitwise_and(src1: Any, src2: Any) -> Any:
        """Wrap cv2.bitwise_and."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.bitwise_and(src1, src2)

    @staticmethod
    def Sobel(src: Any, ddepth: int, dx: int, dy: int) -> Any:
        """Wrap cv2.Sobel."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.Sobel(src, ddepth, dx, dy)

    @staticmethod
    def subtract(src1: Any, src2: Any) -> Any:
        """Wrap cv2.subtract."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.subtract(src1, src2)

    @staticmethod
    def convertScaleAbs(src: Any, alpha: float = 1.0, beta: float = 0.0) -> Any:
        """Wrap cv2.convertScaleAbs."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.convertScaleAbs(src, alpha=alpha, beta=beta)

    @staticmethod
    def contourArea(contour: Any) -> float:
        """Wrap cv2.contourArea."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.contourArea(contour)

    @staticmethod
    def arcLength(curve: Any, closed: bool) -> float:
        """Wrap cv2.arcLength."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.arcLength(curve, closed)

    @staticmethod
    def approxPolyDP(curve: Any, epsilon: float, closed: bool) -> Any:
        """Wrap cv2.approxPolyDP."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.approxPolyDP(curve, epsilon, closed)

    @staticmethod
    def imencode(
        ext: str, img: Any, params: Optional[List[int]] = None
    ) -> Tuple[bool, Any]:
        """Wrap cv2.imencode."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        if params is None:
            return cv2.imencode(ext, img)
        return cv2.imencode(ext, img, params)


# Export constants with safe defaults
class CV2Constants:
    """Constants from cv2 with safe defaults."""

    IMREAD_COLOR = 1 if not HAS_CV2 else cv2.IMREAD_COLOR
    COLOR_BGR2GRAY = 6 if not HAS_CV2 else cv2.COLOR_BGR2GRAY
    COLOR_BGR2LAB = 44 if not HAS_CV2 else cv2.COLOR_BGR2LAB
    COLOR_LAB2BGR = 56 if not HAS_CV2 else cv2.COLOR_LAB2BGR
    COLOR_GRAY2BGR = 8 if not HAS_CV2 else cv2.COLOR_GRAY2BGR
    COLOR_BGR2YUV = 82 if not HAS_CV2 else cv2.COLOR_BGR2YUV
    COLOR_YUV2BGR = 84 if not HAS_CV2 else cv2.COLOR_YUV2BGR
    MORPH_RECT = 0 if not HAS_CV2 else cv2.MORPH_RECT
    MORPH_ELLIPSE = 2 if not HAS_CV2 else cv2.MORPH_ELLIPSE
    MORPH_OPEN = 2 if not HAS_CV2 else cv2.MORPH_OPEN
    MORPH_CLOSE = 3 if not HAS_CV2 else cv2.MORPH_CLOSE
    MORPH_GRADIENT = 4 if not HAS_CV2 else cv2.MORPH_GRADIENT
    MORPH_TOPHAT = 5 if not HAS_CV2 else cv2.MORPH_TOPHAT
    MORPH_DILATE = 1 if not HAS_CV2 else cv2.MORPH_DILATE
    THRESH_BINARY = 0 if not HAS_CV2 else cv2.THRESH_BINARY
    THRESH_BINARY_INV = 1 if not HAS_CV2 else cv2.THRESH_BINARY_INV
    THRESH_OTSU = 8 if not HAS_CV2 else cv2.THRESH_OTSU
    RETR_EXTERNAL = 0 if not HAS_CV2 else cv2.RETR_EXTERNAL
    RETR_TREE = 3 if not HAS_CV2 else cv2.RETR_TREE
    CHAIN_APPROX_SIMPLE = 2 if not HAS_CV2 else cv2.CHAIN_APPROX_SIMPLE
    CV_32F = 5 if not HAS_CV2 else cv2.CV_32F
    CV_64F = 6 if not HAS_CV2 else cv2.CV_64F
    CV_8U = 0 if not HAS_CV2 else cv2.CV_8U
    INTER_LINEAR = 1 if not HAS_CV2 else cv2.INTER_LINEAR
    INTER_CUBIC = 2 if not HAS_CV2 else cv2.INTER_CUBIC
    BORDER_CONSTANT = 0 if not HAS_CV2 else cv2.BORDER_CONSTANT
    NORM_MINMAX = 32 if not HAS_CV2 else cv2.NORM_MINMAX
    IMWRITE_PNG_COMPRESSION = 16 if not HAS_CV2 else cv2.IMWRITE_PNG_COMPRESSION
    IMWRITE_JPEG_QUALITY = 1 if not HAS_CV2 else cv2.IMWRITE_JPEG_QUALITY


# Additional wrapper functions that might be needed
class CV2Extra:
    """Additional cv2 operations."""

    @staticmethod
    def setNumThreads(threads: int) -> None:
        """Wrap cv2.setNumThreads."""
        if not HAS_CV2:
            return  # Silently ignore if cv2 not available
        cv2.setNumThreads(threads)

    @staticmethod
    def setUseOptimized(flag: bool) -> None:
        """Wrap cv2.setUseOptimized."""
        if not HAS_CV2:
            return  # Silently ignore if cv2 not available
        cv2.setUseOptimized(flag)

    @staticmethod
    def createCLAHE(
        clipLimit: float = 40.0, tileGridSize: Tuple[int, int] = (8, 8)
    ) -> Any:
        """Wrap cv2.createCLAHE."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.createCLAHE(clipLimit, tileGridSize)

    @staticmethod
    def Laplacian(src: Any, ddepth: int) -> Any:
        """Wrap cv2.Laplacian."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.Laplacian(src, ddepth)

    @staticmethod
    def medianBlur(src: Any, ksize: int) -> Any:
        """Wrap cv2.medianBlur."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.medianBlur(src, ksize)

    @staticmethod
    def HoughLines(image: Any, rho: float, theta: float, threshold: int) -> Any:
        """Wrap cv2.HoughLines."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.HoughLines(image, rho, theta, threshold)

    @staticmethod
    def blur(src: Any, ksize: Tuple[int, int]) -> Any:
        """Wrap cv2.blur."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.blur(src, ksize)

    @staticmethod
    def split(m: Any) -> List[Any]:
        """Wrap cv2.split."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return list(cv2.split(m))

    @staticmethod
    def merge(mv: List[Any]) -> Any:
        """Wrap cv2.merge."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.merge(mv)

    @staticmethod
    def GaussianBlur(src: Any, ksize: Tuple[int, int], sigmaX: float) -> Any:
        """Wrap cv2.GaussianBlur."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.GaussianBlur(src, ksize, sigmaX)

    @staticmethod
    def addWeighted(
        src1: Any, alpha: float, src2: Any, beta: float, gamma: float
    ) -> Any:
        """Wrap cv2.addWeighted."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.addWeighted(src1, alpha, src2, beta, gamma)

    @staticmethod
    def fastNlMeansDenoisingColored(
        src: Any,
        h: float = 10,
        hColor: float = 10,
        templateWindowSize: int = 7,
        searchWindowSize: int = 21,
    ) -> Any:
        """Wrap cv2.fastNlMeansDenoisingColored."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.fastNlMeansDenoisingColored(
            src, None, h, hColor, templateWindowSize, searchWindowSize
        )

    @staticmethod
    def fastNlMeansDenoising(
        src: Any, h: float = 10, templateWindowSize: int = 7, searchWindowSize: int = 21
    ) -> Any:
        """Wrap cv2.fastNlMeansDenoising."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.fastNlMeansDenoising(
            src, None, h, templateWindowSize, searchWindowSize
        )

    @staticmethod
    def getRotationMatrix2D(
        center: Tuple[float, float], angle: float, scale: float
    ) -> Any:
        """Wrap cv2.getRotationMatrix2D."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.getRotationMatrix2D(center, angle, scale)

    @staticmethod
    def warpAffine(
        src: Any,
        M: Any,
        dsize: Tuple[int, int],
        flags: Optional[int] = None,
        borderMode: Optional[int] = None,
        borderValue: Optional[Any] = None,
    ) -> Any:
        """Wrap cv2.warpAffine."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        if flags is not None and borderMode is not None and borderValue is not None:
            return cv2.warpAffine(src, M, dsize, None, flags, borderMode, borderValue)
        elif flags is not None and borderMode is not None:
            return cv2.warpAffine(src, M, dsize, None, flags, borderMode)
        elif flags is not None:
            return cv2.warpAffine(src, M, dsize, None, flags)
        else:
            return cv2.warpAffine(src, M, dsize)

    @staticmethod
    def divide(src1: Any, src2: Any) -> Any:
        """Wrap cv2.divide."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.divide(src1, src2)

    @staticmethod
    def resize(
        src: Any,
        dsize: Tuple[int, int],
        fx: float = 0,
        fy: float = 0,
        interpolation: Optional[int] = None,
    ) -> Any:
        """Wrap cv2.resize."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        if interpolation is None:
            return cv2.resize(src, dsize, fx=fx, fy=fy)
        return cv2.resize(src, dsize, fx=fx, fy=fy, interpolation=interpolation)

    @staticmethod
    def calcHist(
        images: List[Any],
        channels: List[int],
        mask: Any,
        histSize: List[int],
        ranges: List[float],
    ) -> Any:
        """Wrap cv2.calcHist."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.calcHist(images, channels, mask, histSize, ranges)

    @staticmethod
    def SimpleBlobDetector_create() -> Any:
        """Wrap cv2.SimpleBlobDetector_create."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.SimpleBlobDetector_create()  # type: ignore

    @staticmethod
    def getGaborKernel(
        ksize: Tuple[int, int],
        sigma: float,
        theta: float,
        lambd: float,
        gamma: float,
        psi: float = 0,
    ) -> Any:
        """Wrap cv2.getGaborKernel."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.getGaborKernel(ksize, sigma, theta, lambd, gamma, psi)

    @staticmethod
    def filter2D(src: Any, ddepth: int, kernel: Any) -> Any:
        """Wrap cv2.filter2D."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.filter2D(src, ddepth, kernel)

    @staticmethod
    def bilateralFilter(src: Any, d: int, sigmaColor: float, sigmaSpace: float) -> Any:
        """Wrap cv2.bilateralFilter."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.bilateralFilter(src, d, sigmaColor, sigmaSpace)

    @staticmethod
    def normalize(
        src: Any,
        dst: Optional[Any] = None,
        alpha: float = 0,
        beta: float = 255,
        norm_type: int = 32,
        dtype: int = -1,
    ) -> Any:
        """Wrap cv2.normalize."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        if dst is None:
            dst = src.copy() if hasattr(src, "copy") else src
        return cv2.normalize(src, dst, alpha, beta, norm_type, dtype)

    @staticmethod
    def equalizeHist(src: Any) -> Any:
        """Wrap cv2.equalizeHist."""
        if not HAS_CV2:
            raise ImportError("OpenCV (cv2) is not installed")
        return cv2.equalizeHist(src)

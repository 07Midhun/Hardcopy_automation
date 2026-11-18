"""
Computer Vision and image enhancement utilities using OpenCV and NumPy.
Optimized for preserving delicate handwriting strokes while removing noise and skew.
"""
from pathlib import Path
from typing import Tuple, Optional
import cv2
import numpy as np
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def detect_and_correct_orientation(image: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Detect document skew angle and rotate to upright.
    Uses Hough Line Transform and minimum area bounding box on edge contours.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    # Invert binary threshold to get document text/lines as white pixels
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # Find all non-zero coordinate points
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return image, 0.0

    rect = cv2.minAreaRect(coords)
    angle = rect[-1]

    # Normalize angle to [-45, 45] range
    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = 90 - angle

    # Only rotate if skew is notable (> 0.5 degrees) and reasonable (< 35 degrees)
    if abs(angle) > 0.5 and abs(angle) < 35.0:
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        corrected = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        logger.info(f"Deskewed document by {angle:.2f} degrees")
        return corrected, angle

    return image, 0.0


def enhance_handwriting_contrast(image: np.ndarray) -> np.ndarray:
    """
    Apply Contrast Limited Adaptive Histogram Equalization (CLAHE).
    Enhances contrast between faint ballpoint/gel handwriting and background paper
    without blowing out fine pen curves.
    """
    if len(image.shape) == 3:
        # Convert to LAB color space to equalize luminance channel only
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        enhanced_lab = cv2.merge((cl, a, b))
        return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    else:
        clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8))
        return clahe.apply(image)


def remove_noise_preserve_edges(image: np.ndarray) -> np.ndarray:
    """
    Gentle bilateral filter to smooth paper grain and scanner noise
    while strictly preserving faint single-pixel handwritten pen strokes.
    """
    (h, w) = image.shape[:2]
    if h * w > 1500000:
        return cv2.bilateralFilter(image, d=5, sigmaColor=30, sigmaSpace=30)
    return cv2.bilateralFilter(image, d=5, sigmaColor=40, sigmaSpace=40)


def unsharp_mask(image: np.ndarray, kernel_size=(5, 5), sigma=1.0, amount=0.5, threshold=0) -> np.ndarray:
    """
    Gentle sharpening using optimized cv2.addWeighted to clarify ink edges without ringing artifacts.
    """
    blurred = cv2.GaussianBlur(image, kernel_size, sigma)
    return cv2.addWeighted(image, 1.0 + amount, blurred, -amount, 0)


def preprocess_document_image(
    input_image_path: Path,
    output_image_path: Optional[Path] = None,
    deskew: bool = True,
    denoise: bool = True,
    enhance_contrast: bool = True,
    sharpen: bool = True
) -> Path:
    """
    Full pipeline to clean and enhance document for OCR/Vision.
    Never overwrites original file; writes to output_image_path.
    """
    img = cv2.imread(str(input_image_path))
    if img is None:
        raise ValueError(f"Could not load image: {input_image_path}")

    # 1. Orientation correction
    if deskew:
        img, _ = detect_and_correct_orientation(img)

    # 2. Contrast Enhancement (CLAHE)
    if enhance_contrast:
        img = enhance_handwriting_contrast(img)

    # 3. Denoising while preserving handwriting edges
    if denoise:
        img = remove_noise_preserve_edges(img)

    # 4. Sharpening
    if sharpen:
        img = unsharp_mask(img, amount=0.5)

    if output_image_path is None:
        output_image_path = input_image_path.with_name(f"{input_image_path.stem}_enhanced.png")

    output_image_path = Path(output_image_path)
    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_image_path), img)

    logger.info(f"Preprocessed and saved enhanced document image: {output_image_path}")
    return output_image_path

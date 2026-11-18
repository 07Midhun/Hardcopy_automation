"""
Image Processing Service for enhancement, deskewing, and contrast optimization.
"""
from pathlib import Path
from typing import Optional
from backend.app.utils.image_utils import preprocess_document_image
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


class ImageService:
    """Service wrapping OpenCV document image enhancement operations."""

    @staticmethod
    def enhance_for_ocr(
        image_path: Path,
        output_path: Optional[Path] = None,
        deskew: bool = True,
        denoise: bool = True,
        enhance_contrast: bool = True,
        sharpen: bool = True
    ) -> Path:
        """
        Enhance scanned document image for handwriting and printed text extraction.
        Never mutates original; saves to output_path.
        """
        return preprocess_document_image(
            input_image_path=image_path,
            output_image_path=output_path,
            deskew=deskew,
            denoise=denoise,
            enhance_contrast=enhance_contrast,
            sharpen=sharpen
        )


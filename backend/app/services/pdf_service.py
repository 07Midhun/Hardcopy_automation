"""
PDF Service handling document inspection, validation, and rendering.
"""
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from backend.app.utils.pdf_utils import validate_pdf, detect_and_extract_embedded_text, render_pdf_page_to_image
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


class PDFService:
    """Service for PDF operations."""

    @staticmethod
    def inspect_and_validate(pdf_path: Path) -> Tuple[bool, Optional[str], int]:
        """Validate PDF integrity and get page count."""
        return validate_pdf(pdf_path)

    @staticmethod
    def extract_embedded_text(pdf_path: Path) -> Dict[str, Any]:
        """Extract selectable digital text if present."""
        return detect_and_extract_embedded_text(pdf_path)

    @staticmethod
    def render_page(pdf_path: Path, page_number: int = 1, dpi: int = 300, target_path: Optional[Path] = None) -> Path:
        """Render single page to high-res image for AI analysis."""
        return render_pdf_page_to_image(pdf_path, page_number=page_number, dpi=dpi, output_image_path=target_path)


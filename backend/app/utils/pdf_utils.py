"""
PDF processing utilities using PyMuPDF (fitz).
Provides validation, embedded text extraction, and high-fidelity page rendering.
"""
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import pymupdf as fitz
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def validate_pdf(pdf_path: Path) -> Tuple[bool, Optional[str], int]:
    """
    Validate PDF integrity and return (is_valid, error_message, page_count).
    """
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        if page_count == 0:
            doc.close()
            return False, "PDF contains no pages", 0
        doc.close()
        return True, None, page_count
    except Exception as e:
        logger.error(f"Invalid or corrupted PDF {pdf_path}: {e}")
        return False, str(e), 0


def detect_and_extract_embedded_text(pdf_path: Path, min_chars_per_page: int = 40) -> Dict[str, Any]:
    """
    Detect if PDF contains digital selectable text vs scanned raster image.
    Extract embedded text blocks if present.
    """
    result = {
        "has_embedded_text": False,
        "text": "",
        "blocks": [],
        "char_count": 0
    }

    try:
        doc = fitz.open(pdf_path)
        full_text = []
        all_blocks = []

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_text = page.get_text("text").strip()
            if page_text:
                full_text.append(page_text)

            # Extract detailed block positions
            blocks = page.get_text("blocks")
            for b in blocks:
                # b: (x0, y0, x1, y1, text, block_no, block_type)
                if len(b) >= 5 and b[4].strip():
                    all_blocks.append({
                        "page": page_idx + 1,
                        "bbox": [round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)],
                        "text": b[4].strip()
                    })

        combined_text = "\n".join(full_text)
        char_count = len(combined_text)

        result["text"] = combined_text
        result["blocks"] = all_blocks
        result["char_count"] = char_count
        result["has_embedded_text"] = (char_count >= min_chars_per_page)

        doc.close()
    except Exception as e:
        logger.error(f"Error inspecting embedded text in {pdf_path}: {e}")

    return result


def render_pdf_page_to_image(
    pdf_path: Path,
    page_number: int = 1,
    dpi: int = 200,
    output_image_path: Optional[Path] = None,
    target_path: Optional[Path] = None
) -> Path:
    """
    Render a single PDF page into a high-resolution PNG image for OCR/Vision analysis.
    Preserves original PDF without modifying it.
    """
    if output_image_path is None and target_path is not None:
        output_image_path = target_path
    doc = fitz.open(pdf_path)
    if page_number < 1 or page_number > len(doc):
        doc.close()
        raise ValueError(f"Page {page_number} out of range (total: {len(doc)})")

    page = doc[page_number - 1]
    # Calculate zoom matrix for desired DPI (standard 72 DPI base)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    if output_image_path is None:
        output_image_path = pdf_path.with_suffix(f".p{page_number}_{dpi}dpi.png")

    output_image_path = Path(output_image_path)
    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_image_path))
    doc.close()

    logger.info(f"Rendered PDF page {page_number} at {dpi} DPI to {output_image_path}")
    return output_image_path

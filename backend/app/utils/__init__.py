"""
Utilities module export.
"""
from backend.app.utils.logger import get_logger
from backend.app.utils.file_utils import (
    calculate_sha256,
    get_file_size,
    sanitize_filename,
    is_allowed_file,
    extract_zip_archive
)
from backend.app.utils.pdf_utils import (
    validate_pdf,
    detect_and_extract_embedded_text,
    render_pdf_page_to_image
)
from backend.app.utils.image_utils import (
    detect_and_correct_orientation,
    enhance_handwriting_contrast,
    remove_noise_preserve_edges,
    preprocess_document_image
)
from backend.app.utils.json_utils import clean_and_parse_json, to_json_str

__all__ = [
    "get_logger",
    "calculate_sha256",
    "get_file_size",
    "sanitize_filename",
    "is_allowed_file",
    "extract_zip_archive",
    "validate_pdf",
    "detect_and_extract_embedded_text",
    "render_pdf_page_to_image",
    "detect_and_correct_orientation",
    "enhance_handwriting_contrast",
    "remove_noise_preserve_edges",
    "preprocess_document_image",
    "clean_and_parse_json",
    "to_json_str"
]


"""
Unit tests for file, PDF, image, and JSON utilities.
"""
import numpy as np
from pathlib import Path
from backend.app.utils.file_utils import calculate_sha256, sanitize_filename
from backend.app.utils.pdf_utils import validate_pdf, detect_and_extract_embedded_text, render_pdf_page_to_image
from backend.app.utils.image_utils import detect_and_correct_orientation, enhance_handwriting_contrast
from backend.app.utils.json_utils import clean_and_parse_json


def test_sha256_calculation(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("Hello AI Document Intelligence", encoding="utf-8")
    h = calculate_sha256(f)
    assert len(h) == 64
    assert h == calculate_sha256(f)  # deterministic


def test_sanitize_filename():
    assert sanitize_filename("../../../malicious_file.pdf") == "malicious_file.pdf"
    assert sanitize_filename("Ward 64 Report (Copy).pdf").endswith(".pdf")


def test_pdf_validation_and_rendering(sample_pdf, tmp_path):
    is_valid, err, page_count = validate_pdf(sample_pdf)
    assert is_valid is True
    assert err is None
    assert page_count == 1

    # Embedded text detection
    emb = detect_and_extract_embedded_text(sample_pdf)
    assert emb["has_embedded_text"] is True
    assert "Ward Number" in emb["text"]

    # Page rendering to PNG
    img_target = tmp_path / "rendered.png"
    rendered = render_pdf_page_to_image(sample_pdf, page_number=1, dpi=150, target_path=img_target)
    assert rendered.exists()
    assert rendered.stat().st_size > 1000


def test_image_enhancement(tmp_path):
    # Create synthetic test image
    synthetic_img = np.ones((400, 400, 3), dtype=np.uint8) * 200
    # Add contrast
    enhanced = enhance_handwriting_contrast(synthetic_img)
    assert enhanced.shape == synthetic_img.shape

    corrected, angle = detect_and_correct_orientation(synthetic_img)
    assert corrected.shape == synthetic_img.shape
    assert isinstance(angle, float)


def test_clean_and_parse_json():
    # Markdown fence wrapped JSON
    raw_markdown = """
    Here is the extraction result:
    ```json
    {
      "document_type": "CCMS Installation Report",
      "records": []
    }
    ```
    """
    parsed = clean_and_parse_json(raw_markdown)
    assert parsed is not None
    assert parsed["document_type"] == "CCMS Installation Report"

    # Trailing comma fix
    raw_trailing = '{"name": "test", "value": "123",}'
    parsed2 = clean_and_parse_json(raw_trailing)
    assert parsed2 is not None
    assert parsed2["value"] == "123"


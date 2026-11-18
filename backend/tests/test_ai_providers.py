"""
Unit tests for AI providers, normalization, and validation rules.
"""
from backend.app.ai.schemas import DocumentExtractionResult, RecordExtraction, FieldExtraction
from backend.app.ai.fallback_provider import FallbackDocumentProvider
from backend.app.services.normalization_service import NormalizationService
from backend.app.services.validation_service import ValidationService


def test_schema_serialization():
    field = FieldExtraction(
        field_name="Ward Number",
        value="064",
        confidence=0.98,
        verification_status="verified"
    )
    rec = RecordExtraction(
        section="General Information",
        record_number=1,
        page_number=1,
        fields=[field]
    )
    doc_res = DocumentExtractionResult(
        document_id="DOC0001",
        source_filename="test.pdf",
        document_type="CCMS Installation Report",
        classification_confidence=0.95,
        records=[rec]
    )
    d = doc_res.model_dump()
    assert d["document_id"] == "DOC0001"
    assert d["records"][0]["fields"][0]["value"] == "064"


def test_fallback_provider_extraction(sample_pdf, tmp_path):
    provider = FallbackDocumentProvider(confidence_threshold=0.75)
    # Render page to pass image
    from backend.app.utils.pdf_utils import render_pdf_page_to_image
    img = tmp_path / "page1.png"
    render_pdf_page_to_image(sample_pdf, target_path=img)

    result = provider.extract_document(
        document_id="DOC-TEST-01",
        filename="sample_ccms_report.pdf",
        image_path=img,
        pdf_path=sample_pdf
    )

    assert result.document_id == "DOC-TEST-01"
    assert result.document_type == "CCMS Installation Report"
    assert len(result.records) > 0

    field_dict = {f.field_name: f.value for f in result.records[0].fields}
    assert "Ward Number" in field_dict
    assert field_dict["Ward Number"] == "64"
    # Verify leading zero preservation
    assert "Installed Pole Number" in field_dict
    assert field_dict["Installed Pole Number"] == "0860"


def test_normalization_and_validation_rules():
    # Normalization should clean spaces and delimiters without modifying inner content
    assert NormalizationService.normalize_field_name("  Ward No. :  ") == "Ward No."
    assert NormalizationService.clean_value("  0042  ") == "0042"

    # Validation: high confidence -> verified
    status, _ = ValidationService.validate_field("Ward Number", "64", 0.95, 0.75)
    assert status == "verified"

    # Validation: low confidence -> review_required
    status_low, reason_low = ValidationService.validate_field("Signature", "K. Rao", 0.65, 0.75)
    assert status_low == "review_required"
    assert "Low confidence" in reason_low

    # Validation: unreadable indicator -> unreadable
    status_unread, _ = ValidationService.validate_field("Notes", "[unreadable ink]", 0.40, 0.75)
    assert status_unread == "unreadable"

    # Validation: empty -> missing
    status_empty, _ = ValidationService.validate_field("Remarks", "", 0.90, 0.75)
    assert status_empty == "missing"

    # Validation: Y/N field digit confusion ('4' instead of 'Y') -> review_required
    status_yn, reason_yn = ValidationService.validate_field("SLC Earthing Completed (Y/N)", "4", 0.95, 0.75)
    assert status_yn == "review_required"
    assert "Y/4" in reason_yn


def test_cross_row_digit_confusion_and_wattage_validation():
    """Verify that single-digit handwriting confusions (e.g. 338 -> 378) and wattage mismatches are flagged."""
    from types import SimpleNamespace

    def make_row(pole, arm="1", conn="56", tot="56"):
        return [
            SimpleNamespace(field_name="Pole Number", current_value=pole, confidence_score=0.95, verification_status="verified"),
            SimpleNamespace(field_name="Arm Count", current_value=arm, confidence_score=0.95, verification_status="verified"),
            SimpleNamespace(field_name="Connected Lamp Wattage", current_value=conn, confidence_score=0.95, verification_status="verified"),
            SimpleNamespace(field_name="Total Wattage", current_value=tot, confidence_score=0.95, verification_status="verified"),
        ]

    rows = [
        make_row("335"),
        make_row("335"),
        make_row("338"),
        make_row("378"),  # Classic 3 <-> 7 handwriting confusion outlier
        make_row("336"),
        make_row("337", arm="2", conn="56", tot="56"),  # Wattage math mismatch: 2 * 56 != 56
    ]

    anomalies = ValidationService.validate_page_table_consistency(rows, confidence_threshold=0.75)

    # Row 4 ('378') must be flagged for human review without silently altering its value
    assert rows[3][0].current_value == "378"
    assert rows[3][0].verification_status == "review_required"
    assert rows[3][0].confidence_score < 0.75

    # Normal rows ('335', '338', '336') must remain verified
    assert rows[0][0].verification_status == "verified"
    assert rows[2][0].verification_status == "verified"
    assert rows[4][0].verification_status == "verified"

    # Row 6 wattage mismatch must be flagged
    assert rows[5][3].verification_status == "review_required"
    assert len(anomalies) == 2


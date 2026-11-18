"""
Unit tests for Consolidated Excel Generation.
Enforces Section 13: EXACTLY ONE workbook containing EXACTLY ONE worksheet named 'Consolidated_Data'.
"""
import openpyxl
from backend.app.extensions import db
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.document import Document
from backend.app.models.extracted_record import ExtractedRecord
from backend.app.models.extracted_field import ExtractedField
from backend.app.services.excel_service import ExcelService, WORKSHEET_NAME, COLUMNS


def test_consolidated_excel_generation(app, tmp_path):
    # Seed a job with extracted documents and fields
    job = ProcessingJob(id="JOB-EXCEL-TEST", total_documents=1, status="completed")
    db.session.add(job)

    doc = Document(
        id="DOC0001",
        job_id=job.id,
        original_filename="sample_report.pdf",
        s3_key="documents/sample_report.pdf",
        file_hash="test_hash_123",
        document_type="CCMS Installation Report",
        status="completed"
    )
    db.session.add(doc)
    db.session.commit()

    rec = ExtractedRecord(document_id=doc.id, section="General Information", record_number=1, page_number=1)
    db.session.add(rec)
    db.session.commit()

    f1 = ExtractedField(
        record_id=rec.id,
        field_name="Ward Number",
        original_extracted_value="64",
        current_value="64",
        confidence_score=0.98,
        verification_status="verified"
    )
    f2 = ExtractedField(
        record_id=rec.id,
        field_name="Installed Pole Number",
        original_extracted_value="0860",
        current_value="0860",
        confidence_score=0.96,
        verification_status="verified"
    )
    db.session.add_all([f1, f2])
    db.session.commit()

    # Generate workbook
    target_excel = tmp_path / "Consolidated_Data_Test.xlsx"
    ExcelService.generate_consolidated_workbook(job_id=job.id, target_path=target_excel)

    assert target_excel.exists()

    # Load workbook and verify strict requirements
    wb = openpyxl.load_workbook(target_excel)

    # 1. Exactly ONE worksheet
    assert len(wb.sheetnames) == 1, f"Expected 1 worksheet, got {len(wb.sheetnames)}"

    # 2. Worksheet name must be 'Consolidated_Data'
    assert wb.sheetnames[0] == WORKSHEET_NAME, f"Worksheet name must be {WORKSHEET_NAME}"

    ws = wb[WORKSHEET_NAME]

    # 3. Headers check
    headers = [cell.value for cell in ws[1]]
    assert headers == COLUMNS, "Header columns do not match required specification"

    # 4. Data rows check
    assert ws.max_row == 3  # 1 header + 2 field rows

    row2_vals = [cell.value for cell in ws[2]]
    assert row2_vals[0] == "DOC0001"
    assert row2_vals[1] == "sample_report.pdf"
    assert row2_vals[2] == "CCMS Installation Report"
    assert row2_vals[3] == 1
    assert row2_vals[4] == "General Information"
    assert row2_vals[5] == 1
    assert row2_vals[6] == "Ward Number"
    assert row2_vals[7] == "64"
    assert row2_vals[8] == 0.98
    assert row2_vals[9] == "verified"

    # 5. Check leading zero preservation in row 3
    row3_vals = [cell.value for cell in ws[3]]
    assert row3_vals[6] == "Installed Pole Number"
    assert row3_vals[7] == "0860", "Leading zero must be preserved in Excel cell"

    # 6. Verify freeze panes & auto filter
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref is not None

    wb.close()


def test_tabular_excel_generation(app, tmp_path):
    """Verify horizontal tabular Excel format places all pole columns side-by-side in one worksheet."""
    job = ProcessingJob(id="JOB-TABULAR-TEST", total_documents=1, status="completed")
    db.session.add(job)
    doc = Document(
        id="DOC-TAB-01",
        job_id=job.id,
        original_filename="ward_120.pdf",
        s3_key="documents/ward_120.pdf",
        file_hash="tab_hash_123",
        document_type="CCMS Installation Report",
        status="completed"
    )
    db.session.add(doc)
    db.session.commit()

    hdr = ExtractedRecord(document_id=doc.id, section="General Information", record_number=1, page_number=17)
    r1 = ExtractedRecord(document_id=doc.id, section="Table: Pole and Lamp Details", record_number=1, page_number=17)
    r2 = ExtractedRecord(document_id=doc.id, section="Table: Pole and Lamp Details", record_number=2, page_number=17)
    db.session.add_all([hdr, r1, r2])
    db.session.commit()

    db.session.add_all([
        ExtractedField(record_id=hdr.id, field_name="Ward Number", original_extracted_value="120", current_value="120", confidence_score=0.98, verification_status="verified"),
        ExtractedField(record_id=hdr.id, field_name="Contractor Name", original_extracted_value="Kalabhiraweshwara", current_value="Kalabhiraweshwara", confidence_score=0.92, verification_status="verified"),
        ExtractedField(record_id=hdr.id, field_name="Site Incharge", original_extracted_value="Pavan", current_value="Pavan", confidence_score=0.92, verification_status="verified"),
        ExtractedField(record_id=r1.id, field_name="Sl.No", original_extracted_value="1", current_value="1", confidence_score=0.98, verification_status="verified"),
        ExtractedField(record_id=r1.id, field_name="Pole No", original_extracted_value="305", current_value="305", confidence_score=0.97, verification_status="verified"),
        ExtractedField(record_id=r1.id, field_name="Arm Count", original_extracted_value="1", current_value="1", confidence_score=0.98, verification_status="verified"),
        ExtractedField(record_id=r1.id, field_name="Existing LED / New LED / SVL / Non LED", original_extracted_value="Old", current_value="Old", confidence_score=0.96, verification_status="verified"),
        ExtractedField(record_id=r1.id, field_name="Lamp Burning Status (Yes / No)", original_extracted_value="Y", current_value="Y", confidence_score=0.96, verification_status="verified"),
        ExtractedField(record_id=r1.id, field_name="Connected Lamp Wattages", original_extracted_value="65", current_value="65", confidence_score=0.96, verification_status="verified"),
        ExtractedField(record_id=r1.id, field_name="Total Wattage", original_extracted_value="65", current_value="65", confidence_score=0.96, verification_status="verified"),
        ExtractedField(record_id=r2.id, field_name="Sl.No", original_extracted_value="2", current_value="2", confidence_score=0.98, verification_status="verified"),
        ExtractedField(record_id=r2.id, field_name="Pole No", original_extracted_value="008", current_value="008", confidence_score=0.97, verification_status="verified"),
    ])
    db.session.commit()

    target = tmp_path / "Tabular_Test.xlsx"
    ExcelService.generate_consolidated_workbook(job_id=job.id, target_path=target, layout="tabular")

    wb = openpyxl.load_workbook(target)
    assert wb.sheetnames == [WORKSHEET_NAME]
    ws = wb[WORKSHEET_NAME]
    headers = [c.value for c in ws[1]]
    assert "Document ID" not in headers
    assert "Document Type" not in headers
    assert "Contractor Name" not in headers
    assert "Site Incharge" not in headers
    assert headers[0] == "Source Filename"
    assert headers[1] == "Page Number"
    assert "Sl.No" in headers
    assert "Pole No" in headers
    assert "Arm Count" in headers
    assert "Existing LED / New LED / Non LED" in headers
    assert "Lamp Burning Status (Yes/No)" in headers
    assert "Connected Lamp Wattages" in headers
    assert "Total Wattage" in headers
    assert ws.max_row == 3  # 1 header + 2 pole rows

    pole_col = headers.index("Pole No") + 1
    assert ws.cell(row=2, column=pole_col).value == "305"
    assert ws.cell(row=3, column=pole_col).value == "008"  # Leading zeros preserved
    wb.close()


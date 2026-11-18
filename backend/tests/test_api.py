"""
Integration tests for REST API endpoints.
"""
import io
from backend.app.extensions import db
from backend.app.models.document import Document
from backend.app.models.extracted_record import ExtractedRecord
from backend.app.models.extracted_field import ExtractedField


def test_auth_api_flow(client):
    # Register
    res = client.post("/api/auth/register", json={
        "username": "tester1",
        "email": "tester1@example.com",
        "password": "Password123"
    })
    assert res.status_code == 201

    # Login
    res_login = client.post("/api/auth/login", json={
        "username": "tester1",
        "password": "Password123"
    })
    assert res_login.status_code == 200


def test_bulk_upload_and_extraction_flow(client, sample_pdf):
    with open(sample_pdf, "rb") as f:
        pdf_bytes = f.read()

    data = {
        "files": (io.BytesIO(pdf_bytes), "sample_ccms_report.pdf"),
        "batch_name": "Test Integration Batch"
    }

    res = client.post(
        "/api/upload/bulk",
        data=data,
        content_type="multipart/form-data"
    )
    assert res.status_code == 201
    res_json = res.get_json()
    assert res_json["registered_count"] == 1
    job_id = res_json["job_id"]

    # Verify document exists in database
    doc = Document.query.filter_by(job_id=job_id).first()
    assert doc is not None
    assert doc.original_filename == "sample_ccms_report.pdf"

    # Test Document Extraction API
    res_ext = client.get(f"/api/documents/{doc.id}/extraction")
    assert res_ext.status_code == 200
    ext_data = res_ext.get_json()
    assert ext_data["document_id"] == doc.id
    assert len(ext_data["records"]) > 0

    # Test Corrections PATCH
    first_field = ext_data["records"][0]["fields"][0]
    res_corr = client.patch(f"/api/documents/{doc.id}/corrections", json={
        "document_status": "completed",
        "corrections": [
            {
                "field_id": first_field["id"],
                "corrected_value": "999",
                "verification_status": "verified"
            }
        ]
    })
    assert res_corr.status_code == 200
    assert res_corr.get_json()["updated_count"] == 1

    # Verify field value updated in DB
    updated_field = db.session.get(ExtractedField, first_field["id"])
    assert updated_field.current_value == "999"
    assert updated_field.verification_status == "verified"


def test_dashboard_stats_api(client):
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    stats = res.get_json()
    assert "kpis" in stats
    assert "status_distribution" in stats
    assert "doc_type_distribution" in stats


def test_consolidated_excel_export_api(client, sample_pdf):
    # Upload document first so export has data
    with open(sample_pdf, "rb") as f:
        pdf_bytes = f.read()

    client.post(
        "/api/upload/bulk",
        data={"files": (io.BytesIO(pdf_bytes), "sample_ccms_report.pdf")},
        content_type="multipart/form-data"
    )

    res = client.get("/api/export/consolidated")
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(res.data) > 0


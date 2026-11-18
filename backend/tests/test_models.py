"""
Unit tests for relational database models.
"""
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.document import Document
from backend.app.models.extracted_record import ExtractedRecord
from backend.app.models.extracted_field import ExtractedField
from backend.app.models.verification_log import VerificationLog


def test_user_password_hashing(app):
    user = User(username="janedoe", email="jane@test.com")
    user.set_password("MySecurePassword")
    assert user.check_password("MySecurePassword") is True
    assert user.check_password("WrongPassword") is False
    assert user.password_hash != "MySecurePassword"


def test_processing_job_progress(app):
    job = ProcessingJob(
        id="JOB-TEST-001",
        total_documents=10,
        completed_documents=6,
        failed_documents=1,
        review_required_documents=1
    )
    db.session.add(job)
    db.session.commit()

    assert job.pending_documents == 2
    assert job.progress_percentage == 80.0


def test_document_and_records_cascade(app):
    job = ProcessingJob(id="JOB-CASCADE", total_documents=1)
    db.session.add(job)

    doc = Document(
        id="DOC-CASCADE-1",
        job_id=job.id,
        original_filename="test.pdf",
        s3_key="documents/test.pdf",
        file_hash="abcdef123456"
    )
    db.session.add(doc)
    db.session.commit()

    rec = ExtractedRecord(document_id=doc.id, section="General Info", record_number=1)
    db.session.add(rec)
    db.session.commit()

    field = ExtractedField(
        record_id=rec.id,
        field_name="Ward Number",
        original_extracted_value="64",
        current_value="64",
        confidence_score=0.98,
        verification_status="verified"
    )
    db.session.add(field)
    db.session.commit()

    # Verify retrieval
    assert len(doc.records) == 1
    assert len(doc.records[0].fields) == 1
    assert doc.records[0].fields[0].field_name == "Ward Number"

    # Delete doc -> cascades to records and fields
    db.session.delete(doc)
    db.session.commit()

    assert ExtractedRecord.query.filter_by(document_id="DOC-CASCADE-1").count() == 0
    assert ExtractedField.query.filter_by(id=field.id).count() == 0


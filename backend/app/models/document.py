"""
Document model tracking individual PDF files, their metadata, hash, and status.
"""
from datetime import datetime
from backend.app.extensions import db


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.String(64), primary_key=True)  # e.g., DOC0001 or DOC-uuid
    job_id = db.Column(db.String(64), db.ForeignKey("processing_jobs.id"), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    s3_key = db.Column(db.String(512), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False, index=True)  # SHA-256
    file_size = db.Column(db.BigInteger, default=0, nullable=False)
    page_count = db.Column(db.Integer, default=1, nullable=False)
    document_type = db.Column(db.String(128), default="Unidentified", nullable=False, index=True)
    status = db.Column(db.String(32), default="pending", nullable=False, index=True)
    # Statuses: 'pending', 'queued', 'processing', 'completed', 'review_required', 'failed'
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    confidence_average = db.Column(db.Float, default=0.0, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    job = db.relationship("ProcessingJob", back_populates="documents")
    records = db.relationship(
        "ExtractedRecord",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ExtractedRecord.record_number",
        lazy="selectin"
    )
    verification_logs = db.relationship(
        "VerificationLog",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def to_dict(self, include_records=False):
        data = {
            "id": self.id,
            "job_id": self.job_id,
            "original_filename": self.original_filename,
            "s3_key": self.s3_key,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "page_count": self.page_count,
            "document_type": self.document_type,
            "status": self.status,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "confidence_average": round(self.confidence_average, 2),
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }
        if include_records:
            data["records"] = [record.to_dict() for record in self.records]
        return data


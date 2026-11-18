"""
Extracted Record model representing document sections and logical records/table rows.
"""
from datetime import datetime
from backend.app.extensions import db


class ExtractedRecord(db.Model):
    __tablename__ = "extracted_records"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.String(64), db.ForeignKey("documents.id"), nullable=False, index=True)
    section = db.Column(db.String(128), default="General Information", nullable=False)
    record_number = db.Column(db.Integer, default=1, nullable=False)  # Row number or sequential index
    page_number = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = db.relationship("Document", back_populates="records")
    fields = db.relationship(
        "ExtractedField",
        back_populates="record",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "section": self.section,
            "record_number": self.record_number,
            "page_number": self.page_number,
            "fields": [f.to_dict() for f in self.fields],
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


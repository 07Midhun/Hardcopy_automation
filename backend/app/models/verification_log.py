"""
Verification Log model maintaining audit trails of all manual reviews and corrections.
"""
from datetime import datetime
from backend.app.extensions import db


class VerificationLog(db.Model):
    __tablename__ = "verification_logs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.String(64), db.ForeignKey("documents.id"), nullable=False, index=True)
    extracted_field_id = db.Column(db.Integer, db.ForeignKey("extracted_fields.id"), nullable=False, index=True)
    original_value = db.Column(db.Text, nullable=True)
    corrected_value = db.Column(db.Text, nullable=True)
    verified_by = db.Column(db.String(80), default="system", nullable=False)
    verified_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    document = db.relationship("Document", back_populates="verification_logs")
    extracted_field = db.relationship("ExtractedField", back_populates="verification_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "extracted_field_id": self.extracted_field_id,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "notes": self.notes
        }


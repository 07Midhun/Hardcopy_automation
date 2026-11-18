"""
Extracted Field model representing an individual key-value pair or table cell.
"""
from backend.app.extensions import db


class ExtractedField(db.Model):
    __tablename__ = "extracted_fields"

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("extracted_records.id"), nullable=False, index=True)
    field_name = db.Column(db.String(128), nullable=False, index=True)
    original_extracted_value = db.Column(db.Text, nullable=True)  # Raw unadulterated AI output
    current_value = db.Column(db.Text, nullable=True)             # User-verified or corrected value
    confidence_score = db.Column(db.Float, default=1.0, nullable=False)
    verification_status = db.Column(db.String(32), default="pending", nullable=False, index=True)
    # Statuses: 'verified', 'review_required', 'unreadable', 'missing', 'pending'
    source_coordinates = db.Column(db.JSON, nullable=True)  # {"bbox": [x0, y0, x1, y1], "polygon": [...]}

    # Relationships
    record = db.relationship("ExtractedRecord", back_populates="fields")
    verification_logs = db.relationship(
        "VerificationLog",
        back_populates="extracted_field",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "record_id": self.record_id,
            "field_name": self.field_name,
            "original_extracted_value": self.original_extracted_value,
            "current_value": self.current_value,
            "confidence_score": round(self.confidence_score, 2),
            "verification_status": self.verification_status,
            "source_coordinates": self.source_coordinates
        }


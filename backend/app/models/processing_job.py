"""
Processing Job model to track bulk upload batches and progress metrics.
"""
from datetime import datetime
from backend.app.extensions import db


class ProcessingJob(db.Model):
    __tablename__ = "processing_jobs"

    id = db.Column(db.String(64), primary_key=True)  # e.g., JOB-20261117-ABCDEF
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    batch_name = db.Column(db.String(255), nullable=True)
    total_documents = db.Column(db.Integer, default=0, nullable=False)
    completed_documents = db.Column(db.Integer, default=0, nullable=False)
    failed_documents = db.Column(db.Integer, default=0, nullable=False)
    review_required_documents = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(32), default="pending", nullable=False, index=True)
    # Statuses: 'pending', 'queued', 'processing', 'completed', 'review_required', 'failed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship("User", back_populates="jobs")
    documents = db.relationship(
        "Document",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    @property
    def pending_documents(self) -> int:
        processed = self.completed_documents + self.failed_documents + self.review_required_documents
        return max(0, self.total_documents - processed)

    @property
    def progress_percentage(self) -> float:
        if self.total_documents == 0:
            return 0.0
        if self.status == "failed" and self.completed_documents == 0 and self.review_required_documents == 0:
            return 0.0
        processed = self.completed_documents + self.review_required_documents
        return round((processed / self.total_documents) * 100.0, 1)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "batch_name": self.batch_name,
            "total_documents": self.total_documents,
            "completed_documents": self.completed_documents,
            "failed_documents": self.failed_documents,
            "review_required_documents": self.review_required_documents,
            "pending_documents": self.pending_documents,
            "progress_percentage": self.progress_percentage,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


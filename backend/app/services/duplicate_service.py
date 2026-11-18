"""
Duplicate Detection Service.
Detects duplicate file uploads via SHA-256 content hashes to prevent redundant processing.
"""
from typing import Optional
from backend.app.models.document import Document
from backend.app.extensions import db


class DuplicateService:
    """Service to check document duplication."""

    @staticmethod
    def find_duplicate_by_hash(file_hash: str) -> Optional[Document]:
        """Find existing document matching SHA-256 hash."""
        return db.session.query(Document).filter_by(file_hash=file_hash).first()

    @staticmethod
    def is_duplicate(file_hash: str) -> bool:
        """Check if hash already exists in database."""
        return db.session.query(
            db.session.query(Document).filter_by(file_hash=file_hash).exists()
        ).scalar()


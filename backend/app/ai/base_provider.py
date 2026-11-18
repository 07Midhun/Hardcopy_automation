"""
Base abstract class for document understanding and OCR providers.
Enforces unified extraction contract across Azure, Vision LLMs, and local fallbacks.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from backend.app.ai.schemas import DocumentExtractionResult


class BaseAIProvider(ABC):
    """Abstract interface for AI Document Intelligence providers."""

    def __init__(self, confidence_threshold: float = 0.75):
        self.confidence_threshold = confidence_threshold

    @abstractmethod
    def extract_document(
        self,
        document_id: str,
        filename: str,
        image_path: Path,
        pdf_path: Optional[Path] = None,
        embedded_text: Optional[str] = None
    ) -> DocumentExtractionResult:
        """
        Process the document and extract structured records and fields.
        """
        pass

    def determine_status(self, value: Optional[str], confidence: float) -> str:
        """Utility to assign verification status according to confidence and value presence."""
        if value is None or str(value).strip() == "":
            return "missing"
        if "[unreadable]" in str(value).lower() or "[illegible]" in str(value).lower():
            return "unreadable"
        if confidence < self.confidence_threshold:
            return "review_required"
        return "verified"


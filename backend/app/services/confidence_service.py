"""
Confidence Service.
Calculates aggregate confidence metrics across fields, records, and entire documents.
"""
from typing import List
from backend.app.ai.schemas import FieldExtraction, DocumentExtractionResult


class ConfidenceService:
    """Calculates statistical confidence indicators."""

    @staticmethod
    def calculate_average_confidence(fields: List[FieldExtraction]) -> float:
        if not fields:
            return 0.0
        return sum(f.confidence for f in fields) / len(fields)

    @classmethod
    def calculate_document_confidence(cls, result: DocumentExtractionResult) -> float:
        all_fields = []
        for record in result.records:
            all_fields.extend(record.fields)
        return cls.calculate_average_confidence(all_fields)


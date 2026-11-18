"""
AI Extraction Module export.
"""
from backend.app.ai.base_provider import BaseAIProvider
from backend.app.ai.azure_provider import AzureDocumentIntelligenceProvider
from backend.app.ai.vision_provider import VisionAIProvider
from backend.app.ai.fallback_provider import FallbackDocumentProvider
from backend.app.ai.provider_factory import get_ai_provider
from backend.app.ai.schemas import DocumentExtractionResult, RecordExtraction, FieldExtraction

__all__ = [
    "BaseAIProvider",
    "AzureDocumentIntelligenceProvider",
    "VisionAIProvider",
    "FallbackDocumentProvider",
    "get_ai_provider",
    "DocumentExtractionResult",
    "RecordExtraction",
    "FieldExtraction"
]


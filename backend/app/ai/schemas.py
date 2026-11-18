"""
Pydantic schemas for standardized intermediate document representation.
Enforces strict typing and validation across all AI/OCR providers.
"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class FieldExtraction(BaseModel):
    """Single extracted field (key-value pair or table cell)."""
    field_name: str = Field(..., description="Normalized field label, e.g. 'Ward Number'")
    value: Optional[str] = Field(None, description="Recognized printed or handwritten value")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    verification_status: str = Field(
        "pending",
        description="One of: 'verified', 'review_required', 'unreadable', 'missing', 'pending'"
    )
    coordinates: Optional[Dict[str, Any]] = Field(
        None,
        description="Bounding box or polygon {'bbox': [x0, y0, x1, y1]}"
    )


class RecordExtraction(BaseModel):
    """A logical group of fields (e.g. general info block or a single table row)."""
    section: str = Field("General Information", description="Section or table title")
    record_number: int = Field(1, description="Row index or record sequence number within section")
    page_number: int = Field(1, description="Source page number")
    fields: List[FieldExtraction] = Field(default_factory=list)


class DocumentExtractionResult(BaseModel):
    """Complete standardized extraction result for a single document."""
    document_id: str = Field(..., description="Unique document identifier")
    source_filename: str = Field(..., description="Original filename of the PDF")
    document_type: str = Field("Unidentified", description="Detected category e.g. 'CCMS Installation Report'")
    page_count: int = Field(1, description="Total pages processed")
    classification_confidence: float = Field(1.0, ge=0.0, le=1.0)
    records: List[RecordExtraction] = Field(default_factory=list)
    raw_response: Optional[str] = Field(None, description="Original raw response from AI provider")
    error: Optional[str] = Field(None, description="Error message if extraction partially or fully failed")


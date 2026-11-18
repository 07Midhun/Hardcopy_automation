"""
Normalization Service.
Standardizes field names and formats values while strictly obeying handwriting preservation rules:
Never autocorrect names, never invent digits, preserve leading zeros.
"""
import re
from typing import Optional
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


class NormalizationService:
    """Normalizes field names and cleans data without altering source truth."""

    @staticmethod
    def normalize_field_name(raw_name: str) -> str:
        """
        Clean and standardize field names:
        e.g. '  Ward No. : ' -> 'Ward No.'
        """
        if not raw_name:
            return "Unnamed Field"

        cleaned = raw_name.strip(" :;=-_\t\n\r")
        # Collapse multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned if cleaned else "Unnamed Field"

    @staticmethod
    def clean_value(raw_val: Optional[str]) -> Optional[str]:
        """
        Trims whitespace around values while preserving exact internal spelling,
        symbols, and leading zeros.
        """
        if raw_val is None:
            return None
        cleaned = str(raw_val).strip()
        return cleaned if cleaned != "" else None


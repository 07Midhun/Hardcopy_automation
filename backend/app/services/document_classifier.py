"""
Intelligent Document Classification Service.
Analyzes layout features, text keywords, and document headers to classify document categories dynamically.
"""
from typing import Tuple, Dict, Any, List
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


class DocumentClassifierService:
    """Classifies document layouts into structured categories."""

    CATEGORIES = {
        "CCMS Installation Report": [
            "ccms", "pole", "ward", "feeder", "lamp", "led", "wattage", "lux",
            "phase", "earthing", "contractor", "centralized control and monitoring"
        ],
        "Inspection Report": [
            "inspection", "inspector", "observation", "compliance", "defect",
            "audit", "checklist", "verification status", "passed", "deviation"
        ],
        "Survey Form": [
            "survey", "cadastral", "plot", "boundary", "land", "measurement",
            "dimension", "surveyor", "topography", "sector"
        ],
        "Application Form": [
            "application", "applicant", "father", "dob", "address", "signature of applicant",
            "enclosure", "candidate", "submission date"
        ],
        "Technical Report": [
            "technical", "specification", "test results", "tolerance", "calibration",
            "schematic", "operating voltage", "ambient temperature", "engineering"
        ]
    }

    @classmethod
    def classify(cls, text: str, filename: str = "", layout_hints: Dict[str, Any] = None) -> Tuple[str, float]:
        """
        Classifies document based on text content, keywords, and structural layout hints.
        Returns: (document_type, confidence_score)
        """
        combined = (text + " " + filename).lower()
        if not combined.strip():
            return "Unidentified Document", 0.30

        scores: Dict[str, int] = {}
        for category, keywords in cls.CATEGORIES.items():
            match_count = sum(1 for kw in keywords if kw in combined)
            scores[category] = match_count

        best_category = max(scores, key=scores.get)
        best_count = scores[best_category]

        if best_count >= 3:
            confidence = min(0.98, 0.70 + (best_count * 0.05))
            return best_category, round(confidence, 2)
        elif best_count >= 1:
            return best_category, 0.65
        else:
            return "Unidentified Document", 0.40


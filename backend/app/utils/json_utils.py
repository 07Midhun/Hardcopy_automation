"""
JSON parsing and serialization utilities, including LLM markdown-block extraction.
"""
import json
import re
from datetime import datetime, date
from typing import Any, Dict, Optional


class DocumentJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder handling datetime, date, and decimal."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def clean_and_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Safely extract and parse JSON from model output or raw text.
    Handles Markdown code fences (```json ... ```) and trailing commas.
    """
    if not text:
        return None

    cleaned = text.strip()

    # Extract block from ```json ... ``` or ``` ... ```
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(fence_pattern, cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try basic repairs: remove trailing commas before } or ]
        repaired = re.sub(r",\s*([\}\]])", r"\1", cleaned)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None


def to_json_str(data: Any, indent: int = 2) -> str:
    """Serialize object to JSON string with custom encoder."""
    return json.dumps(data, cls=DocumentJSONEncoder, indent=indent, ensure_ascii=False)


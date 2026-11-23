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


def clean_and_parse_json(text: str) -> Optional[Any]:
    """
    Safely extract and parse JSON from model output or raw text.
    Handles Markdown code fences (```json ... ```), trailing commas,
    outer wrappers, and truncated responses via backtracking.
    """
    if not text:
        return None

    cleaned = text.strip()

    # Extract block from ```json ... ``` or ``` ... ```
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(fence_pattern, cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    # 1. Direct parse attempt
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2. Basic trailing comma repair before } or ]
    repaired = re.sub(r",\s*([\}\]])", r"\1", cleaned)
    try:
        return json.loads(repaired)
    except Exception:
        pass

    # 3. Extract outermost { ... } or [ ... ]
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        snippet = cleaned[first_brace:last_brace + 1]
        try:
            return json.loads(snippet)
        except Exception:
            try:
                snippet_repaired = re.sub(r",\s*([\}\]])", r"\1", snippet)
                return json.loads(snippet_repaired)
            except Exception:
                pass

    # 4. Truncated JSON recovery: backtrack to last completed record in array
    if first_brace != -1:
        prefix = cleaned[first_brace:]
        # Find all occurrences of '}' in reverse and test candidate closures
        brace_indices = [m.start() for m in re.finditer(r'\}', prefix)]
        for idx in reversed(brace_indices[-50:]):  # check up to 50 recent closing braces
            candidate = prefix[:idx + 1]
            for closer in [']}', '}', '}}', ']}}']:
                try:
                    repaired_cand = candidate + closer
                    repaired_cand = re.sub(r",\s*([\}\]])", r"\1", repaired_cand)
                    return json.loads(repaired_cand)
                except Exception:
                    continue

    return None


def to_json_str(data: Any, indent: int = 2) -> str:
    """Serialize object to JSON string with custom encoder."""
    return json.dumps(data, cls=DocumentJSONEncoder, indent=indent, ensure_ascii=False)


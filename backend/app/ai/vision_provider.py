"""
Configurable Vision AI Provider supporting OpenAI (GPT-4o), Google Gemini, and Anthropic Claude.
Specialized for complex cursive handwriting, stamps, non-standard tables, and layout understanding.
"""
import base64
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from backend.app.ai.base_provider import BaseAIProvider
from backend.app.ai.schemas import DocumentExtractionResult, RecordExtraction, FieldExtraction
from backend.app.ai.prompts import DOCUMENT_UNDERSTANDING_SYSTEM_PROMPT, DOCUMENT_EXTRACTION_USER_PROMPT
from backend.app.utils.json_utils import clean_and_parse_json
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


class VisionAIProvider(BaseAIProvider):
    """Vision-based LLM Document Extractor."""

    def __init__(
        self,
        service: str = "openai",  # 'openai', 'gemini', 'claude'
        api_key: str = "",
        model_name: Optional[str] = None,
        confidence_threshold: float = 0.75
    ):
        super().__init__(confidence_threshold)
        self.service = service.lower()
        self.api_key = api_key
        self.model_name = model_name or self._default_model_name()

    def _default_model_name(self) -> str:
        if self.service == "gemini":
            return "gemini-3.5-flash-lite"
        elif self.service == "claude":
            return "claude-3-5-sonnet-20241022"
        return "gpt-4o"

    def extract_document(
        self,
        document_id: str,
        filename: str,
        image_path: Path,
        pdf_path: Optional[Path] = None,
        embedded_text: Optional[str] = None
    ) -> DocumentExtractionResult:
        if not self.api_key:
            raise ValueError(f"API key for vision provider '{self.service}' is missing.")

        # Read and encode image to base64
        with open(image_path, "rb") as img_file:
            image_b64 = base64.b64encode(img_file.read()).decode("utf-8")

        prompt = DOCUMENT_EXTRACTION_USER_PROMPT.format(
            filename=filename,
            document_id=document_id,
            embedded_text=embedded_text or "No selectable digital text detected."
        )

        logger.info(f"Extracting document {document_id} via Vision AI ({self.service}: {self.model_name})...")
        if self.service == "gemini":
            raw_response = self._call_gemini(prompt, image_b64)
        elif self.service == "claude":
            raw_response = self._call_claude(prompt, image_b64)
        else:
            raw_response = self._call_openai(prompt, image_b64)

        parsed = clean_and_parse_json(raw_response)
        if parsed is None:
            logger.error(f"Malformed or non-JSON output from Vision AI: {raw_response[:300]}")
            raise ValueError("Vision AI returned invalid JSON structure.")

        # Normalize parsed output into { "records": [...], "document_type": ... }
        if isinstance(parsed, list):
            if len(parsed) == 1 and isinstance(parsed[0], dict) and "records" in parsed[0]:
                parsed = parsed[0]
            else:
                parsed = {
                    "document_type": "CCMS Installation Report",
                    "classification_confidence": 0.90,
                    "records": parsed
                }
        elif isinstance(parsed, dict):
            # Check nested candidate keys
            for candidate_key in ["data", "extraction", "document_extraction", "document", "response"]:
                if candidate_key in parsed and isinstance(parsed[candidate_key], dict) and "records" in parsed[candidate_key]:
                    parsed = parsed[candidate_key]
                    break
            # Check alternative naming
            for alt_key in ["Records", "table_records", "table", "records_list", "items"]:
                if alt_key in parsed and "records" not in parsed:
                    parsed["records"] = parsed.pop(alt_key)
                    break
            # If records key is still missing, adapt fields or top-level keys
            if "records" not in parsed:
                if "fields" in parsed:
                    parsed["records"] = [{"section": "General Information", "record_number": 1, "fields": parsed["fields"]}]
                else:
                    rec_fields = []
                    for k, v in parsed.items():
                        if k not in ("document_type", "classification_confidence"):
                            rec_fields.append({"field_name": k, "value": str(v), "confidence": 0.85, "verification_status": "verified"})
                    parsed["records"] = [{"section": "General Information", "record_number": 1, "fields": rec_fields}]

        return self._transform_json_result(document_id, filename, parsed, raw_response)

    GEMINI_FALLBACK_MODELS = [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-flash-latest",
    ]

    def _post_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        provider_label: str = "Vision AI",
        max_retries: int = 4
    ) -> requests.Response:
        """Send POST request with exponential backoff for HTTP 429/503 rate limits, DNS errors, and timeouts."""
        delay = 3.0
        for attempt in range(1, max_retries + 1):
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=35)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
                if attempt < max_retries:
                    logger.warning(
                        f"{provider_label} network/connection error ({type(net_err).__name__}: {net_err}). "
                        f"Retrying in {delay:.1f}s (attempt {attempt}/{max_retries})..."
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, 30.0)
                    continue
                raise RuntimeError(f"{provider_label} TRANSIENT_FAILURE network error after {max_retries} attempts: {net_err}")

            if res.status_code == 200:
                return res

            # Daily quota exhaustion cannot be solved by sleeping; bubble up immediately for model fallback
            if res.status_code == 429 and ("PerDay" in res.text or "per day" in res.text.lower()):
                raise RuntimeError(f"{provider_label} DAILY_QUOTA_EXCEEDED (HTTP 429): {res.text}")

            if res.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                retry_after = res.headers.get("Retry-After")
                wait_sec = float(retry_after) if (retry_after and retry_after.isdigit()) else delay
                logger.warning(
                    f"{provider_label} transient/rate-limit error (HTTP {res.status_code}). "
                    f"Retrying in {wait_sec:.1f}s (attempt {attempt}/{max_retries})..."
                )
                time.sleep(wait_sec)
                delay = min(delay * 2, 30.0)
                continue
            raise RuntimeError(f"{provider_label} API Error {res.status_code}: {res.text}")
        raise RuntimeError(f"{provider_label} TRANSIENT_FAILURE failed after {max_retries} retries.")

    def _call_openai(self, prompt: str, image_b64: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": DOCUMENT_UNDERSTANDING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "high"}
                        }
                    ]
                }
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }

        res = self._post_with_retry(
            "https://api.openai.com/v1/chat/completions",
            payload=payload,
            headers=headers,
            provider_label="OpenAI"
        )
        return res.json()["choices"][0]["message"]["content"]

    def _call_gemini(self, prompt: str, image_b64: str) -> str:
        payload = {
            "system_instruction": {
                "parts": [{"text": DOCUMENT_UNDERSTANDING_SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.0,
                "maxOutputTokens": 8192
            }
        }

        # Build ordered candidate list starting from configured model, then fallback models
        candidates = [self.model_name] + [m for m in self.GEMINI_FALLBACK_MODELS if m != self.model_name]
        last_error = None

        for model_id in candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={self.api_key}"
            try:
                res = self._post_with_retry(url, payload=payload, provider_label=f"Gemini ({model_id})")
                if model_id != self.model_name:
                    logger.info(f"Switched active Gemini model to '{model_id}' for remaining pages.")
                    self.model_name = model_id
                parts = res.json()["candidates"][0]["content"]["parts"]
                text_parts = [p.get("text", "") for p in parts if not p.get("thought") and p.get("text")]
                return text_parts[-1] if text_parts else parts[0].get("text", "")
            except RuntimeError as err:
                err_str = str(err)
                last_error = err
                if any(tok in err_str for tok in ("DAILY_QUOTA_EXCEEDED", "TRANSIENT_FAILURE", "HTTP 404", "Error 404", "Error 429", "Error 503", "Error 504", "ReadTimeout")):
                    logger.warning(f"Gemini model '{model_id}' unavailable/overloaded; trying next model...")
                    continue
                raise

        raise RuntimeError(f"All Gemini models failed or exhausted quota. Last error: {last_error}")

    def _call_claude(self, prompt: str, image_b64: str) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "system": DOCUMENT_UNDERSTANDING_SYSTEM_PROMPT,
            "max_tokens": 4096,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
        }
        res = self._post_with_retry(
            "https://api.anthropic.com/v1/messages",
            payload=payload,
            headers=headers,
            provider_label="Anthropic"
        )
        return res.json()["content"][0]["text"]

    def _transform_json_result(
        self,
        document_id: str,
        filename: str,
        data: Dict[str, Any],
        raw_response: str
    ) -> DocumentExtractionResult:
        doc_type = data.get("document_type", "Unidentified Document")
        try:
            class_conf = float(data.get("classification_confidence", 0.90))
        except (ValueError, TypeError):
            class_conf = 0.90

        records: List[RecordExtraction] = []
        for rec in data.get("records", []):
            section_name = rec.get("section", "General Information")
            try:
                rec_num = int(rec.get("record_number", 1))
            except (ValueError, TypeError):
                rec_num = 1
            try:
                page_num = int(rec.get("page_number", 1))
            except (ValueError, TypeError):
                page_num = 1

            fields: List[FieldExtraction] = []
            for f in rec.get("fields", []):
                fname = f.get("field_name", "").strip()
                if not fname:
                    continue
                val = f.get("value")
                try:
                    conf = float(f.get("confidence", 0.85))
                except (ValueError, TypeError):
                    conf = 0.85
                status = f.get("verification_status") or self.determine_status(val, conf)
                coords = f.get("coordinates")

                fields.append(FieldExtraction(
                    field_name=fname,
                    value=str(val).strip() if val is not None else None,
                    confidence=conf,
                    verification_status=status,
                    coordinates=coords
                ))

            if fields:
                records.append(RecordExtraction(
                    section=section_name,
                    record_number=rec_num,
                    page_number=page_num,
                    fields=fields
                ))

        return DocumentExtractionResult(
            document_id=document_id,
            source_filename=filename,
            document_type=doc_type,
            classification_confidence=class_conf,
            records=records,
            raw_response=raw_response
        )


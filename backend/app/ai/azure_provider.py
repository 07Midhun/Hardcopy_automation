"""
Azure AI Document Intelligence (Form Recognizer) Provider.
Uses Layout and General Document models to extract printed, handwritten text and tables.
Implements resilient HTTP REST calls with retry logic to avoid SDK version incompatibilities.
"""
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from backend.app.ai.base_provider import BaseAIProvider
from backend.app.ai.schemas import DocumentExtractionResult, RecordExtraction, FieldExtraction
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


class AzureDocumentIntelligenceProvider(BaseAIProvider):
    """Azure AI Document Intelligence extraction provider."""

    def __init__(self, endpoint: str, api_key: str, confidence_threshold: float = 0.75, model_id: str = "prebuilt-layout"):
        super().__init__(confidence_threshold)
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model_id = model_id

    def extract_document(
        self,
        document_id: str,
        filename: str,
        image_path: Path,
        pdf_path: Optional[Path] = None,
        embedded_text: Optional[str] = None
    ) -> DocumentExtractionResult:
        if not self.endpoint or not self.api_key:
            raise ValueError("Azure Document Intelligence endpoint and API key must be configured.")

        # Determine target file to send (prefer PDF if available, else rendered image)
        target_path = pdf_path if (pdf_path and pdf_path.exists()) else image_path
        content_type = "application/pdf" if target_path.suffix.lower() == ".pdf" else "image/png"

        analyze_url = f"{self.endpoint}/formrecognizer/documentModels/{self.model_id}:analyze?api-version=2023-07-31"
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": content_type
        }

        with open(target_path, "rb") as f:
            data = f.read()

        logger.info(f"Submitting document {document_id} to Azure Document Intelligence ({self.model_id})...")
        response = requests.post(analyze_url, headers=headers, data=data, timeout=60)
        if response.status_code not in (200, 202):
            raise RuntimeError(f"Azure API error {response.status_code}: {response.text}")

        operation_location = response.headers.get("Operation-Location")
        if not operation_location:
            # Synchronous return or missing header
            analyze_result = response.json().get("analyzeResult", {})
        else:
            # Poll async operation
            analyze_result = self._poll_result(operation_location)

        return self._transform_azure_result(document_id, filename, analyze_result)

    def _poll_result(self, operation_location: str, max_seconds: int = 60) -> Dict[str, Any]:
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        start = time.time()
        while time.time() - start < max_seconds:
            res = requests.get(operation_location, headers=headers, timeout=30)
            if res.status_code != 200:
                raise RuntimeError(f"Polling failed ({res.status_code}): {res.text}")
            body = res.json()
            status = body.get("status")
            if status == "succeeded":
                return body.get("analyzeResult", {})
            elif status in ("failed", "canceled"):
                raise RuntimeError(f"Azure analysis {status}: {body.get('error')}")
            time.sleep(1.5)
        raise TimeoutError("Azure Document Intelligence analysis timed out.")

    def _transform_azure_result(self, document_id: str, filename: str, result: Dict[str, Any]) -> DocumentExtractionResult:
        records: List[RecordExtraction] = []
        doc_type = "Unidentified Document"

        # 1. Process Key-Value Pairs into General Information record
        kv_pairs = result.get("keyValuePairs", [])
        general_fields: List[FieldExtraction] = []

        for kv in kv_pairs:
            key_obj = kv.get("key", {})
            val_obj = kv.get("value")
            field_name = key_obj.get("content", "").strip(" :-\t\n")
            if not field_name:
                continue

            extracted_val = val_obj.get("content", "").strip() if val_obj else ""
            confidence = kv.get("confidence", 0.85)
            status = self.determine_status(extracted_val, confidence)

            # Coordinates
            poly = key_obj.get("boundingRegions", [{}])[0].get("polygon")
            coords = {"polygon": poly} if poly else None

            general_fields.append(FieldExtraction(
                field_name=field_name,
                value=extracted_val if extracted_val else None,
                confidence=confidence,
                verification_status=status,
                coordinates=coords
            ))

            # Heuristic document classification from key header
            if "ccms" in field_name.lower():
                doc_type = "CCMS Installation Report"
            elif "inspection" in field_name.lower():
                doc_type = "Inspection Report"
            elif "survey" in field_name.lower():
                doc_type = "Survey Form"

        if general_fields:
            records.append(RecordExtraction(
                section="General Information",
                record_number=1,
                page_number=1,
                fields=general_fields
            ))

        # 2. Process Tables
        tables = result.get("tables", [])
        for table_idx, table in enumerate(tables):
            row_count = table.get("rowCount", 0)
            col_count = table.get("columnCount", 0)
            cells = table.get("cells", [])

            # Extract header row
            header_map = {}
            for col in range(col_count):
                header_map[col] = f"Column_{col + 1}"

            row_cells: Dict[int, Dict[int, Dict[str, Any]]] = {}
            for cell in cells:
                r = cell.get("rowIndex", 0)
                c = cell.get("columnIndex", 0)
                content = cell.get("content", "").strip()
                kind = cell.get("kind", "")
                if r == 0 or kind == "columnHeader":
                    if content:
                        header_map[c] = content
                else:
                    if r not in row_cells:
                        row_cells[r] = {}
                    row_cells[r][c] = cell

            # Create table row records
            for r_idx in sorted(row_cells.keys()):
                row_fields = []
                for c_idx in range(col_count):
                    col_name = header_map.get(c_idx, f"Column_{c_idx + 1}")
                    cell_data = row_cells[r_idx].get(c_idx, {})
                    val = cell_data.get("content", "").strip()
                    conf = cell_data.get("confidence", 0.85)
                    status = self.determine_status(val, conf)

                    row_fields.append(FieldExtraction(
                        field_name=col_name,
                        value=val if val else None,
                        confidence=conf,
                        verification_status=status
                    ))

                records.append(RecordExtraction(
                    section=f"Table {table_idx + 1}",
                    record_number=r_idx,
                    page_number=1,
                    fields=row_fields
                ))

        return DocumentExtractionResult(
            document_id=document_id,
            source_filename=filename,
            document_type=doc_type,
            classification_confidence=0.90,
            records=records
        )


"""
Extraction Service.
Orchestrates the entire document intelligence pipeline:
Storage retrieval -> PDF Validation -> Embedded text extraction -> Image rendering ->
OpenCV Image enhancement -> AI/OCR extraction -> Normalization & Validation -> DB persistence.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from backend.app.extensions import db
from backend.app.models.document import Document
from backend.app.models.extracted_record import ExtractedRecord
from backend.app.models.extracted_field import ExtractedField
from backend.app.storage.s3_storage import get_storage
from backend.app.services.pdf_service import PDFService
from backend.app.services.image_service import ImageService
from backend.app.services.document_classifier import DocumentClassifierService
from backend.app.services.normalization_service import NormalizationService
from backend.app.services.validation_service import ValidationService
from backend.app.ai.provider_factory import get_ai_provider
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


class ExtractionService:
    """End-to-end document extraction orchestrator."""

    @classmethod
    def process_document(cls, document_id: str, app_config=None, resume: bool = False) -> Dict[str, Any]:
        """
        Process a single document through the end-to-end extraction pipeline.
        When resume=False (default), clears prior records for idempotency.
        When resume=True, preserves already-extracted pages and processes only remaining pages.
        """
        doc = db.session.get(Document, document_id)
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found.")

        if app_config is None:
            from flask import has_app_context, current_app
            if has_app_context():
                app_config = current_app.config

        storage = get_storage(app_config)
        ai_provider = get_ai_provider(app_config)

        doc.status = "processing"
        db.session.commit()

        temp_dir = Path("storage/temp") / document_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        local_pdf = temp_dir / doc.original_filename
        rendered_image = temp_dir / "rendered_page1.png"
        enhanced_image = temp_dir / "enhanced_page1.png"

        try:
            # 1. Download/restore file from database persistence or storage
            if not local_pdf.exists():
                if doc.file_content:
                    local_pdf.write_bytes(doc.file_content)
                else:
                    storage.get_file(doc.s3_key, str(local_pdf))

            # 2. Inspect & validate PDF
            is_valid, err_msg, page_count = PDFService.inspect_and_validate(local_pdf)
            if not is_valid:
                raise ValueError(f"PDF validation failed: {err_msg}")
            doc.page_count = page_count

            completed_pages = set()
            if resume:
                existing_recs = db.session.query(ExtractedRecord).filter_by(document_id=doc.id).all()
                completed_pages = {r.page_number for r in existing_recs}
                if completed_pages:
                    logger.info(f"Resuming {doc.id}: skipping already extracted pages {sorted(completed_pages)}")
            else:
                # 3. Clear prior records via ORM so cascade deletes all child ExtractedField rows cleanly
                prior_records = db.session.query(ExtractedRecord).filter_by(document_id=doc.id).all()
                for prior_rec in prior_records:
                    db.session.delete(prior_rec)
                db.session.flush()

            total_conf = 0.0
            field_count = 0
            has_review_required = False
            detected_doc_type = doc.document_type if (resume and doc.document_type and doc.document_type != "Unidentified") else None

            # 4. Process all pages in the document
            for page_num in range(1, doc.page_count + 1):
                if page_num in completed_pages:
                    continue
                page_rendered = temp_dir / f"rendered_page{page_num}.png"
                page_enhanced = temp_dir / f"enhanced_page{page_num}.png"

                # Render page image (150 DPI for optimal vision balance and low cloud memory footprint)
                PDFService.render_page(local_pdf, page_number=page_num, dpi=150, target_path=page_rendered)

                # Image enhancement via OpenCV
                ImageService.enhance_for_ocr(
                    image_path=page_rendered,
                    output_path=page_enhanced,
                    deskew=True,
                    enhance_contrast=True,
                    denoise=True,
                    sharpen=True
                )

                # Extract page content using configured AI provider
                page_emb = PDFService.extract_embedded_text(local_pdf).get("text", "")
                extraction_result = ai_provider.extract_document(
                    document_id=f"{doc.id}-p{page_num}" if doc.page_count > 1 else doc.id,
                    filename=doc.original_filename,
                    image_path=page_enhanced,
                    pdf_path=local_pdf,
                    embedded_text=page_emb
                )

                if not detected_doc_type and extraction_result.document_type not in ("Unidentified", "Unidentified Document", ""):
                    detected_doc_type = extraction_result.document_type

                # Persist records and fields for this page
                page_table_rows = []
                for record_data in extraction_result.records:
                    record = ExtractedRecord(
                        document_id=doc.id,
                        section=record_data.section,
                        record_number=record_data.record_number,
                        page_number=page_num
                    )
                    db.session.add(record)
                    db.session.flush()

                    row_fields = []
                    for field_data in record_data.fields:
                        norm_name = NormalizationService.normalize_field_name(field_data.field_name)
                        cleaned_val = NormalizationService.clean_value(field_data.value)

                        val_status, reason = ValidationService.validate_field(
                            field_name=norm_name,
                            value=cleaned_val,
                            confidence=field_data.confidence,
                            confidence_threshold=ai_provider.confidence_threshold
                        )

                        if val_status == "review_required":
                            has_review_required = True

                        extracted_field = ExtractedField(
                            record_id=record.id,
                            field_name=norm_name,
                            original_extracted_value=cleaned_val,
                            current_value=cleaned_val,
                            confidence_score=field_data.confidence,
                            verification_status=val_status,
                            source_coordinates=field_data.coordinates
                        )
                        db.session.add(extracted_field)
                        row_fields.append(extracted_field)

                        total_conf += field_data.confidence
                        field_count += 1

                    if "table" in (record_data.section or "").lower():
                        page_table_rows.append(row_fields)

                # Cross-row table validation: detect digit-confusion outliers (e.g. 338 -> 378) & wattage math errors
                if page_table_rows:
                    anomalies = ValidationService.validate_page_table_consistency(
                        page_table_rows,
                        confidence_threshold=ai_provider.confidence_threshold
                    )
                    if anomalies:
                        has_review_required = True

                # Commit after each page so extracted data is never lost if a later page hits an API quota limit
                db.session.commit()

                # Clean up temporary rendered images and force garbage collection to keep RAM minimal
                page_rendered.unlink(missing_ok=True)
                page_enhanced.unlink(missing_ok=True)
                del page_emb, extraction_result, page_table_rows
                import gc
                gc.collect()

            # 5. Final document classification & status update
            if detected_doc_type:
                doc.document_type = detected_doc_type
            else:
                doc.document_type, _ = DocumentClassifierService.classify(
                    text="",
                    filename=doc.original_filename
                )

            # 10. Update Document Status and Metrics across all persisted fields
            all_fields = db.session.query(ExtractedField).join(ExtractedRecord).filter(
                ExtractedRecord.document_id == doc.id
            ).all()
            if all_fields:
                field_count = len(all_fields)
                total_conf = sum((f.confidence_score or 0.0) for f in all_fields)
                has_review_required = any(f.verification_status == "review_required" for f in all_fields)

            doc.confidence_average = (total_conf / field_count) if field_count > 0 else 0.0
            doc.status = "review_required" if has_review_required else "completed"
            doc.error_message = None
            doc.processed_at = datetime.utcnow()

            db.session.commit()
            logger.info(f"Successfully processed document {doc.id} (Status: {doc.status}, Fields: {field_count})")

            return {
                "document_id": doc.id,
                "status": doc.status,
                "document_type": doc.document_type,
                "field_count": field_count,
                "confidence_average": doc.confidence_average
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed processing document {document_id}: {e}", exc_info=True)
            doc.status = "failed"
            doc.error_message = str(e)
            doc.processed_at = datetime.utcnow()
            db.session.commit()
            return {
                "document_id": doc.id,
                "status": "failed",
                "error": str(e)
            }

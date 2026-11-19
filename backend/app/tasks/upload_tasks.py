"""
Celery tasks for bulk ZIP archive ingestion and file registration.
"""
from pathlib import Path
from backend.app.tasks.celery_app import celery_app
from backend.app.extensions import db
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.document import Document
from backend.app.storage.s3_storage import get_storage
from backend.app.utils.file_utils import extract_zip_archive, calculate_sha256, get_file_size
from backend.app.services.duplicate_service import DuplicateService
from backend.app.tasks.processing_tasks import process_single_document_task
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task
def process_zip_upload_task(job_id: str, zip_file_path: str):
    """
    Extracts ZIP archive in background, validates all contained PDFs,
    stores them into S3/LocalStorage, registers them in PostgreSQL, and enqueues extraction.
    """
    job = db.session.get(ProcessingJob, job_id)
    if not job:
        logger.error(f"Job {job_id} not found.")
        return

    storage = get_storage()
    extract_target = Path("storage/temp") / f"zip_{job_id}"

    try:
        extracted = extract_zip_archive(zip_file_path, extract_target)
        job.total_documents = len(extracted)
        db.session.commit()

        registered_count = 0
        seen_hashes = set()
        for idx, (original_name, file_path) in enumerate(extracted, 1):
            file_hash = calculate_sha256(file_path)
            if file_hash in seen_hashes or DuplicateService.is_duplicate(file_hash):
                logger.info(f"Skipping duplicate ZIP PDF ({original_name}, Hash: {file_hash[:10]}...)")
                continue
            seen_hashes.add(file_hash)

            file_size = get_file_size(file_path)
            doc_id = f"DOC-{job_id[-6:]}-{idx:04d}"

            # Save to storage
            s3_key = f"documents/{job_id}/{doc_id}.pdf"
            storage.save_file(str(file_path), s3_key, content_type="application/pdf")

            # Register document in PostgreSQL
            doc = Document(
                id=doc_id,
                job_id=job_id,
                original_filename=original_name,
                s3_key=s3_key,
                file_hash=file_hash,
                file_size=file_size,
                status="queued"
            )
            db.session.add(doc)
            db.session.commit()
            registered_count += 1

            # Enqueue processing task
            from backend.app.tasks.processing_tasks import enqueue_document_processing
            enqueue_document_processing(doc.id)

        job.total_documents = registered_count
        db.session.commit()

        # Cleanup zip file
        Path(zip_file_path).unlink(missing_ok=True)
        return {"job_id": job_id, "documents_registered": registered_count}

    except Exception as e:
        logger.error(f"Failed to process ZIP upload for job {job_id}: {e}")
        job.status = "failed"
        db.session.commit()


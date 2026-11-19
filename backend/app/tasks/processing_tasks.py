"""
Celery processing tasks for asynchronous document extraction and job progression.
"""
import threading
from datetime import datetime
from backend.app.tasks.celery_app import celery_app
from backend.app.extensions import db
from backend.app.models.document import Document
from backend.app.models.processing_job import ProcessingJob
from backend.app.services.extraction_service import ExtractionService
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def enqueue_document_processing(document_id: str, flask_app=None, resume: bool = False):
    """
    Dispatch document extraction immediately:
      - Testing mode: runs synchronously for deterministic tests.
      - Production / Single Container / Render: executes in a dedicated background daemon thread.
    """
    from flask import current_app
    app_obj = flask_app or current_app._get_current_object()

    if app_obj.config.get("TESTING", False):
        ExtractionService.process_document(document_id, app_config=app_obj.config, resume=resume)
        doc = db.session.get(Document, document_id)
        if doc:
            _update_job_progress(doc.job_id)
        return

    def _run_in_thread():
        with app_obj.app_context():
            try:
                logger.info(f"Background worker started extraction for doc: {document_id} (resume={resume})")
                ExtractionService.process_document(document_id, app_config=app_obj.config, resume=resume)
                doc = db.session.get(Document, document_id)
                if doc:
                    _update_job_progress(doc.job_id)
                logger.info(f"Background worker completed extraction for doc: {document_id}")
            except Exception as exc:
                logger.error(f"Background worker failed for document {document_id}: {exc}", exc_info=True)
                doc = db.session.get(Document, document_id)
                if doc:
                    doc.status = "failed"
                    doc.error_message = str(exc)
                    db.session.commit()
                    _update_job_progress(doc.job_id)

    worker_thread = threading.Thread(
        target=_run_in_thread,
        daemon=True,
        name=f"doc-worker-{document_id}"
    )
    worker_thread.start()


def enqueue_zip_processing(job_id: str, zip_file_path: str, flask_app=None):
    """Dispatch ZIP ingestion cleanly in a background daemon thread."""
    from flask import current_app
    from backend.app.tasks.upload_tasks import process_zip_upload_task
    app_obj = flask_app or current_app._get_current_object()

    if app_obj.config.get("TESTING", False):
        process_zip_upload_task(job_id, zip_file_path)
        return

    def _run_zip_in_thread():
        with app_obj.app_context():
            try:
                process_zip_upload_task(job_id, zip_file_path)
            except Exception as exc:
                logger.error(f"Background ZIP worker failed for job {job_id}: {exc}", exc_info=True)

    worker_thread = threading.Thread(
        target=_run_zip_in_thread,
        daemon=True,
        name=f"zip-worker-{job_id}"
    )
    worker_thread.start()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def process_single_document_task(self, document_id: str):
    """
    Asynchronous Celery task processing a single document.
    Updates job counters atomically.
    """
    logger.info(f"Task {self.request.id} started for document {document_id}")
    doc = db.session.get(Document, document_id)
    if not doc:
        logger.error(f"Document {document_id} not found.")
        return {"error": "Document not found"}

    try:
        result = ExtractionService.process_document(document_id)
        _update_job_progress(doc.job_id)
        return result
    except Exception as exc:
        logger.error(f"Task failed for document {document_id}: {exc}")
        doc.retry_count += 1
        db.session.commit()
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))
        else:
            doc.status = "failed"
            doc.error_message = f"Max retries exceeded: {str(exc)}"
            db.session.commit()
            _update_job_progress(doc.job_id)
            return {"document_id": document_id, "status": "failed", "error": str(exc)}


@celery_app.task
def process_batch_job_task(job_id: str):
    """
    Enqueues individual tasks for all pending documents in a job batch.
    Ensures decoupled, resilient processing where one failed document never blocks others.
    """
    job = db.session.get(ProcessingJob, job_id)
    if not job:
        logger.error(f"Job {job_id} not found.")
        return

    job.status = "processing"
    db.session.commit()

    docs = db.session.query(Document).filter(
        Document.job_id == job_id,
        Document.status.in_(["pending", "queued"])
    ).all()

    logger.info(f"Dispatching {len(docs)} documents for job {job_id}...")
    for doc in docs:
        doc.status = "queued"
        db.session.commit()
        enqueue_document_processing(doc.id)

    return {"job_id": job_id, "enqueued": len(docs)}


def _update_job_progress(job_id: str):
    """Recalculate and update job progress metrics in PostgreSQL."""
    try:
        job = db.session.get(ProcessingJob, job_id)
        if not job:
            return

        completed = db.session.query(Document).filter_by(job_id=job_id, status="completed").count()
        failed = db.session.query(Document).filter_by(job_id=job_id, status="failed").count()
        review = db.session.query(Document).filter_by(job_id=job_id, status="review_required").count()

        job.completed_documents = completed
        job.failed_documents = failed
        job.review_required_documents = review

        processed = completed + failed + review
        if processed >= job.total_documents:
            job.status = "review_required" if review > 0 else ("failed" if completed == 0 else "completed")
            job.completed_at = datetime.utcnow()
        elif processed > 0:
            job.status = "processing"

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update job progress for {job_id}: {e}")


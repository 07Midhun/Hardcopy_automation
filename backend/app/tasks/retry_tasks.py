"""
Celery tasks for retrying failed or review-required documents.
"""
from backend.app.tasks.celery_app import celery_app
from backend.app.extensions import db
from backend.app.models.document import Document
from backend.app.tasks.processing_tasks import process_single_document_task
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task
def retry_document_task(document_id: str):
    """Reset status and re-run extraction on a single document."""
    doc = db.session.get(Document, document_id)
    if not doc:
        return {"error": "Document not found"}

    doc.status = "queued"
    doc.error_message = None
    db.session.commit()

    return process_single_document_task(document_id)


@celery_app.task
def retry_job_failed_documents_task(job_id: str):
    """Retry all failed documents within a job."""
    from backend.app.models.processing_job import ProcessingJob
    from backend.app.tasks.processing_tasks import enqueue_document_processing

    job = db.session.get(ProcessingJob, job_id)
    if job:
        job.status = "processing"
        job.completed_at = None
        db.session.commit()

    failed_docs = db.session.query(Document).filter_by(job_id=job_id, status="failed").all()
    for doc in failed_docs:
        doc.status = "queued"
        doc.error_message = None
        db.session.commit()
        enqueue_document_processing(doc.id, resume=True)

    return {"job_id": job_id, "retrying": len(failed_docs)}


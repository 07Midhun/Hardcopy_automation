"""
Processing Routes.
Provides endpoints for monitoring Celery jobs, live queue metrics, and batch retries.
"""
from flask import Blueprint, request, jsonify, render_template
from backend.app.extensions import db
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.document import Document
from backend.app.tasks.retry_tasks import retry_job_failed_documents_task
from backend.app.tasks.processing_tasks import process_batch_job_task
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)
processing_bp = Blueprint("processing", __name__)


# --- HTML Template Views ---
@processing_bp.route("/processing", methods=["GET"])
def processing_view():
    return render_template("processing.html")


@processing_bp.route("/history", methods=["GET"])
def history_view():
    return render_template("history.html")


# --- REST API Endpoints ---
@processing_bp.route("/api/jobs", methods=["GET"])
def api_list_jobs():
    """List all processing jobs, most recent first, with real-time multi-page progress."""
    from backend.app.models.extracted_record import ExtractedRecord

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status_filter = request.args.get("status")

    query = ProcessingJob.query
    if status_filter:
        query = query.filter_by(status=status_filter)

    pagination = query.order_by(ProcessingJob.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    job_dicts = []
    for j in pagination.items:
        d = j.to_dict()
        if j.total_documents == 1:
            doc = db.session.query(Document).filter_by(job_id=j.id).first()
            if doc and doc.page_count > 1:
                extracted_pages = db.session.query(
                    db.func.count(db.func.distinct(ExtractedRecord.page_number))
                ).filter_by(document_id=doc.id).scalar() or 0
                if doc.status in ("completed", "review_required") or extracted_pages >= doc.page_count:
                    d["progress_percentage"] = 100.0
                elif extracted_pages > 0:
                    page_pct = round((extracted_pages / doc.page_count) * 100.0, 1)
                    d["progress_percentage"] = min(page_pct, 99.0)
                elif doc.status in ("processing", "queued"):
                    d["progress_percentage"] = 5.0
                else:
                    d["progress_percentage"] = 0.0
        job_dicts.append(d)

    return jsonify({
        "jobs": job_dicts,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages
    }), 200


@processing_bp.route("/api/jobs/<job_id>", methods=["GET"])
def api_get_job(job_id: str):
    """Get metadata and document count for a single job."""
    job = db.session.get(ProcessingJob, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.to_dict()), 200


@processing_bp.route("/api/jobs/<job_id>", methods=["DELETE"])
def api_delete_job(job_id: str):
    """Delete a job and all its documents cleanly."""
    job = db.session.get(ProcessingJob, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    db.session.delete(job)
    db.session.commit()
    return jsonify({"message": f"Job {job_id} deleted successfully."}), 200


@processing_bp.route("/api/jobs/<job_id>/progress", methods=["GET"])
def api_get_job_progress(job_id: str):
    """
    Real-time progress polling endpoint for progress bars and worker status.
    """
    job = db.session.get(ProcessingJob, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Calculate real-time document counts
    completed = db.session.query(Document).filter_by(job_id=job_id, status="completed").count()
    failed = db.session.query(Document).filter_by(job_id=job_id, status="failed").count()
    review = db.session.query(Document).filter_by(job_id=job_id, status="review_required").count()
    processing = db.session.query(Document).filter_by(job_id=job_id, status="processing").count()
    queued = db.session.query(Document).filter_by(job_id=job_id, status="queued").count()

    from backend.app.models.extracted_record import ExtractedRecord

    total = job.total_documents
    processed = completed + failed + review

    if total == 1:
        # Single document multi-page progress calculation
        single_doc = db.session.query(Document).filter_by(job_id=job_id).first()
        if single_doc and single_doc.page_count > 1:
            extracted_pages = db.session.query(
                db.func.count(db.func.distinct(ExtractedRecord.page_number))
            ).filter_by(document_id=single_doc.id).scalar() or 0
            if completed == 1 or review == 1 or extracted_pages >= single_doc.page_count:
                percentage = 100.0
            elif extracted_pages > 0:
                page_percentage = round((extracted_pages / single_doc.page_count) * 100.0, 1)
                percentage = min(page_percentage, 99.0)
            else:
                percentage = 5.0 if single_doc.status in ("processing", "queued") else 0.0
        elif completed == 1:
            percentage = 100.0
        elif processing == 1 or queued == 1:
            percentage = 5.0
        else:
            percentage = 0.0
    elif total > 0:
        base_pct = (processed / total) * 100.0
        if processing > 0 and base_pct < 95.0:
            base_pct += (processing / total) * 25.0
        percentage = round(min(base_pct, 99.0 if processed < total else 100.0), 1)
    else:
        percentage = 0.0

    return jsonify({
        "job_id": job.id,
        "status": job.status,
        "total_documents": total,
        "completed": completed,
        "failed": failed,
        "review_required": review,
        "in_progress": processing,
        "queued": queued,
        "progress_percentage": percentage,
        "is_finished": (processed >= total and total > 0)
    }), 200


@processing_bp.route("/api/jobs/<job_id>/retry-failed", methods=["POST"])
def api_retry_job_failed(job_id: str):
    """Retry all failed documents belonging to a job batch."""
    job = db.session.get(ProcessingJob, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    res = retry_job_failed_documents_task(job_id)
    return jsonify({"message": f"Enqueued retry for failed documents in job {job_id}", "details": res}), 200


@processing_bp.route("/api/history", methods=["GET"])
def api_history():
    """Retrieve full processing history with summary statistics."""
    jobs = ProcessingJob.query.order_by(ProcessingJob.created_at.desc()).limit(100).all()
    return jsonify({
        "history": [j.to_dict() for j in jobs]
    }), 200


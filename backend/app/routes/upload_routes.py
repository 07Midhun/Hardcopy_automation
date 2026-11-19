"""
Upload Routes.
Handles bulk PDF uploads, ZIP archive extractions, hashing, duplicate prevention, and job queueing.
"""
import uuid
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import current_user
from backend.app.extensions import db
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.document import Document
from backend.app.storage.s3_storage import get_storage
from backend.app.utils.file_utils import calculate_sha256, sanitize_filename, get_file_size
from backend.app.services.duplicate_service import DuplicateService
from backend.app.tasks.processing_tasks import enqueue_document_processing, enqueue_zip_processing
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)
upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/upload", methods=["GET"])
def upload_view():
    return render_template("upload.html")


@upload_bp.route("/api/upload/bulk", methods=["POST"])
def api_upload_bulk():
    """
    Handle multiple PDF file uploads simultaneously.
    Validates, hashes, stores, registers in PostgreSQL, and enqueues extraction tasks.
    """
    files = request.files.getlist("files")
    if not files or len(files) == 0:
        return jsonify({"error": "No files provided"}), 400

    job_id = f"JOB-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    job = ProcessingJob(
        id=job_id,
        user_id=current_user.id if current_user.is_authenticated else None,
        batch_name=request.form.get("batch_name") or f"Batch {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        total_documents=len(files),
        status="processing"
    )
    db.session.add(job)
    db.session.commit()

    storage = get_storage()
    temp_dir = Path("storage/temp") / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    registered_docs = []
    duplicates_detected = 0
    seen_hashes = set()

    for idx, uploaded_file in enumerate(files, 1):
        if not uploaded_file.filename or not uploaded_file.filename.lower().endswith(".pdf"):
            continue

        clean_name = sanitize_filename(uploaded_file.filename)
        doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
        local_temp_file = temp_dir / f"{doc_id}_{clean_name}"

        # Stream save to disk to avoid keeping all files in memory
        uploaded_file.save(str(local_temp_file))

        file_hash = calculate_sha256(local_temp_file)
        file_size = get_file_size(local_temp_file)

        # Prevent duplicate registration & duplicate Excel rows
        existing_doc = DuplicateService.find_duplicate_by_hash(file_hash)
        if file_hash in seen_hashes:
            duplicates_detected += 1
            local_temp_file.unlink(missing_ok=True)
            continue

        if existing_doc:
            if existing_doc.status in ("completed", "review_required"):
                duplicates_detected += 1
                logger.info(f"Skipping already-completed duplicate document ({clean_name})")
                local_temp_file.unlink(missing_ok=True)
                continue
            else:
                logger.info(f"Purging prior incomplete/interrupted document {existing_doc.id} for fresh upload")
                db.session.delete(existing_doc)
                db.session.flush()

        seen_hashes.add(file_hash)

        # Save to permanent storage (S3 or local uploads)
        s3_key = f"documents/{job_id}/{doc_id}.pdf"
        storage.save_file(str(local_temp_file), s3_key, content_type="application/pdf")

        # Register in DB
        doc = Document(
            id=doc_id,
            job_id=job.id,
            original_filename=clean_name,
            s3_key=s3_key,
            file_hash=file_hash,
            file_size=file_size,
            status="queued"
        )
        db.session.add(doc)
        registered_docs.append(doc_id)

    job.total_documents = len(registered_docs)
    if len(registered_docs) == 0:
        job.status = "completed"
    db.session.commit()

    # Trigger non-blocking background tasks for all registered documents
    app_obj = current_app._get_current_object()
    for doc_id in registered_docs:
        enqueue_document_processing(doc_id, flask_app=app_obj)

    return jsonify({
        "message": f"Successfully registered {len(registered_docs)} documents.",
        "job_id": job.id,
        "total_files": len(files),
        "registered_count": len(registered_docs),
        "duplicates_detected": duplicates_detected
    }), 201


@upload_bp.route("/api/upload/zip", methods=["POST"])
def api_upload_zip():
    """
    Handle single ZIP archive upload containing multiple PDF documents.
    """
    if "file" not in request.files:
        return jsonify({"error": "No ZIP file uploaded"}), 400

    zip_file = request.files["file"]
    if not zip_file.filename or not zip_file.filename.lower().endswith(".zip"):
        return jsonify({"error": "Uploaded file must be a .zip archive"}), 400

    job_id = f"JOB-ZIP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    job = ProcessingJob(
        id=job_id,
        user_id=current_user.id if current_user.is_authenticated else None,
        batch_name=request.form.get("batch_name") or f"ZIP: {sanitize_filename(zip_file.filename)}",
        total_documents=0,
        status="queued"
    )
    db.session.add(job)
    db.session.commit()

    temp_dir = Path("storage/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_zip_path = temp_dir / f"{job_id}.zip"
    zip_file.save(str(temp_zip_path))

    # Dispatch non-blocking background task to extract, hash, and process all contained PDFs
    enqueue_zip_processing(job.id, str(temp_zip_path), flask_app=current_app._get_current_object())

    return jsonify({
        "message": "ZIP archive received and processing queued.",
        "job_id": job.id,
        "status": "queued"
    }), 202


"""
Document Routes.
Endpoints for document search, metadata, extraction inspect, preview, and single-document retries.
"""
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template, send_file, current_app, abort
from backend.app.extensions import db
from backend.app.models.document import Document
from backend.app.models.extracted_record import ExtractedRecord
from backend.app.storage.s3_storage import get_storage
from backend.app.services.pdf_service import PDFService
from backend.app.tasks.processing_tasks import process_single_document_task
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)
document_bp = Blueprint("document", __name__)


# --- HTML Template Views ---
@document_bp.route("/documents", methods=["GET"])
def documents_view():
    return render_template("documents.html")


@document_bp.route("/documents/<doc_id>", methods=["GET"])
def document_detail_view(doc_id: str):
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)
    return render_template("document_detail.html", document=doc)


# --- REST API Endpoints ---
@document_bp.route("/api/documents", methods=["GET"])
def api_list_documents():
    """List documents with pagination, status, document_type, and job filtering."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    job_id = request.args.get("job_id")
    status = request.args.get("status")
    doc_type = request.args.get("document_type")
    search = request.args.get("search")

    query = Document.query

    if job_id:
        query = query.filter_by(job_id=job_id)
    if status:
        query = query.filter_by(status=status)
    if doc_type:
        query = query.filter_by(document_type=doc_type)
    if search:
        query = query.filter(Document.original_filename.ilike(f"%{search}%"))

    pagination = query.order_by(Document.uploaded_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "documents": [d.to_dict() for d in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages
    }), 200


@document_bp.route("/api/documents/<doc_id>", methods=["GET"])
def api_get_document(doc_id: str):
    """Retrieve document metadata."""
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return jsonify(doc.to_dict()), 200


@document_bp.route("/api/documents/<doc_id>/extraction", methods=["GET"])
def api_get_document_extraction(doc_id: str):
    """Retrieve full structured extraction hierarchy (records and fields) for a document."""
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    records = ExtractedRecord.query.filter_by(document_id=doc.id).order_by(
        ExtractedRecord.record_number.asc()
    ).all()

    return jsonify({
        "document_id": doc.id,
        "source_filename": doc.original_filename,
        "document_type": doc.document_type,
        "status": doc.status,
        "confidence_average": doc.confidence_average,
        "records": [r.to_dict() for r in records]
    }), 200


@document_bp.route("/api/documents/<doc_id>/retry", methods=["POST"])
def api_retry_document(doc_id: str):
    """Retry extraction for a single document."""
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    doc.status = "queued"
    doc.error_message = None
    db.session.commit()

    process_single_document_task.delay(doc.id)
    return jsonify({"message": f"Retry queued for document {doc.id}"}), 200


@document_bp.route("/api/documents/<doc_id>/preview", methods=["GET"])
def api_preview_document(doc_id: str):
    """
    Render and serve high-resolution document image for browser preview / verification screen.
    Caches rendered image to avoid repeated PDF rendering.
    """
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)

    storage = get_storage()
    preview_cache = Path("storage/temp") / "previews" / f"{doc_id}_page1.png"

    if not preview_cache.exists():
        preview_cache.parent.mkdir(parents=True, exist_ok=True)
        local_pdf = preview_cache.with_suffix(".pdf")
        storage.get_file(doc.s3_key, str(local_pdf))
        PDFService.render_page(local_pdf, page_number=1, dpi=200, target_path=preview_cache)
        local_pdf.unlink(missing_ok=True)

    return send_file(preview_cache, mimetype="image/png")


@document_bp.route("/api/documents/media/<path:key>", methods=["GET"])
def api_serve_media(key: str):
    """Serve uploaded documents from local storage if running in local storage mode."""
    storage_dir = Path("storage/uploads").resolve()
    target_file = (storage_dir / key).resolve()
    if not str(target_file).startswith(str(storage_dir)) or not target_file.exists():
        abort(404)
    return send_file(target_file, mimetype="application/pdf")


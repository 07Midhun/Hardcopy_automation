"""
Review & Verification Routes.
Supports Human-in-the-Loop review screen, confidence inspection, and field correction audit logging.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, abort
from flask_login import current_user
from backend.app.extensions import db
from backend.app.models.document import Document
from backend.app.models.extracted_field import ExtractedField
from backend.app.models.verification_log import VerificationLog
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)
review_bp = Blueprint("review", __name__)


# --- HTML Template Views ---
@review_bp.route("/review", methods=["GET"])
def review_list_view():
    """List of documents awaiting review."""
    return render_template("review.html")


@review_bp.route("/review/<doc_id>", methods=["GET"])
def review_document_view(doc_id: str):
    """Side-by-side Human-in-the-Loop review workstation."""
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)
    return render_template("review.html", active_document_id=doc_id)


# --- REST API Endpoints ---
@review_bp.route("/api/review/queue", methods=["GET"])
def api_review_queue():
    """Retrieve queue of documents with status 'review_required'."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = Document.query.filter_by(status="review_required").order_by(
        Document.uploaded_at.asc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "queue": [d.to_dict() for d in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages
    }), 200


@review_bp.route("/api/documents/<doc_id>/corrections", methods=["PATCH"])
def api_update_corrections(doc_id: str):
    """
    Save manual corrections made by human reviewer.
    Preserves original_extracted_value and records entry in verification_logs.
    """
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    data = request.get_json() or {}
    corrections = data.get("corrections", [])  # List of {field_id, corrected_value, verification_status, notes}
    overall_status = data.get("document_status")  # Optional document-level status override

    if not isinstance(corrections, list):
        return jsonify({"error": "Corrections must be an array"}), 400

    verifier_name = current_user.username if (current_user and current_user.is_authenticated) else "reviewer"
    updated_count = 0

    for item in corrections:
        field_id = item.get("field_id")
        if not field_id:
            continue

        field = db.session.get(ExtractedField, field_id)
        if not field or field.record.document_id != doc.id:
            continue

        new_val = item.get("corrected_value")
        new_status = item.get("verification_status", "verified")
        notes = item.get("notes")

        # Check if value was modified
        if new_val != field.current_value or new_status != field.verification_status:
            # Audit log entry
            log_entry = VerificationLog(
                document_id=doc.id,
                extracted_field_id=field.id,
                original_value=field.current_value,
                corrected_value=new_val,
                verified_by=verifier_name,
                verified_at=datetime.utcnow(),
                notes=notes
            )
            db.session.add(log_entry)

            field.current_value = new_val
            field.verification_status = new_status
            updated_count += 1

    # Check if any remaining unverified or review-required fields exist
    has_remaining_review = db.session.query(ExtractedField).join(
        ExtractedField.record
    ).filter(
        ExtractedField.verification_status == "review_required"
    ).filter(
        ExtractedField.record.has(document_id=doc.id)
    ).count() > 0

    if overall_status:
        doc.status = overall_status
    elif not has_remaining_review:
        doc.status = "completed"

    db.session.commit()
    logger.info(f"Saved {updated_count} corrections for document {doc.id} by {verifier_name}")

    return jsonify({
        "message": f"Successfully updated {updated_count} fields",
        "document_status": doc.status,
        "updated_count": updated_count
    }), 200


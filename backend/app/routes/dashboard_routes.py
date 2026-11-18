"""
Dashboard Routes.
Aggregates enterprise overview metrics, status distribution, and document classification stats for Chart.js.
"""
from flask import Blueprint, jsonify, render_template
from sqlalchemy import func
from backend.app.extensions import db
from backend.app.models.document import Document
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.extracted_field import ExtractedField
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
@dashboard_bp.route("/dashboard", methods=["GET"])
def dashboard_view():
    return render_template("dashboard.html")


@dashboard_bp.route("/api/dashboard/stats", methods=["GET"])
def api_dashboard_stats():
    """
    Returns aggregated KPIs, document type counts, and review metrics for the dashboard charts.
    """
    total_docs = db.session.query(func.count(Document.id)).scalar() or 0
    completed = db.session.query(func.count(Document.id)).filter(Document.status == "completed").scalar() or 0
    review_req = db.session.query(func.count(Document.id)).filter(Document.status == "review_required").scalar() or 0
    failed = db.session.query(func.count(Document.id)).filter(Document.status == "failed").scalar() or 0
    pending = db.session.query(func.count(Document.id)).filter(Document.status.in_(["pending", "queued", "processing"])).scalar() or 0

    # Average confidence score across all extracted fields
    avg_conf = db.session.query(func.avg(ExtractedField.confidence_score)).scalar() or 0.0

    # Document type distribution
    doc_types = db.session.query(
        Document.document_type,
        func.count(Document.id)
    ).group_by(Document.document_type).all()
    doc_type_distribution = {dt: count for dt, count in doc_types}

    # Status distribution
    status_distribution = {
        "completed": completed,
        "review_required": review_req,
        "failed": failed,
        "pending": pending
    }

    # Recent jobs
    recent_jobs = ProcessingJob.query.order_by(ProcessingJob.created_at.desc()).limit(5).all()

    # Priority documents requiring review
    review_needed_docs = Document.query.filter_by(status="review_required").order_by(
        Document.uploaded_at.desc()
    ).limit(5).all()

    return jsonify({
        "kpis": {
            "total_documents": total_docs,
            "completed": completed,
            "review_required": review_req,
            "failed": failed,
            "pending": pending,
            "average_confidence": round(float(avg_conf), 2)
        },
        "status_distribution": status_distribution,
        "doc_type_distribution": doc_type_distribution,
        "recent_jobs": [j.to_dict() for j in recent_jobs],
        "review_queue_preview": [d.to_dict() for d in review_needed_docs]
    }), 200


"""
Blueprints export and registration.
"""
from backend.app.routes.auth_routes import auth_bp
from backend.app.routes.upload_routes import upload_bp
from backend.app.routes.processing_routes import processing_bp
from backend.app.routes.document_routes import document_bp
from backend.app.routes.review_routes import review_bp
from backend.app.routes.dashboard_routes import dashboard_bp
from backend.app.routes.export_routes import export_bp

__all__ = [
    "auth_bp",
    "upload_bp",
    "processing_bp",
    "document_bp",
    "review_bp",
    "dashboard_bp",
    "export_bp"
]


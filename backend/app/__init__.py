"""
Application factory initializing Flask, SQLAlchemy, Celery, and all Blueprints.
"""
import os
from pathlib import Path
from flask import Flask, jsonify, render_template
from backend.app.config import config_by_name
from backend.app.extensions import db, login_manager, cors
from backend.app.tasks.celery_app import make_celery


def create_app(config_name: str = None) -> Flask:
    """Create and configure Flask application instance."""
    if not config_name:
        config_name = os.getenv("FLASK_ENV", "development")

    config_class = config_by_name.get(config_name, config_by_name["default"])

    root_dir = Path(__file__).resolve().parent.parent.parent
    template_folder = root_dir / "frontend" / "templates"
    static_folder = root_dir / "frontend" / "static"

    app = Flask(
        __name__,
        template_folder=str(template_folder),
        static_folder=str(static_folder),
        static_url_path="/static"
    )
    app.config.from_object(config_class)

    # Auto-detect local infrastructure availability for zero-friction local development
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if "postgresql" in db_uri and ("localhost" in db_uri or "127.0.0.1" in db_uri):
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            res = sock.connect_ex(("127.0.0.1", 5432))
            sock.close()
            if res != 0:
                sqlite_path = (config_class.STORAGE_DIR / "doc_intelligence.db").resolve()
                sqlite_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"[Doc Intelligence] Local PostgreSQL server not reachable on port 5432.")
                print(f"[Doc Intelligence] Automatically falling back to local SQLite database: {sqlite_path}")
                app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_path.as_posix()}"
        except Exception:
            pass

    # Auto-detect local Redis broker for Celery
    broker_url = app.config.get("CELERY_BROKER_URL", "")
    if ("localhost" in broker_url or "127.0.0.1" in broker_url) and not app.config.get("CELERY_ALWAYS_EAGER", False):
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            res = sock.connect_ex(("127.0.0.1", 6379))
            sock.close()
            if res != 0:
                print(f"[Doc Intelligence] Local Redis broker not reachable on port 6379.")
                print(f"[Doc Intelligence] Automatically enabling in-process Celery task execution (CELERY_ALWAYS_EAGER=True).")
                app.config["CELERY_ALWAYS_EAGER"] = True
        except Exception:
            pass

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    cors.init_app(app)

    # Initialize Celery with Flask context
    from backend.app.tasks.celery_app import celery_app
    celery_app.conf.update(
        task_always_eager=app.config.get("CELERY_ALWAYS_EAGER", False),
        task_eager_propagates=True
    )
    make_celery(app)

    # Ensure storage directories exist
    for dir_path in [config_class.UPLOAD_DIR, config_class.TEMP_DIR, config_class.EXPORTS_DIR]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    # Register blueprints
    from backend.app.routes import (
        auth_bp,
        upload_bp,
        processing_bp,
        document_bp,
        review_bp,
        dashboard_bp,
        export_bp
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(processing_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(export_bp)

    # Health check endpoint for cloud load balancers (Render / AWS ALB / Docker)
    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok"}), 200

    # Create tables automatically on startup if not yet created
    with app.app_context():
        db.create_all()
        # Ensure file_content column exists in documents table (auto-migration for Neon PostgreSQL)
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_content BYTEA;"))
                conn.commit()
        except Exception:
            pass

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(413)
    def payload_too_large(error):
        return jsonify({"error": "File size exceeds maximum allowed upload limit (100MB)"}), 413

    return app

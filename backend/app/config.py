"""
Application configuration management supporting development, testing, and production.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "prod-secret-key-change-in-production-1234567890")
    DEBUG = False
    TESTING = False

    # Root and storage paths
    BASE_DIR = ROOT_DIR
    STORAGE_DIR = BASE_DIR / "storage"
    UPLOAD_DIR = STORAGE_DIR / "uploads"
    TEMP_DIR = STORAGE_DIR / "temp"
    EXPORTS_DIR = STORAGE_DIR / "exports"

    # Database configuration (PostgreSQL default, with SQLite fallback)
    raw_db_url = os.getenv("DATABASE_URL", "")
    if raw_db_url and raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

    if not raw_db_url or "sqlite" in raw_db_url:
        sqlite_file = (STORAGE_DIR / "doc_intelligence.db").resolve()
        sqlite_file.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_URL = f"sqlite:///{sqlite_file.as_posix()}"
    else:
        DATABASE_URL = raw_db_url

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Celery & Redis background task configuration
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    CELERY_ALWAYS_EAGER = os.getenv("CELERY_ALWAYS_EAGER", "False").lower() in ("true", "1", "yes")

    # Storage Backend: 's3' or 'local'
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "ai-doc-intelligence-storage")
    S3_PRESIGNED_EXPIRATION = int(os.getenv("S3_PRESIGNED_EXPIRATION", "3600"))

    # Upload Constraints
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(100 * 1024 * 1024)))  # 100 MB
    ALLOWED_EXTENSIONS = {"pdf", "zip"}

    # Processing & Batching
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
    MAX_CONCURRENT_WORKERS = int(os.getenv("MAX_CONCURRENT_WORKERS", "4"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF_FACTOR = int(os.getenv("RETRY_BACKOFF_FACTOR", "2"))
    RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "5"))

    # AI Extraction & OCR
    # Options: 'azure', 'vision_openai', 'vision_gemini', 'vision_claude', 'hybrid', 'fallback'
    AI_PROVIDER = os.getenv("AI_PROVIDER", "fallback")
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    AZURE_DOCUMENT_INTELLIGENCE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-3.8-flash")

    # Excel Generation Requirements
    EXCEL_WORKSHEET_NAME = "Consolidated_Data"
    EXCEL_MAX_ROW_LIMIT = 1048576  # Standard Excel row limit


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # If not specified in env, Celery eager can be enabled for zero-dependency local dev
    CELERY_ALWAYS_EAGER = os.getenv("CELERY_ALWAYS_EAGER", "True").lower() in ("true", "1", "yes")


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    CELERY_ALWAYS_EAGER = True
    STORAGE_BACKEND = "local"
    AI_PROVIDER = "fallback"
    EXPORTS_DIR = Config.STORAGE_DIR / "temp" / "test_exports"


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    CELERY_ALWAYS_EAGER = os.getenv("CELERY_ALWAYS_EAGER", "False").lower() in ("true", "1", "yes")


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}


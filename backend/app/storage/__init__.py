"""
Storage module export.
"""
from backend.app.storage.base_storage import BaseStorage
from backend.app.storage.s3_storage import S3Storage, LocalStorage, get_storage

__all__ = ["BaseStorage", "S3Storage", "LocalStorage", "get_storage"]


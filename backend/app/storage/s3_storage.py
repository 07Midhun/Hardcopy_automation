"""
Storage implementations: AWS S3 storage and Local filesystem storage fallback.
"""
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Union, Optional
from backend.app.storage.base_storage import BaseStorage
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


class S3Storage(BaseStorage):
    """AWS S3 Storage Provider."""

    def __init__(self, bucket_name: str, region_name: str = "us-east-1",
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None):
        import boto3
        from botocore.config import Config as BotoConfig

        self.bucket_name = bucket_name
        self.region_name = region_name
        boto_kwargs = {
            "region_name": region_name,
            "config": BotoConfig(signature_version="s3v4")
        }
        if aws_access_key_id and aws_secret_access_key:
            boto_kwargs["aws_access_key_id"] = aws_access_key_id
            boto_kwargs["aws_secret_access_key"] = aws_secret_access_key

        self.s3_client = boto3.client("s3", **boto_kwargs)

    def save_file(self, file_data: Union[bytes, BinaryIO, str], key: str, content_type: Optional[str] = None) -> str:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        if isinstance(file_data, str) and os.path.exists(file_data):
            self.s3_client.upload_file(file_data, self.bucket_name, key, ExtraArgs=extra_args or None)
        elif isinstance(file_data, bytes):
            self.s3_client.put_object(Bucket=self.bucket_name, Key=key, Body=file_data, **extra_args)
        else:
            self.s3_client.upload_fileobj(file_data, self.bucket_name, key, ExtraArgs=extra_args or None)

        logger.info(f"Saved file to S3: s3://{self.bucket_name}/{key}")
        return key

    def get_file(self, key: str, local_destination: Optional[str] = None) -> Union[bytes, str]:
        if local_destination:
            os.makedirs(os.path.dirname(local_destination), exist_ok=True)
            self.s3_client.download_file(self.bucket_name, key, local_destination)
            return local_destination
        else:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=expires_in
        )

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False

    def delete_file(self, key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete S3 object {key}: {e}")
            return False


class LocalStorage(BaseStorage):
    """Local filesystem storage provider for offline/local development."""

    def __init__(self, base_directory: Union[str, Path]):
        self.base_dir = Path(base_directory).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        # Prevent path traversal
        clean_key = key.lstrip("/\\").replace("..", "")
        return (self.base_dir / clean_key).resolve()

    def save_file(self, file_data: Union[bytes, BinaryIO, str], key: str, content_type: Optional[str] = None) -> str:
        target_path = self._resolve_path(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(file_data, str) and os.path.exists(file_data):
            shutil.copyfile(file_data, target_path)
        elif isinstance(file_data, bytes):
            with open(target_path, "wb") as f:
                f.write(file_data)
        else:
            with open(target_path, "wb") as f:
                shutil.copyfileobj(file_data, f)

        logger.info(f"Saved file to LocalStorage: {target_path}")
        return key

    def get_file(self, key: str, local_destination: Optional[str] = None) -> Union[bytes, str]:
        source_path = self._resolve_path(key)
        if not source_path.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")

        if local_destination:
            dest = Path(local_destination).resolve()
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source_path != dest:
                shutil.copyfile(source_path, dest)
            return str(dest)
        else:
            with open(source_path, "rb") as f:
                return f.read()

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        # Returns an internal media download endpoint
        return f"/api/documents/media/{key}"

    def exists(self, key: str) -> bool:
        return self._resolve_path(key).exists()

    def delete_file(self, key: str) -> bool:
        path = self._resolve_path(key)
        if path.exists():
            path.unlink()
            return True
        return False


def _cfg_get(cfg, key: str, default=None):
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def get_storage(app_config=None) -> BaseStorage:
    """Factory to get the configured storage instance."""
    from backend.app.config import Config
    cfg = app_config if app_config is not None else Config

    if _cfg_get(cfg, "STORAGE_BACKEND", "local") == "s3" and _cfg_get(cfg, "S3_BUCKET_NAME", None):
        try:
            return S3Storage(
                bucket_name=_cfg_get(cfg, "S3_BUCKET_NAME"),
                region_name=_cfg_get(cfg, "AWS_REGION", "us-east-1"),
                aws_access_key_id=_cfg_get(cfg, "AWS_ACCESS_KEY_ID", None),
                aws_secret_access_key=_cfg_get(cfg, "AWS_SECRET_ACCESS_KEY", None)
            )
        except Exception as e:
            logger.warning(f"Failed to initialize S3 storage ({e}). Falling back to LocalStorage.")

    return LocalStorage(_cfg_get(cfg, "UPLOAD_DIR", "storage/uploads"))


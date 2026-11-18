"""
File manipulation, hashing, archive extraction, and safety helpers.
"""
import hashlib
import os
import re
import zipfile
from pathlib import Path
from typing import List, Tuple, Union, BinaryIO
from werkzeug.utils import secure_filename
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_sha256(data: Union[str, Path, bytes, BinaryIO]) -> str:
    """Calculate SHA-256 hash of file or byte stream."""
    sha256 = hashlib.sha256()

    if isinstance(data, (str, Path)):
        with open(data, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
    elif isinstance(data, bytes):
        sha256.update(data)
    else:
        # File-like object
        pos = data.tell()
        for chunk in iter(lambda: data.read(65536), b""):
            sha256.update(chunk)
        data.seek(pos)

    return sha256.hexdigest()


def get_file_size(file_path: Union[str, Path]) -> int:
    """Return size of file in bytes."""
    return os.path.getsize(file_path)


def sanitize_filename(filename: str) -> str:
    """Safely sanitize original filename preserving extension."""
    clean = secure_filename(filename)
    if not clean:
        clean = "document.pdf"
    return clean


def is_allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def extract_zip_archive(zip_path: Union[str, Path], target_dir: Union[str, Path]) -> List[Tuple[str, Path]]:
    """
    Extract single-page or multi-page PDFs from a ZIP archive securely.
    Returns list of (original_relative_name, extracted_path).
    Prevents directory traversal (Zip Slip vulnerability).
    """
    extracted_files = []
    target_path = Path(target_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            # Skip directories or macOS metadata
            if member.is_dir() or member.filename.startswith("__MACOSX/") or member.filename.startswith("."):
                continue

            # Ensure file has .pdf extension
            if not member.filename.lower().endswith(".pdf"):
                continue

            # Check for zip slip
            extracted_target = (target_path / member.filename).resolve()
            if not str(extracted_target).startswith(str(target_path)):
                logger.warning(f"Prevented Zip Slip attempt: {member.filename}")
                continue

            extracted_target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, open(extracted_target, "wb") as dest:
                dest.write(source.read())

            extracted_files.append((Path(member.filename).name, extracted_target))

    logger.info(f"Extracted {len(extracted_files)} valid PDFs from {zip_path}")
    return extracted_files


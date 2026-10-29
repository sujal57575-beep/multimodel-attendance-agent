"""
utils/file_utils.py — Secure file handling utilities
"""

import os
import uuid
import hashlib
import mimetypes
import logging
from pathlib import Path
from werkzeug.utils import secure_filename

from config import Config

logger = logging.getLogger(__name__)

ALLOWED_VIDEO_MIME = {
    "video/mp4", "video/avi", "video/x-msvideo",
    "video/quicktime", "video/x-matroska", "video/webm",
}


def allowed_video(filename: str) -> bool:
    ext = Path(filename).suffix.lstrip(".").lower()
    return ext in Config.ALLOWED_VIDEO_EXTENSIONS


def save_upload(file_obj, session_id: str, subfolder: str = "uploads") -> dict:
    """Securely save an uploaded file. Returns metadata dict."""
    original_name = secure_filename(file_obj.filename)
    if not original_name:
        raise ValueError("Invalid filename")

    if not allowed_video(original_name):
        raise ValueError(
            f"File type not allowed. Accepted: {Config.ALLOWED_VIDEO_EXTENSIONS}"
        )

    ext = Path(original_name).suffix
    stored_name = f"{session_id}_{uuid.uuid4().hex}{ext}"
    dest_dir = Path(Config.UPLOAD_FOLDER if subfolder == "uploads" else Config.PROCESSED_FOLDER)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / stored_name

    file_obj.save(str(dest_path))
    size = dest_path.stat().st_size
    logger.info("Saved upload %s (%d bytes) → %s", original_name, size, dest_path)

    return {
        "original_name": original_name,
        "stored_path": str(dest_path),
        "file_size_bytes": size,
    }


def secure_path(base_dir: str, filename: str) -> Path:
    """Resolve a path ensuring it doesn't escape base_dir (path traversal guard)."""
    base = Path(base_dir).resolve()
    target = (base / secure_filename(filename)).resolve()
    if not str(target).startswith(str(base)):
        raise PermissionError(f"Path traversal attempt blocked: {filename}")
    return target


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} TB"

import os
import re
import shutil
import hashlib
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile
from app.core.config import get_settings
from app.services.ingestion.exceptions import FileTooLargeError

settings = get_settings()


class StorageService:
    """
    Manages local filesystem storage for uploaded raw datasets and versioned assets.
    Designed with a clean interface for future S3/Blob storage migration.
    """

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.STORAGE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitizes input filename to prevent directory traversal and illegal characters.
        """
        base = os.path.basename(filename)
        # Strip dangerous characters, allow alphanumerics, dots, dashes, underscores
        sanitized = re.sub(r"[^\w\.\-]", "_", base)
        # Prevent hidden files or double dots
        sanitized = re.sub(r"^\.+", "", sanitized)
        if not sanitized:
            sanitized = "unnamed_dataset"
        return sanitized

    def get_dataset_version_dir(
        self, project_id: str, dataset_id: str, version_id: str
    ) -> Path:
        """
        Builds and ensures the directory path for a specific dataset version:
        storage/projects/{project_id}/datasets/{dataset_id}/versions/{version_id}/original/
        """
        path = (
            self.base_dir
            / "projects"
            / str(project_id)
            / "datasets"
            / str(dataset_id)
            / "versions"
            / str(version_id)
            / "original"
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def save_upload(
        self,
        file: UploadFile,
        project_id: str,
        dataset_id: str,
        version_id: str,
    ) -> Tuple[Path, int, str]:
        """
        Streams uploaded file to storage path, validating max file size and computing SHA-256 hash.
        Returns: (saved_path, total_bytes, sha256_checksum)
        """
        safe_filename = self.sanitize_filename(file.filename or "uploaded_data")
        target_dir = self.get_dataset_version_dir(project_id, dataset_id, version_id)
        target_path = target_dir / safe_filename

        total_bytes = 0
        hasher = hashlib.sha256()
        chunk_size = 1024 * 1024  # 1MB buffer

        try:
            with open(target_path, "wb") as f:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
                        raise FileTooLargeError(
                            f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024):.1f} MB."
                        )
                    hasher.update(chunk)
                    f.write(chunk)
        except Exception:
            # Clean up partial file on error
            if target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    pass
            raise

        checksum = hasher.hexdigest()
        return target_path, total_bytes, checksum

    def delete_dataset_storage(self, project_id: str, dataset_id: str) -> None:
        """Removes the entire storage directory for a dataset."""
        dataset_dir = (
            self.base_dir / "projects" / str(project_id) / "datasets" / str(dataset_id)
        )
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir, ignore_errors=True)

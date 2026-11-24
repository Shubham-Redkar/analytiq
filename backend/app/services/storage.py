"""AnalytIQ Storage Service - Secure local filesystem dataset storage."""

import logging
import shutil
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class StorageSecurityError(Exception):
    """Raised when a storage operation violates path safety constraints."""


class PayloadTooLargeError(Exception):
    """Raised when an uploaded file exceeds the configured size limit."""


class StorageDeletionError(Exception):
    """Raised when removing dataset files or directories fails on the filesystem."""


class StorageService:
    """Manages file storage for dataset source uploads and normalized Parquet files."""

    def __init__(self, root_path: Path | None = None) -> None:
        self._settings = get_settings()
        self._root_path = (root_path or self._settings.storage_path).resolve()
        self._uploads_dir = self._root_path / "uploads"
        self._parquet_dir = self._root_path / "parquet"
        self._ensure_storage_dirs()

    @property
    def root_path(self) -> Path:
        return self._root_path

    def _ensure_storage_dirs(self) -> None:
        """Create storage root and subdirectories if they do not exist."""
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        self._parquet_dir.mkdir(parents=True, exist_ok=True)

    def _validate_path_within_root(self, path: Path) -> Path:
        """Verify that resolved path resides strictly within the approved storage root."""
        if path.is_symlink():
            raise StorageSecurityError(f"Symlinks are prohibited: {path}")
        resolved = path.resolve()
        if resolved.is_symlink():
            raise StorageSecurityError(f"Symlinks are prohibited: {resolved}")
        try:
            resolved.relative_to(self._root_path)
        except ValueError as err:
            logger.error("Path traversal attempt detected: %s", path)
            msg = f"Access denied: path '{path}' escapes storage root."
            raise StorageSecurityError(msg) from err
        return resolved

    def get_upload_dir(self, dataset_id: uuid.UUID) -> Path:
        """Return the directory path for a dataset's uploaded source file."""
        target = self._uploads_dir / str(dataset_id)
        return self._validate_path_within_root(target)

    def get_parquet_dir(self, dataset_id: uuid.UUID) -> Path:
        """Return the directory path for a dataset's normalized Parquet file."""
        target = self._parquet_dir / str(dataset_id)
        return self._validate_path_within_root(target)

    def get_upload_file_path(self, dataset_id: uuid.UUID, file_extension: str) -> Path:
        """Return the full file path for an uploaded source file."""
        sanitized_ext = file_extension.lower().strip()
        if not sanitized_ext.startswith("."):
            sanitized_ext = f".{sanitized_ext}"
        if sanitized_ext not in {".csv", ".xlsx"}:
            raise StorageSecurityError(f"Unsupported file extension: {sanitized_ext}")
        target = self.get_upload_dir(dataset_id) / f"source{sanitized_ext}"
        return self._validate_path_within_root(target)

    def get_parquet_file_path(self, dataset_id: uuid.UUID) -> Path:
        """Return the full file path for a normalized Parquet file."""
        target = self.get_parquet_dir(dataset_id) / "data.parquet"
        return self._validate_path_within_root(target)

    async def save_upload_stream(
        self,
        dataset_id: uuid.UUID,
        file_extension: str,
        stream: AsyncIterator[bytes],
        max_bytes: int | None = None,
    ) -> tuple[Path, int]:
        """Stream chunks to disk, enforcing size limits during ingestion.

        If total bytes exceed max_bytes, the partial file is cleaned up immediately
        and PayloadTooLargeError is raised.
        """
        limit = max_bytes or self._settings.max_upload_size_bytes
        file_path = self.get_upload_file_path(dataset_id, file_extension)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        bytes_written = 0
        try:
            with open(file_path, "wb") as f:
                async for chunk in stream:
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    if bytes_written > limit:
                        limit_mib = limit // (1024 * 1024)
                        raise PayloadTooLargeError(
                            f"File size exceeds the maximum limit of {limit_mib} MiB."
                        )
                    f.write(chunk)
        except Exception:
            # Clean up partial upload immediately on failure
            try:
                self.delete_dataset_files(dataset_id)
            except Exception as cleanup_err:
                logger.warning(
                    "Failed to clean up partial upload for %s: %s", dataset_id, cleanup_err
                )
            raise

        if bytes_written == 0:
            try:
                self.delete_dataset_files(dataset_id)
            except Exception as cleanup_err:
                logger.warning("Failed to clean up empty file for %s: %s", dataset_id, cleanup_err)
            raise ValueError("Uploaded file is empty.")

        return file_path, bytes_written

    def delete_dataset_files(self, dataset_id: uuid.UUID) -> None:
        """Safely remove all files and directories associated with a dataset.

        Missing directories or files are handled idempotently. Genuine filesystem failures
        (e.g., PermissionError or other OSError) are raised as StorageDeletionError to prevent
        unreported residual storage files.
        """
        upload_dir = self.get_upload_dir(dataset_id)
        parquet_dir = self.get_parquet_dir(dataset_id)

        failed_dirs: list[tuple[Path, OSError]] = []
        for d in (upload_dir, parquet_dir):
            if d.exists():
                try:
                    shutil.rmtree(d)
                except FileNotFoundError:
                    # Idempotent cleanup if already gone
                    pass
                except OSError as err:
                    logger.error("Failed to delete storage directory %s: %s", d, err)
                    failed_dirs.append((d, err))

        if failed_dirs:
            first_dir, first_err = failed_dirs[0]
            raise StorageDeletionError(
                f"Filesystem deletion failed for directory '{first_dir.name}': {first_err}"
            ) from first_err


storage_service = StorageService()

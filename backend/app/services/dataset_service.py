"""AnalytIQ Dataset Service - High-level dataset ingestion, management, and retrieval."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.models.dataset import Dataset
from app.services.duckdb_engine import duckdb_engine
from app.services.parser import ParseValidationError, dataset_parser
from app.services.storage import (
    storage_service,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DatasetService:
    """Coordinates storage, deterministic parsing, DuckDB analysis, and database metadata."""

    async def create_dataset(
        self,
        db: AsyncSession,
        owner_id: uuid.UUID,
        original_filename: str,
        stream: AsyncIterator[bytes],
        display_name: str | None = None,
        max_bytes: int | None = None,
    ) -> Dataset:
        """Ingest, validate, and convert an uploaded dataset to Parquet and profile it."""
        clean_filename = Path(original_filename).name.strip()
        ext = Path(clean_filename).suffix.lower()

        if ext not in {".csv", ".xlsx"}:
            raise ParseValidationError(
                "Unsupported file format. Only .csv and .xlsx files are supported."
            )

        file_format = "CSV" if ext == ".csv" else "XLSX"
        dataset_name = (
            display_name.strip()
            if display_name and display_name.strip()
            else Path(clean_filename).stem
        )

        dataset_id = uuid.uuid4()
        storage_key = str(dataset_id)

        try:
            # 1. Stream upload to disk while enforcing size limits
            upload_path, file_size = await storage_service.save_upload_stream(
                dataset_id=dataset_id,
                file_extension=ext,
                stream=stream,
                max_bytes=max_bytes,
            )

            # 2. Parse and normalize to Parquet in a worker thread (non-blocking)
            parquet_path = storage_service.get_parquet_file_path(dataset_id)
            schema_metadata = await asyncio.to_thread(
                dataset_parser.parse_and_convert,
                upload_path,
                parquet_path,
                file_format,
            )

            # 3. Compute deterministic profile and quality metrics via DuckDB in worker thread
            profile_and_quality = await asyncio.to_thread(
                duckdb_engine.compute_profile_and_quality,
                parquet_path,
                schema_metadata["columns"],
            )

            # 4. Persist metadata to PostgreSQL
            dataset = Dataset(
                id=dataset_id,
                owner_id=owner_id,
                name=dataset_name,
                original_filename=clean_filename,
                file_format=file_format,
                file_size_bytes=file_size,
                row_count=schema_metadata["row_count"],
                column_count=schema_metadata["column_count"],
                status="ready",
                storage_key=storage_key,
                schema_json=schema_metadata,
                profile_json=profile_and_quality,
            )

            db.add(dataset)
            await db.commit()
            await db.refresh(dataset)
            return dataset

        except Exception as exc:
            # Cleanup on failure
            logger.warning("Dataset ingestion failed for '%s': %s", clean_filename, exc)
            storage_service.delete_dataset_files(dataset_id)
            await db.rollback()
            raise

    async def list_datasets(
        self,
        db: AsyncSession,
        owner_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Dataset], int]:
        """List datasets owned by the given user with pagination (newest first)."""
        safe_page = max(1, page)
        safe_page_size = min(max(1, page_size), 100)
        offset = (safe_page - 1) * safe_page_size

        count_query = select(func.count()).select_from(Dataset).where(Dataset.owner_id == owner_id)
        total_res = await db.execute(count_query)
        total_count = total_res.scalar() or 0

        query = (
            select(Dataset)
            .where(Dataset.owner_id == owner_id)
            .order_by(Dataset.created_at.desc(), Dataset.id.desc())
            .offset(offset)
            .limit(safe_page_size)
        )
        res = await db.execute(query)
        datasets = list(res.scalars().all())
        return datasets, total_count

    async def get_dataset(
        self,
        db: AsyncSession,
        dataset_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> Dataset | None:
        """Retrieve a dataset ensuring it belongs to the authenticated user."""
        query = select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.owner_id == owner_id,
        )
        res = await db.execute(query)
        return res.scalar_one_or_none()

    async def get_preview(
        self,
        db: AsyncSession,
        dataset_id: uuid.UUID,
        owner_id: uuid.UUID,
        offset: int = 0,
        limit: int = 25,
    ) -> dict[str, Any] | None:
        """Fetch paginated dataset rows via DuckDB."""
        dataset = await self.get_dataset(db, dataset_id, owner_id)
        if dataset is None or dataset.status != "ready":
            return None

        parquet_path = storage_service.get_parquet_file_path(dataset.id)
        schema_cols = dataset.schema_json.get("columns") if dataset.schema_json else None
        return await asyncio.to_thread(
            duckdb_engine.get_preview,
            parquet_path,
            offset,
            limit,
            schema_cols,
        )

    async def get_profile(
        self,
        db: AsyncSession,
        dataset_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Fetch stored deterministic column profiling."""
        dataset = await self.get_dataset(db, dataset_id, owner_id)
        if dataset is None or dataset.status != "ready" or not dataset.profile_json:
            return None

        return {
            "summary": dataset.profile_json.get("summary", {}),
            "columns": dataset.profile_json.get("columns", []),
        }

    async def get_quality(
        self,
        db: AsyncSession,
        dataset_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Fetch stored deterministic data-quality summary and findings."""
        dataset = await self.get_dataset(db, dataset_id, owner_id)
        if dataset is None or dataset.status != "ready" or not dataset.profile_json:
            return None

        return {
            "summary": dataset.profile_json.get("summary", {}),
            "quality_findings": dataset.profile_json.get("quality_findings", []),
            "columns_breakdown": dataset.profile_json.get("columns_breakdown", []),
        }

    async def delete_dataset(
        self,
        db: AsyncSession,
        dataset_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> bool:
        """Delete dataset metadata from PostgreSQL and remove its files from storage.

        Database commit acts as the primary system of record. Associated filesystem directories
        are removed with structured recovery logging to prevent blocking user requests if disk
        cleanup experiences transient delays.
        """
        dataset = await self.get_dataset(db, dataset_id, owner_id)
        if dataset is None:
            return False

        await db.delete(dataset)
        await db.commit()

        # Resilient file cleanup
        storage_service.delete_dataset_files(dataset_id)
        return True


dataset_service = DatasetService()

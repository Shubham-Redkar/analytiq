"""AnalytIQ API v1 - User-owned dataset management and exploration endpoints."""

import math
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.dataset import (
    DatasetDeleteResponse,
    DatasetListResponse,
    DatasetPreviewResponse,
    DatasetProfileResponse,
    DatasetQualityResponse,
    DatasetResponse,
)
from app.services.dataset_service import dataset_service
from app.services.parser import ParseValidationError
from app.services.storage import PayloadTooLargeError, StorageSecurityError

router = APIRouter()


async def file_chunk_generator(
    upload_file: UploadFile,
    chunk_size: int = 1024 * 1024,
) -> AsyncIterator[bytes]:
    """Asynchronously yield binary chunks from UploadFile."""
    while True:
        chunk = await upload_file.read(chunk_size)
        if not chunk:
            break
        yield chunk


@router.post(
    "",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a new dataset (CSV or XLSX)",
)
async def upload_dataset(
    current_user: CurrentUser,
    db: DatabaseSession,
    file: Annotated[UploadFile, File(description="CSV or XLSX dataset file to ingest")],
    name: Annotated[
        str | None,
        Form(description="Optional custom display name for the dataset"),
    ] = None,
) -> DatasetResponse:
    """Ingest, validate, and normalize a user-uploaded CSV or XLSX dataset."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file must have a valid filename.",
        )

    try:
        dataset = await dataset_service.create_dataset(
            db=db,
            owner_id=current_user.id,
            original_filename=file.filename,
            stream=file_chunk_generator(file),
            display_name=name,
        )
        return DatasetResponse.model_validate(dataset)
    except PayloadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except (ParseValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except StorageSecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List datasets owned by current user",
)
async def list_datasets(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> DatasetListResponse:
    """Return paginated list of datasets owned by the authenticated user."""
    items, total = await dataset_service.list_datasets(
        db=db,
        owner_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return DatasetListResponse(
        items=[DatasetResponse.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{dataset_id}",
    response_model=DatasetResponse,
    summary="Get dataset details",
)
async def get_dataset(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> DatasetResponse:
    """Retrieve metadata for a specific dataset owned by current user."""
    dataset = await dataset_service.get_dataset(db, dataset_id, current_user.id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )
    return DatasetResponse.model_validate(dataset)


@router.get(
    "/{dataset_id}/preview",
    response_model=DatasetPreviewResponse,
    summary="Get paginated dataset preview rows",
)
async def get_dataset_preview(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    offset: Annotated[int, Query(ge=0, description="Row offset for pagination")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of preview rows")] = 25,
) -> DatasetPreviewResponse:
    """Return paginated preview rows queried directly via DuckDB from Parquet."""
    preview = await dataset_service.get_preview(
        db=db,
        dataset_id=dataset_id,
        owner_id=current_user.id,
        offset=offset,
        limit=limit,
    )
    if preview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or not ready.",
        )
    return DatasetPreviewResponse(**preview)


@router.get(
    "/{dataset_id}/profile",
    response_model=DatasetProfileResponse,
    summary="Get column profiling statistics",
)
async def get_dataset_profile(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> DatasetProfileResponse:
    """Return deterministic column statistics computed via DuckDB."""
    profile = await dataset_service.get_profile(db, dataset_id, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or profiling unavailable.",
        )
    return DatasetProfileResponse(**profile)


@router.get(
    "/{dataset_id}/quality",
    response_model=DatasetQualityResponse,
    summary="Get data-quality summary and findings",
)
async def get_dataset_quality(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> DatasetQualityResponse:
    """Return deterministic data-quality findings."""
    quality = await dataset_service.get_quality(db, dataset_id, current_user.id)
    if quality is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or quality metrics unavailable.",
        )
    return DatasetQualityResponse(**quality)


@router.delete(
    "/{dataset_id}",
    response_model=DatasetDeleteResponse,
    summary="Delete dataset and storage files",
)
async def delete_dataset(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> DatasetDeleteResponse:
    """Delete a dataset and all associated files from storage."""
    deleted = await dataset_service.delete_dataset(db, dataset_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )
    return DatasetDeleteResponse(dataset_id=dataset_id)

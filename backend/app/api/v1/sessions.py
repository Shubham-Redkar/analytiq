"""AnalytIQ API v1 - Analytical Sessions & History Endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.history import (
    AnalysisSessionListResponse,
    AnalysisSessionResponse,
    SessionCreateRequest,
    SessionUpdateRequest,
)
from app.services.dataset_service import dataset_service
from app.services.history_service import history_service

router = APIRouter()


@router.post(
    "",
    response_model=AnalysisSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or initialize an analytical workspace session",
)
async def create_analysis_session(
    payload: SessionCreateRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> AnalysisSessionResponse:
    """Create a new analytical session associated with an owned dataset."""
    dataset = await dataset_service.get_dataset(
        db=db,
        dataset_id=payload.dataset_id,
        owner_id=current_user.id,
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with id '{payload.dataset_id}' not found.",
        )

    session = await history_service.get_or_create_session(
        db=db,
        user_id=current_user.id,
        dataset_id=payload.dataset_id,
        initial_question=payload.title,
    )
    detail = await history_service.get_session(
        db=db,
        session_id=session.id,
        user_id=current_user.id,
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load created session.",
        )
    return detail


@router.get(
    "",
    response_model=AnalysisSessionListResponse,
    summary="List analytical sessions for the authenticated user",
)
async def list_analysis_sessions(
    current_user: CurrentUser,
    db: DatabaseSession,
    dataset_id: uuid.UUID | None = Query(default=None, description="Filter by dataset ID"),  # noqa: B008
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> AnalysisSessionListResponse:
    """Retrieve paginated list of analytical sessions owned by the current user."""
    return await history_service.list_sessions(
        db=db,
        user_id=current_user.id,
        dataset_id=dataset_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{session_id}",
    response_model=AnalysisSessionResponse,
    summary="Get full analytical session history and runs",
)
async def get_analysis_session(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> AnalysisSessionResponse:
    """Retrieve complete session history with reconstructed verified runs."""
    session = await history_service.get_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis session '{session_id}' not found.",
        )
    return session


@router.patch(
    "/{session_id}",
    response_model=AnalysisSessionResponse,
    summary="Rename an analytical workspace session",
)
async def update_analysis_session(
    session_id: uuid.UUID,
    payload: SessionUpdateRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> AnalysisSessionResponse:
    """Update title of an analytical session."""
    session = await history_service.update_session_title(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        title=payload.title,
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis session '{session_id}' not found.",
        )
    detail = await history_service.get_session(
        db=db,
        session_id=session.id,
        user_id=current_user.id,
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load session.",
        )
    return detail


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an analytical workspace session",
)
async def delete_analysis_session(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> None:
    """Permanently delete an analytical session and all associated runs."""
    deleted = await history_service.delete_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis session '{session_id}' not found.",
        )

"""AnalytIQ API v1 - Dataset Analytical Query and Multi-Agent Orchestration Endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.analysis.service import AnalysisService
from app.api.deps import CurrentUser, DatabaseSession
from app.core.config import Settings, get_settings
from app.llm.contracts import LLMProvider
from app.llm.factory import create_llm_provider
from app.orchestration.service import OrchestrationService
from app.schemas.analysis import (
    AnalysisQueryRequest,
    AnalysisQueryResponse,
    AnalysisStatusResponse,
    WorkflowAnalysisResponse,
)
from app.services.dataset_service import dataset_service

router = APIRouter()

# Singleton or cached provider reference for the API lifecycle
_cached_llm_provider: LLMProvider | None = None


def get_llm_provider(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> LLMProvider:
    """Dependency that yields the active LLM provider."""
    global _cached_llm_provider
    if _cached_llm_provider is None:
        _cached_llm_provider = create_llm_provider(settings)
    return _cached_llm_provider


def get_analysis_service(
    llm_provider: LLMProvider = Depends(get_llm_provider),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> AnalysisService:
    """Dependency providing an initialized AnalysisService instance."""
    return AnalysisService(llm_provider=llm_provider, settings=settings)


def get_orchestration_service(
    llm_provider: LLMProvider = Depends(get_llm_provider),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> OrchestrationService:
    """Dependency providing an initialized OrchestrationService instance."""
    return OrchestrationService(llm_provider=llm_provider, settings=settings)


@router.get(
    "/status",
    response_model=AnalysisStatusResponse,
    summary="Check analytical capability and LLM provider connectivity status",
)
async def check_analysis_status(
    llm_provider: LLMProvider = Depends(get_llm_provider),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> AnalysisStatusResponse:
    """Lightweight diagnostic probe verifying LLM provider availability."""
    health = await llm_provider.health_check()
    return AnalysisStatusResponse(
        analysis_available=health.available,
        provider=health.provider,
        model=health.model,
        status=health.status,
        error=health.error,
        timestamp=health.timestamp,
    )


@router.post(
    "/{dataset_id}/query",
    response_model=AnalysisQueryResponse,
    summary="Submit analytical query against owned dataset (M3 endpoint)",
)
async def execute_dataset_query(
    dataset_id: uuid.UUID,
    payload: AnalysisQueryRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    analysis_service: AnalysisService = Depends(get_analysis_service),  # noqa: B008
) -> AnalysisQueryResponse:
    """Execute authenticated analytical query against authorized dataset.

    Enforces:
    - User authentication (CurrentUser)
    - Dataset ownership (404 if not found or owned by another user)
    - Dataset readiness (must be in status 'ready')
    - AST-based SQL security policy and DuckDB execution isolation
    """
    dataset = await dataset_service.get_dataset(
        db=db,
        dataset_id=dataset_id,
        owner_id=current_user.id,
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with id '{dataset_id}' not found.",
        )

    if dataset.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset is in '{dataset.status}' state and not ready for analytical queries.",
        )

    result = await analysis_service.run_analysis(
        dataset=dataset,
        question=payload.question,
    )

    return AnalysisQueryResponse.model_validate(result)


@router.post(
    "/{dataset_id}/analysis",
    response_model=WorkflowAnalysisResponse,
    summary="Submit query to LangGraph analytical workflow (M4 endpoint)",
)
async def execute_dataset_workflow_analysis(
    dataset_id: uuid.UUID,
    payload: AnalysisQueryRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),  # noqa: B008
) -> WorkflowAnalysisResponse:
    """Execute authenticated analytical query via LangGraph multi-agent workflow.

    Enforces:
    - User authentication (CurrentUser)
    - Dataset ownership (404 if not found or owned by another user)
    - Dataset readiness (must be in status 'ready')
    - Multi-agent orchestration: Intent classification, schema grounding,
      deterministic clarification, planning, SQLGlot validation,
      restricted DuckDB execution, result interpretation, and execution evidence.
    """
    dataset = await dataset_service.get_dataset(
        db=db,
        dataset_id=dataset_id,
        owner_id=current_user.id,
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with id '{dataset_id}' not found.",
        )

    if dataset.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset is in '{dataset.status}' state and not ready for analytical queries.",
        )

    result = await orchestration_service.execute_workflow(
        dataset=dataset,
        question=payload.question,
        user_id=current_user.id,
    )

    return WorkflowAnalysisResponse.model_validate(result)

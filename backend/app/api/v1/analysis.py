"""AnalytIQ API v1 - Dataset Analytical Query and Multi-Agent Orchestration Endpoints."""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.analysis.admission import AnalyticalOverloadError
from app.analysis.service import AnalysisService
from app.api.deps import CurrentUser, DatabaseSession
from app.core.config import Settings, get_settings
from app.llm.contracts import LLMProvider
from app.llm.factory import create_llm_provider
from app.orchestration.contracts import OrchestrationResult
from app.orchestration.service import OrchestrationService
from app.schemas.analysis import (
    AnalysisQueryRequest,
    AnalysisQueryResponse,
    AnalysisStatusResponse,
    WorkflowAnalysisResponse,
)
from app.schemas.stream import CancellationResponse, StreamProgressEvent
from app.services.cancellation_registry import cancellation_registry
from app.services.dataset_service import dataset_service
from app.services.history_service import history_service

logger = logging.getLogger(__name__)

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

    try:
        result = await analysis_service.run_analysis(
            dataset=dataset,
            question=payload.question,
        )
    except AnalyticalOverloadError as oe:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=oe.message,
            headers={"Retry-After": str(oe.retry_after)},
        ) from oe

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

    try:
        result = await orchestration_service.execute_workflow(
            dataset=dataset,
            question=payload.question,
            user_id=current_user.id,
        )
    except AnalyticalOverloadError as oe:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=oe.message,
            headers={"Retry-After": str(oe.retry_after)},
        ) from oe

    response_model = WorkflowAnalysisResponse.model_validate(result)

    # Persist in session if session_id provided or create/update session
    try:
        session = await history_service.get_or_create_session(
            db=db,
            user_id=current_user.id,
            dataset_id=dataset_id,
            session_id=payload.session_id,
            initial_question=payload.question,
        )
        await history_service.persist_run(
            db=db,
            session=session,
            response=response_model,
        )
    except Exception as exc:
        logger.warning("Failed to persist run: %s", exc)

    return response_model


@router.post(
    "/{dataset_id}/analysis/stream",
    summary="Submit query to LangGraph workflow with real-time SSE progress streaming",
)
async def execute_dataset_workflow_stream(
    dataset_id: uuid.UUID,
    payload: AnalysisQueryRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),  # noqa: B008
) -> StreamingResponse:
    """Stream real-time workflow progress stages via Server-Sent Events (SSE)."""
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

    request_id = str(uuid.uuid4())
    start_time = time.monotonic()
    cancel_event = await cancellation_registry.register(
        request_id=request_id,
        user_id=current_user.id,
        dataset_id=dataset_id,
    )

    session = await history_service.get_or_create_session(
        db=db,
        user_id=current_user.id,
        dataset_id=dataset_id,
        session_id=payload.session_id,
        initial_question=payload.question,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        seq = 1
        workflow_task: asyncio.Task[OrchestrationResult] | None = None
        try:
            # 1. Accepted event
            accepted_evt = StreamProgressEvent(
                request_id=request_id,
                seq=seq,
                event_type="accepted",
                stage="admission",
                stage_name="Acquiring analytical execution permit",
                status="queued",
                elapsed_ms=round((time.monotonic() - start_time) * 1000, 2),
            )
            seq += 1
            yield f"data: {accepted_evt.model_dump_json()}\n\n"

            # 2. Started event
            started_evt = StreamProgressEvent(
                request_id=request_id,
                seq=seq,
                event_type="stage_started",
                stage="supervisor",
                stage_name="Understanding your analytical question",
                status="running",
                elapsed_ms=round((time.monotonic() - start_time) * 1000, 2),
            )
            seq += 1
            yield f"data: {started_evt.model_dump_json()}\n\n"

            if cancel_event.is_set():
                cancelled_evt = StreamProgressEvent(
                    request_id=request_id,
                    seq=seq,
                    event_type="cancelled",
                    status="cancelled",
                    elapsed_ms=round((time.monotonic() - start_time) * 1000, 2),
                )
                yield f"data: {cancelled_evt.model_dump_json()}\n\n"
                return

            # Execute workflow concurrently with periodic SSE keepalive comments to
            # prevent proxy / client timeouts
            workflow_task = asyncio.create_task(
                orchestration_service.execute_workflow(
                    dataset=dataset,
                    question=payload.question,
                    user_id=current_user.id,
                    request_id=request_id,
                )
            )

            active_task = workflow_task
            assert active_task is not None

            while not active_task.done():
                if cancel_event.is_set():
                    active_task.cancel()
                    cancelled_evt = StreamProgressEvent(
                        request_id=request_id,
                        seq=seq,
                        event_type="cancelled",
                        status="cancelled",
                        elapsed_ms=round((time.monotonic() - start_time) * 1000, 2),
                    )
                    yield f"data: {cancelled_evt.model_dump_json()}\n\n"
                    return

                done, _ = await asyncio.wait([active_task], timeout=2.0)
                if not done:
                    # Send standard SSE keepalive comment to maintain active socket
                    yield ": keepalive\n\n"

            result = await active_task

            # Map executed trace events to progressive SSE stages
            for trace in result.trace_events:
                stage_evt = StreamProgressEvent(
                    request_id=request_id,
                    seq=seq,
                    event_type="stage_completed",
                    stage=trace.node,
                    stage_name=f"Completed {trace.node}: {trace.action}",
                    status="running",
                    elapsed_ms=round((time.monotonic() - start_time) * 1000, 2),
                    payload={"duration_ms": trace.duration_ms, "status": trace.status},
                )
                seq += 1
                yield f"data: {stage_evt.model_dump_json()}\n\n"

            response_model = WorkflowAnalysisResponse.model_validate(result)

            # Persist run into history
            try:
                await history_service.persist_run(
                    db=db,
                    session=session,
                    response=response_model,
                )
            except Exception as exc:
                logger.warning("Failed to persist run in stream: %s", exc)

            # Final result event
            result_evt = StreamProgressEvent(
                request_id=request_id,
                seq=seq,
                event_type="result",
                status=result.status,
                elapsed_ms=round((time.monotonic() - start_time) * 1000, 2),
                result=response_model,
            )
            seq += 1
            yield f"data: {result_evt.model_dump_json()}\n\n"

            # Terminal completed event
            completed_evt = StreamProgressEvent(
                request_id=request_id,
                seq=seq,
                event_type="completed",
                status="completed",
                elapsed_ms=round((time.monotonic() - start_time) * 1000, 2),
            )
            yield f"data: {completed_evt.model_dump_json()}\n\n"

        except AnalyticalOverloadError as oe:
            err_evt = StreamProgressEvent(
                request_id=request_id,
                seq=seq,
                event_type="error",
                status="overloaded",
                elapsed_ms=round((time.monotonic() - start_time) * 1000, 2),
                payload={"detail": oe.message, "retry_after": oe.retry_after},
            )
            yield f"data: {err_evt.model_dump_json()}\n\n"
        except Exception as e:
            err_evt = StreamProgressEvent(
                request_id=request_id,
                seq=seq,
                event_type="error",
                status="failed",
                elapsed_ms=round((time.monotonic() - start_time) * 1000, 2),
                payload={"detail": str(e)},
            )
            yield f"data: {err_evt.model_dump_json()}\n\n"
        finally:
            if workflow_task is not None and not workflow_task.done():
                workflow_task.cancel()
                try:
                    await workflow_task
                except (asyncio.CancelledError, Exception) as cleanup_exc:
                    logger.debug("Cleaned up cancelled workflow task: %s", cleanup_exc)
            await cancellation_registry.unregister(request_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/{dataset_id}/analysis/{request_id}/cancel",
    response_model=CancellationResponse,
    summary="Cooperatively cancel an active analytical request",
)
async def cancel_dataset_workflow_analysis(
    dataset_id: uuid.UUID,
    request_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> CancellationResponse:
    """Signal cooperative cancellation to an active analytical request owned by the user."""
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

    cancelled = await cancellation_registry.cancel(
        request_id=request_id,
        user_id=current_user.id,
    )
    if not cancelled:
        return CancellationResponse(
            request_id=request_id,
            status="not_found_or_finished",
            message="Request is no longer active or was already completed.",
        )

    return CancellationResponse(
        request_id=request_id,
        status="cancelled",
        message="Cancellation signal transmitted successfully.",
    )

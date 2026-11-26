"""AnalytIQ History Service - Management and persistence of analytical sessions and runs."""

import math
import uuid
from typing import Any

from app.models.analysis_history import AnalysisRun, AnalysisSession
from app.schemas.analysis import WorkflowAnalysisResponse
from app.schemas.history import (
    AnalysisRunDetail,
    AnalysisSessionListResponse,
    AnalysisSessionResponse,
    AnalysisSessionSummary,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class AnalysisHistoryService:
    """Service handling durable analytical sessions, run records, and ownership checks."""

    @staticmethod
    def _generate_default_title(question: str) -> str:
        """Deterministically derive a clean concise title from the initial user question."""
        cleaned = " ".join(question.strip().split())
        if len(cleaned) <= 60:
            return cleaned
        return cleaned[:57].rstrip() + "..."

    async def get_or_create_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        dataset_id: uuid.UUID,
        session_id: uuid.UUID | None = None,
        initial_question: str | None = None,
    ) -> AnalysisSession:
        """Find an existing session owned by the user, or create a new session."""
        if session_id:
            stmt = (
                select(AnalysisSession)
                .where(
                    AnalysisSession.id == session_id,
                    AnalysisSession.user_id == user_id,
                )
                .options(selectinload(AnalysisSession.dataset))
            )
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                if existing.dataset_id != dataset_id:
                    raise ValueError(
                        f"Session {session_id} belongs to dataset {existing.dataset_id}, "
                        f"not {dataset_id}."
                    )
                return existing

        title = (
            self._generate_default_title(initial_question) if initial_question else "New Analysis"
        )
        new_session = AnalysisSession(
            id=session_id or uuid.uuid4(),
            user_id=user_id,
            dataset_id=dataset_id,
            title=title,
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        return new_session

    async def list_sessions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        dataset_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AnalysisSessionListResponse:
        """List analytical sessions for an authenticated user with pagination."""
        query = select(AnalysisSession).where(AnalysisSession.user_id == user_id)
        if dataset_id:
            query = query.where(AnalysisSession.dataset_id == dataset_id)

        count_stmt = select(func.count()).select_from(query.subquery())
        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        total_pages = math.ceil(total / page_size) if total > 0 else 1
        offset = (page - 1) * page_size

        stmt = (
            query.options(selectinload(AnalysisSession.dataset), selectinload(AnalysisSession.runs))
            .order_by(AnalysisSession.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        res = await db.execute(stmt)
        sessions = res.scalars().all()

        items: list[AnalysisSessionSummary] = []
        for s in sessions:
            runs = s.runs
            last_question = runs[-1].question if runs else None
            dataset_name = s.dataset.name if s.dataset else None
            items.append(
                AnalysisSessionSummary(
                    id=s.id,
                    dataset_id=s.dataset_id,
                    dataset_name=dataset_name,
                    title=s.title,
                    run_count=len(runs),
                    last_question=last_question,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
            )

        return AnalysisSessionListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_session(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AnalysisSessionResponse | None:
        """Retrieve complete session history with reconstructed analytical runs."""
        stmt = (
            select(AnalysisSession)
            .where(
                AnalysisSession.id == session_id,
                AnalysisSession.user_id == user_id,
            )
            .options(selectinload(AnalysisSession.dataset), selectinload(AnalysisSession.runs))
        )
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            return None

        runs_detail: list[AnalysisRunDetail] = []
        for r in session.runs:
            res_payload: dict[str, Any] = r.result_payload or {}
            runs_detail.append(
                AnalysisRunDetail(
                    id=r.id,
                    session_id=r.session_id,
                    request_id=r.request_id,
                    question=r.question,
                    intent=r.intent,
                    status=r.status,
                    authoritative_answer=r.authoritative_answer,
                    executed_sql=r.executed_sql,
                    columns=res_payload.get("columns", []),
                    rows=res_payload.get("rows", []),
                    returned_row_count=r.returned_row_count,
                    dataset_row_count=r.dataset_row_count,
                    total_row_count=r.total_row_count,
                    truncated=r.truncated,
                    unsupported_reason=r.unsupported_reason,
                    error_message=r.error_message,
                    evidence=r.evidence_payload,  # type: ignore[reportArgumentType]
                    verification=r.verification_payload,  # type: ignore[reportArgumentType]
                    clarification=r.clarification_payload,  # type: ignore[reportArgumentType]
                    created_at=r.created_at,
                    completed_at=r.completed_at,
                )
            )

        return AnalysisSessionResponse(
            id=session.id,
            user_id=session.user_id,
            dataset_id=session.dataset_id,
            dataset_name=session.dataset.name if session.dataset else None,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            runs=runs_detail,
        )

    async def update_session_title(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
    ) -> AnalysisSession | None:
        """Rename an analytical workspace session."""
        stmt = select(AnalysisSession).where(
            AnalysisSession.id == session_id,
            AnalysisSession.user_id == user_id,
        )
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            return None

        session.title = title.strip()
        await db.commit()
        await db.refresh(session)
        return session

    async def delete_session(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete an analytical workspace session and all associated runs (cascaded)."""
        stmt = select(AnalysisSession).where(
            AnalysisSession.id == session_id,
            AnalysisSession.user_id == user_id,
        )
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            return False

        await db.delete(session)
        await db.commit()
        return True

    async def persist_run(
        self,
        db: AsyncSession,
        session: AnalysisSession,
        response: WorkflowAnalysisResponse,
    ) -> AnalysisRun:
        """Idempotently persist an analytical run record linked to a session."""
        check_stmt = select(AnalysisRun).where(AnalysisRun.request_id == response.request_id)
        check_res = await db.execute(check_stmt)
        existing_run = check_res.scalar_one_or_none()
        if existing_run:
            return existing_run

        authoritative = None
        if response.verification and response.verification.verified_explanation:
            authoritative = response.verification.verified_explanation
        elif response.interpretation and response.interpretation.summary:
            authoritative = response.interpretation.summary

        result_payload = {
            "columns": [col.model_dump(mode="json") for col in response.columns],
            "rows": response.rows,
        }

        verification_payload = (
            response.verification.model_dump(mode="json") if response.verification else None
        )
        evidence_payload = response.evidence.model_dump(mode="json") if response.evidence else None
        clarification_payload = (
            response.clarification.model_dump(mode="json") if response.clarification else None
        )

        run = AnalysisRun(
            session_id=session.id,
            request_id=response.request_id,
            question=response.question,
            intent=response.intent,
            status=response.status,
            authoritative_answer=authoritative,
            executed_sql=response.executed_sql,
            result_payload=result_payload,
            verification_payload=verification_payload,
            evidence_payload=evidence_payload,
            clarification_payload=clarification_payload,
            unsupported_reason=response.unsupported_reason,
            error_message=response.error_message,
            returned_row_count=response.returned_row_count,
            dataset_row_count=response.dataset_row_count,
            total_row_count=response.total_row_count,
            truncated=response.truncated,
        )

        db.add(run)
        if session.title in ("New Analysis", "Untitled Analysis"):
            session.title = self._generate_default_title(response.question)

        await db.commit()
        await db.refresh(run)
        return run


history_service = AnalysisHistoryService()

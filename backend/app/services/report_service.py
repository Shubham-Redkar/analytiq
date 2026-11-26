"""AnalytIQ Services - High-level Report management and persistence service."""

import logging
import uuid
from collections.abc import Sequence

from app.models.analysis_history import AnalysisSession
from app.models.report import Report
from app.reports.builder import ReportBuilder
from app.reports.contracts import ReportDocument
from app.schemas.report import CreateReportRequest, UpdateReportRequest
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


class ReportService:
    """Manages the creation, retrieval, updates, duplication, and deletion of reports."""

    async def create_report(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: CreateReportRequest,
    ) -> Report:
        """Compile selected session runs into a persistent Report."""
        # 1. Fetch and verify ownership of AnalysisSession
        session_stmt = (
            select(AnalysisSession)
            .where(
                AnalysisSession.id == payload.analysis_session_id,
                AnalysisSession.user_id == user_id,
            )
            .options(selectinload(AnalysisSession.runs), selectinload(AnalysisSession.dataset))
        )
        res = await db.execute(session_stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis session '{payload.analysis_session_id}' not found.",
            )

        # 2. Filter requested runs or use all completed runs if none specified
        all_runs = session.runs
        if payload.run_ids:
            requested_set = set(payload.run_ids)
            selected_runs = [
                r for r in all_runs if str(r.id) in requested_set or r.request_id in requested_set
            ]
        else:
            selected_runs = [r for r in all_runs if r.status not in ["failed", "cancelled"]]

        if not selected_runs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No eligible completed analytical runs available to generate report.",
            )

        # 3. Build structured ReportDocument
        report_id = uuid.uuid4()
        doc = ReportBuilder.build_report_document(
            report_id=report_id,
            session=session,
            dataset=session.dataset,
            runs=selected_runs,
            title=payload.title,
            description=payload.description,
        )

        # 4. Persist Report entity
        report = Report(
            id=report_id,
            user_id=user_id,
            dataset_id=session.dataset_id,
            analysis_session_id=session.id,
            title=doc.metadata.title,
            description=doc.metadata.description,
            status="ready",
            schema_version=doc.schema_version,
            revision=1,
            document=doc.model_dump(mode="json"),
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        logger.info("Created report: id=%s title='%s' user_id=%s", report.id, report.title, user_id)
        return report

    async def list_reports(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        dataset_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Report]:
        """List reports owned by the user, ordered by last updated."""
        stmt = (
            select(Report)
            .where(Report.user_id == user_id)
            .options(selectinload(Report.dataset))
            .order_by(Report.updated_at.desc())
            .limit(min(limit, 100))
            .offset(offset)
        )
        if dataset_id:
            stmt = stmt.where(Report.dataset_id == dataset_id)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_report_count(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Return total count of reports owned by user."""
        stmt = select(func.count(Report.id)).where(Report.user_id == user_id)
        res = await db.execute(stmt)
        return res.scalar() or 0

    async def get_report(
        self,
        db: AsyncSession,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Report:
        """Retrieve a specific report enforcing ownership."""
        stmt = (
            select(Report)
            .where(Report.id == report_id, Report.user_id == user_id)
            .options(selectinload(Report.dataset))
        )
        res = await db.execute(stmt)
        report = res.scalar_one_or_none()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report '{report_id}' not found.",
            )
        return report

    async def update_report(
        self,
        db: AsyncSession,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: UpdateReportRequest,
    ) -> Report:
        """Update report metadata or document with optimistic concurrency check."""
        report = await self.get_report(db, report_id, user_id)

        # Optimistic concurrency check
        if report.revision != payload.revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Report was modified by another operation. "
                    f"Expected revision {report.revision}, received {payload.revision}."
                ),
            )

        if payload.title is not None:
            report.title = payload.title.strip()[:120]
        if payload.description is not None:
            report.description = payload.description.strip()[:1000]

        if payload.document is not None:
            report.document = payload.document.model_dump(mode="json")

        report.revision += 1
        await db.commit()
        await db.refresh(report)
        return report

    async def duplicate_report(
        self,
        db: AsyncSession,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Report:
        """Create a duplicate copy of an existing report."""
        orig = await self.get_report(db, report_id, user_id)
        new_id = uuid.uuid4()
        new_title = f"{orig.title} (Copy)"[:120]

        # Clone document and update metadata id and title
        doc = ReportDocument.model_validate(orig.document)
        doc.metadata.report_id = str(new_id)
        doc.metadata.title = new_title

        dup = Report(
            id=new_id,
            user_id=user_id,
            dataset_id=orig.dataset_id,
            analysis_session_id=orig.analysis_session_id,
            title=new_title,
            description=orig.description,
            status=orig.status,
            schema_version=orig.schema_version,
            revision=1,
            document=doc.model_dump(mode="json"),
        )
        db.add(dup)
        await db.commit()
        await db.refresh(dup)
        return dup

    async def delete_report(
        self,
        db: AsyncSession,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete an owned report record."""
        report = await self.get_report(db, report_id, user_id)
        await db.delete(report)
        await db.commit()
        return True


report_service = ReportService()

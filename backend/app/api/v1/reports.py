"""AnalytIQ API v1 - Authenticated Report management and export endpoints."""

import logging
import math
import uuid

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import PlainTextResponse

from app.api.deps import CurrentUser, DatabaseSession
from app.reports.contracts import ReportDocument
from app.reports.exporters.csv import CSVExporter
from app.reports.exporters.pdf import PDFExporter
from app.schemas.report import (
    CreateReportRequest,
    ReportDetailResponse,
    ReportListResponse,
    ReportSummaryResponse,
    UpdateReportRequest,
)
from app.services.report_service import report_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=ReportDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new analytical report from session runs",
)
async def create_report(
    payload: CreateReportRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> ReportDetailResponse:
    """Compile selected session runs into a persistent Report."""
    report = await report_service.create_report(
        db=db,
        user_id=current_user.id,
        payload=payload,
    )
    doc = ReportDocument.model_validate(report.document)
    return ReportDetailResponse(
        id=report.id,
        dataset_id=report.dataset_id,
        analysis_session_id=report.analysis_session_id,
        title=report.title,
        description=report.description,
        status=report.status,
        revision=report.revision,
        schema_version=report.schema_version,
        document=doc,
        created_at=report.created_at,
        updated_at=report.updated_at,
        generated_at=report.generated_at,
    )


@router.get(
    "",
    response_model=ReportListResponse,
    summary="List all reports owned by the authenticated user",
)
async def list_reports(
    current_user: CurrentUser,
    db: DatabaseSession,
    dataset_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int | None = Query(default=None, ge=0),
) -> ReportListResponse:
    """Retrieve summarized reports list with pagination metadata."""
    effective_limit = limit if limit is not None else page_size
    effective_offset = offset if offset is not None else (page - 1) * page_size

    reports = await report_service.list_reports(
        db=db,
        user_id=current_user.id,
        dataset_id=dataset_id,
        limit=effective_limit,
        offset=effective_offset,
    )
    total = await report_service.get_report_count(db=db, user_id=current_user.id)
    pages = max(1, math.ceil(total / effective_limit))

    items = [
        ReportSummaryResponse(
            id=r.id,
            dataset_id=r.dataset_id,
            dataset_name=r.dataset.name if r.dataset else "Dataset",
            analysis_session_id=r.analysis_session_id,
            title=r.title,
            description=r.description,
            status=r.status,
            revision=r.revision,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in reports
    ]
    return ReportListResponse(
        items=items,
        total=total,
        page=page,
        page_size=effective_limit,
        pages=pages,
    )


@router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    summary="Get full report details and document",
)
async def get_report_detail(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> ReportDetailResponse:
    """Retrieve specific report enforcing ownership."""
    report = await report_service.get_report(db, report_id, current_user.id)
    doc = ReportDocument.model_validate(report.document)
    return ReportDetailResponse(
        id=report.id,
        dataset_id=report.dataset_id,
        analysis_session_id=report.analysis_session_id,
        title=report.title,
        description=report.description,
        status=report.status,
        revision=report.revision,
        schema_version=report.schema_version,
        document=doc,
        created_at=report.created_at,
        updated_at=report.updated_at,
        generated_at=report.generated_at,
    )


@router.patch(
    "/{report_id}",
    response_model=ReportDetailResponse,
    summary="Update report title, description, or section document",
)
async def update_report(
    report_id: uuid.UUID,
    payload: UpdateReportRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> ReportDetailResponse:
    """Update report metadata or document."""
    report = await report_service.update_report(
        db=db,
        report_id=report_id,
        user_id=current_user.id,
        payload=payload,
    )
    doc = ReportDocument.model_validate(report.document)
    return ReportDetailResponse(
        id=report.id,
        dataset_id=report.dataset_id,
        analysis_session_id=report.analysis_session_id,
        title=report.title,
        description=report.description,
        status=report.status,
        revision=report.revision,
        schema_version=report.schema_version,
        document=doc,
        created_at=report.created_at,
        updated_at=report.updated_at,
        generated_at=report.generated_at,
    )


@router.post(
    "/{report_id}/duplicate",
    response_model=ReportDetailResponse,
    summary="Duplicate an existing report",
)
async def duplicate_report(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> ReportDetailResponse:
    """Create a duplicate copy of a report."""
    report = await report_service.duplicate_report(db, report_id, current_user.id)
    doc = ReportDocument.model_validate(report.document)
    return ReportDetailResponse(
        id=report.id,
        dataset_id=report.dataset_id,
        analysis_session_id=report.analysis_session_id,
        title=report.title,
        description=report.description,
        status=report.status,
        revision=report.revision,
        schema_version=report.schema_version,
        document=doc,
        created_at=report.created_at,
        updated_at=report.updated_at,
        generated_at=report.generated_at,
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an owned report",
)
async def delete_report(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Response:
    """Delete an owned report."""
    await report_service.delete_report(db, report_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{report_id}/export/pdf",
    summary="Export report as a formatted PDF document",
)
async def export_report_pdf(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Response:
    """Generate and return a professional PDF export."""
    report = await report_service.get_report(db, report_id, current_user.id)
    pdf_bytes = PDFExporter.export_report_to_pdf(report)
    filename = f"AnalytIQ_Report_{report.title.replace(' ', '_')[:40]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )


@router.get(
    "/{report_id}/export/csv",
    summary="Export tabular results from report as CSV",
)
async def export_report_csv(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> PlainTextResponse:
    """Export tabular result data to CSV with formula injection protection."""
    report = await report_service.get_report(db, report_id, current_user.id)
    csv_text = CSVExporter.export_report_tables_to_csv(report)
    filename = f"AnalytIQ_Export_{report.title.replace(' ', '_')[:40]}.csv"

    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )

"""Unit and integration tests for AnalytIQ Report Generation, Management, and Export."""

import uuid

import pytest
from app.models.analysis_history import AnalysisRun, AnalysisSession
from app.models.dataset import Dataset
from app.models.report import Report
from app.models.user import User
from app.reports.builder import ReportBuilder
from app.reports.contracts import (
    ReportDocument,
)
from app.reports.exporters.csv import CSVExporter
from app.reports.exporters.pdf import PDFExporter
from app.schemas.report import CreateReportRequest, UpdateReportRequest
from app.services.report_service import report_service
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_datasets import register_and_login


def test_csv_formula_injection_sanitization():
    """Verify CSV exporter prepends quote to dangerous formula triggers: =, +, -, @, tab, CR."""
    assert CSVExporter.sanitize_cell_value("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert CSVExporter.sanitize_cell_value("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert CSVExporter.sanitize_cell_value("-5+2") == "'-5+2"
    assert CSVExporter.sanitize_cell_value("@SUM") == "'@SUM"
    assert CSVExporter.sanitize_cell_value("\tTAB_START") == "'\tTAB_START"
    assert CSVExporter.sanitize_cell_value("\rCR_START") == "'\rCR_START"
    assert CSVExporter.sanitize_cell_value("safe_val") == "safe_val"
    # Preserves actual negative numbers
    assert CSVExporter.sanitize_cell_value("-42.5") == "-42.5"
    assert CSVExporter.sanitize_cell_value(-100) == -100


def test_report_builder_creates_evidence_grounded_document():
    """Test ReportBuilder generates valid structured document from session and runs."""
    owner_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    dataset = Dataset(
        id=dataset_id,
        owner_id=owner_id,
        name="Titanic Passenger Data",
        original_filename="titanic.csv",
        file_format="csv",
        storage_key=f"datasets/{uuid.uuid4()}.csv",
        file_size_bytes=1024,
        row_count=418,
        column_count=12,
        schema_json={
            "columns": [
                {"name": "pclass", "type": "INTEGER"},
                {"name": "survived", "type": "INTEGER"},
                {"name": "fare", "type": "FLOAT"},
            ]
        },
    )
    session = AnalysisSession(
        id=uuid.uuid4(),
        user_id=owner_id,
        dataset_id=dataset_id,
        title="Titanic Exploration",
    )
    run1 = AnalysisRun(
        id=uuid.uuid4(),
        session_id=session.id,
        request_id="req_run1_count",
        question="How many records are in this dataset?",
        status="completed",
        executed_sql="SELECT COUNT(*) AS total_records FROM titanic",
        result_payload={
            "columns": [{"name": "total_records", "type": "int"}],
            "rows": [[418]],
            "row_count": 1,
            "truncated": False,
        },
        verification_payload={
            "claims": [
                {
                    "claim_id": "c1",
                    "claim_text": "The dataset contains 418 records.",
                    "claim_type": "record_count",
                    "metric_name": "total_records",
                    "claimed_value": 418,
                    "verified": True,
                    "reason_code": "MATCH",
                    "evidence_fingerprint": "fp_count_418",
                }
            ],
            "all_verified": True,
        },
        evidence_payload={
            "request_id": "req_run1_count",
            "result_fingerprint": "rfp_1",
            "dataset_fingerprint": "dfp_1",
            "verification_status": "verified",
        },
    )
    run2 = AnalysisRun(
        id=uuid.uuid4(),
        session_id=session.id,
        request_id="req_run2_fare",
        question="What is the average fare by passenger class?",
        status="completed",
        executed_sql=(
            "SELECT pclass, AVG(fare) AS avg_fare FROM titanic GROUP BY pclass ORDER BY pclass"
        ),
        result_payload={
            "columns": [
                {"name": "pclass", "type": "int"},
                {"name": "avg_fare", "type": "float"},
            ],
            "rows": [[1, 84.15], [2, 20.66], [3, 13.68]],
            "row_count": 3,
            "truncated": False,
        },
        verification_payload={
            "claims": [
                {
                    "claim_id": "c2",
                    "claim_text": "First class average fare was 84.15.",
                    "claim_type": "scalar_metric",
                    "metric_name": "avg_fare",
                    "claimed_value": 84.15,
                    "verified": True,
                    "reason_code": "MATCH",
                    "evidence_fingerprint": "fp_fare_class1",
                }
            ],
            "all_verified": True,
        },
        evidence_payload={
            "request_id": "req_run2_fare",
            "result_fingerprint": "rfp_2",
            "dataset_fingerprint": "dfp_1",
            "verification_status": "verified",
        },
    )

    report_id = uuid.uuid4()
    doc = ReportBuilder.build_report_document(
        report_id=report_id,
        session=session,
        dataset=dataset,
        runs=[run1, run2],
        title="Custom Report Title",
        description="A verified report on Titanic data.",
    )

    assert isinstance(doc, ReportDocument)
    assert doc.metadata.title == "Custom Report Title"
    assert doc.dataset_overview.dataset_name == "Titanic Passenger Data"
    assert doc.dataset_overview.row_count == 418
    assert len(doc.sections) == 2
    assert "418 records" in doc.executive_summary
    assert len(doc.evidence_appendix) == 2


def test_pdf_and_csv_export_generation():
    """Test PDF and CSV generation with Report model."""
    owner_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    dataset = Dataset(
        id=dataset_id,
        owner_id=owner_id,
        name="Titanic Passenger Data",
        original_filename="titanic.csv",
        file_format="csv",
        storage_key=f"datasets/{uuid.uuid4()}.csv",
        file_size_bytes=1024,
        row_count=418,
        column_count=12,
        schema_json={"columns": [{"name": "total_records", "type": "INTEGER"}]},
    )
    session = AnalysisSession(
        id=uuid.uuid4(),
        user_id=owner_id,
        dataset_id=dataset_id,
        title="Titanic Exploration",
    )
    run = AnalysisRun(
        id=uuid.uuid4(),
        session_id=session.id,
        request_id="req_run1_count",
        question="How many records are in this dataset?",
        status="completed",
        executed_sql="SELECT COUNT(*) AS total_records FROM titanic",
        result_payload={
            "columns": [{"name": "total_records", "type": "int"}],
            "rows": [[418]],
            "row_count": 1,
            "truncated": False,
        },
    )
    report_id = uuid.uuid4()
    doc = ReportBuilder.build_report_document(
        report_id=report_id,
        session=session,
        dataset=dataset,
        runs=[run],
    )
    report_model = Report(
        id=report_id,
        user_id=owner_id,
        dataset_id=dataset_id,
        analysis_session_id=session.id,
        title=doc.metadata.title,
        status="ready",
        document=doc.model_dump(mode="json"),
    )

    pdf_bytes = PDFExporter.export_report_to_pdf(report_model)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")

    csv_text = CSVExporter.export_report_tables_to_csv(report_model)
    assert isinstance(csv_text, str)
    assert "Section: How many records are in this dataset?" in csv_text
    assert "total_records" in csv_text
    assert "418" in csv_text


@pytest.mark.asyncio
async def test_report_service_crud_and_duplication(
    db_session: AsyncSession,
):
    """Test ReportService create, get, update, duplicate, and delete operations."""
    user = User(
        id=uuid.uuid4(),
        email="report_tester@example.com",
        password_hash="fake_hash",
        display_name="Report Tester",
    )
    db_session.add(user)
    await db_session.flush()

    dataset = Dataset(
        id=uuid.uuid4(),
        owner_id=user.id,
        name="Test Dataset",
        original_filename="test.csv",
        file_format="csv",
        storage_key=f"datasets/{uuid.uuid4()}.csv",
        file_size_bytes=512,
        row_count=100,
        column_count=2,
        schema_json={"columns": [{"name": "col1", "type": "int"}]},
    )
    session = AnalysisSession(
        id=uuid.uuid4(),
        user_id=user.id,
        dataset_id=dataset.id,
        title="Test Session",
    )
    run = AnalysisRun(
        id=uuid.uuid4(),
        session_id=session.id,
        request_id="req_test",
        question="What is col1?",
        status="completed",
        executed_sql="SELECT col1 FROM tbl",
        result_payload={
            "columns": [{"name": "col1", "type": "int"}],
            "rows": [[1]],
            "row_count": 1,
            "truncated": False,
        },
    )
    db_session.add(dataset)
    db_session.add(session)
    db_session.add(run)
    await db_session.commit()

    # 1. Create Report
    req = CreateReportRequest(
        analysis_session_id=session.id,
        title="Session Summary Report",
        description="Comprehensive summary",
    )
    report = await report_service.create_report(db_session, user.id, req)
    assert report.id is not None
    assert report.title == "Session Summary Report"
    assert report.user_id == user.id
    assert report.revision == 1

    # 2. Get Detail
    detail = await report_service.get_report(db_session, report.id, user.id)
    assert detail is not None
    assert detail.id == report.id
    assert len(detail.document["sections"]) == 1

    # 3. Update Report (reordering/renaming)
    doc_dict = dict(detail.document)
    doc_dict["executive_summary"] = "Updated executive summary."
    parsed_doc = ReportDocument.model_validate(doc_dict)
    update_req = UpdateReportRequest(
        title="Renamed Report",
        document=parsed_doc,
        revision=1,
    )
    updated = await report_service.update_report(db_session, report.id, user.id, update_req)
    assert updated.title == "Renamed Report"
    assert updated.revision == 2
    assert updated.document["executive_summary"] == "Updated executive summary."

    # 4. Duplicate Report
    duplicate = await report_service.duplicate_report(db_session, report.id, user.id)
    assert duplicate.id != report.id
    assert "Copy" in duplicate.title
    assert duplicate.revision == 1

    # 5. List Reports
    items = await report_service.list_reports(db_session, user.id, limit=10, offset=0)
    total = await report_service.get_report_count(db_session, user.id)
    assert total >= 2
    assert any(r.id == report.id for r in items)
    assert any(r.id == duplicate.id for r in items)

    # 6. Delete Report
    await report_service.delete_report(db_session, report.id, user.id)

    # 7. Verify Deleted is Gone
    with pytest.raises(HTTPException) as exc_info:
        await report_service.get_report(db_session, report.id, user.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_report_api_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test full HTTP API lifecycle for reports under /api/v1/reports."""
    await register_and_login(client, "api_report_user@example.com", "API Reporter")

    user_res = await db_session.execute(
        select(User).where(User.email == "api_report_user@example.com")
    )
    user = user_res.scalar_one()

    dataset = Dataset(
        id=uuid.uuid4(),
        owner_id=user.id,
        name="API Test Dataset",
        original_filename="api_test.csv",
        file_format="csv",
        storage_key=f"datasets/{uuid.uuid4()}.csv",
        file_size_bytes=100,
        row_count=50,
        column_count=2,
        schema_json={"columns": [{"name": "val", "type": "int"}]},
    )
    session = AnalysisSession(
        id=uuid.uuid4(),
        user_id=user.id,
        dataset_id=dataset.id,
        title="API Test Session",
    )
    run = AnalysisRun(
        id=uuid.uuid4(),
        session_id=session.id,
        request_id="req_api_test",
        question="What is the val count?",
        status="completed",
        executed_sql="SELECT COUNT(val) AS val_count FROM tbl",
        result_payload={
            "columns": [{"name": "val_count", "type": "int"}],
            "rows": [[50]],
            "row_count": 1,
            "truncated": False,
        },
    )
    db_session.add(dataset)
    db_session.add(session)
    db_session.add(run)
    await db_session.commit()

    # 1. Create Report via API
    create_payload = {
        "analysis_session_id": str(session.id),
        "title": "API Created Report",
        "description": "Created via API endpoint",
    }
    resp = await client.post("/api/v1/reports", json=create_payload)
    assert resp.status_code == 201
    data = resp.json()
    report_id = data["id"]
    assert data["title"] == "API Created Report"

    # 2. Get Report Detail
    resp = await client.get(f"/api/v1/reports/{report_id}")
    assert resp.status_code == 200
    detail_data = resp.json()
    assert detail_data["id"] == report_id
    assert len(detail_data["document"]["sections"]) == 1

    # 3. Export PDF via API
    pdf_resp = await client.get(f"/api/v1/reports/{report_id}/export/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF-")

    # 4. Export CSV via API
    csv_resp = await client.get(f"/api/v1/reports/{report_id}/export/csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "val_count" in csv_resp.text

    # 5. Duplicate Report via API
    dup_resp = await client.post(f"/api/v1/reports/{report_id}/duplicate")
    assert dup_resp.status_code == 200
    dup_id = dup_resp.json()["id"]
    assert dup_id != report_id

    # 6. Delete Report via API
    del_resp = await client.delete(f"/api/v1/reports/{report_id}")
    assert del_resp.status_code == 204

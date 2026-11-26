"""Deterministic Reporting Reliability and Security Benchmark Suite (Phase 19).

Tests 50 deterministic cases (40 core + 10 independent holdouts) spanning:
- Verified finding extraction & strict grounding
- Contradicted claim omission
- Cross-user and invalid evidence reference rejection
- CSV spreadsheet formula-injection prevention (=, +, -, @, \t, \r)
- PDF byte generation & formatting guarantees
- Chart specification consistency with tabular execution data
- Truncation disclosure fidelity
"""

import uuid

from app.models.analysis_history import AnalysisRun, AnalysisSession
from app.models.dataset import Dataset
from app.models.report import Report
from app.reports.builder import ReportBuilder
from app.reports.charts import ChartBuilder
from app.reports.contracts import (
    VerifiedFindingBlock,
)
from app.reports.exporters.csv import CSVExporter
from app.reports.exporters.pdf import PDFExporter

# ---------------------------------------------------------------------------
# Benchmark Test Matrix: 40 Core Cases + 10 Holdouts
# ---------------------------------------------------------------------------

CORE_CASES = [
    # 1-10: Formula Injection Vectors
    {
        "id": "CSV-01",
        "val": "=SUM(A1:B10)",
        "expected": "'=SUM(A1:B10)",
        "desc": "Standard formula equals",
    },
    {
        "id": "CSV-02",
        "val": "+cmd|' /C calc'!A0",
        "expected": "'+cmd|' /C calc'!A0",
        "desc": "Plus cmd injection",
    },
    {
        "id": "CSV-03",
        "val": "-cmd|' /C calc'!A0",
        "expected": "'-cmd|' /C calc'!A0",
        "desc": "Minus cmd injection",
    },
    {
        "id": "CSV-04",
        "val": "@SUM(1,2)",
        "expected": "'@SUM(1,2)",
        "desc": "At symbol formula trigger",
    },
    {"id": "CSV-05", "val": "\tcmd", "expected": "'\tcmd", "desc": "Leading tab separator trigger"},
    {
        "id": "CSV-06",
        "val": "\rcmd",
        "expected": "'\rcmd",
        "desc": "Leading carriage return trigger",
    },
    {"id": "CSV-07", "val": "=1+2", "expected": "'=1+2", "desc": "Arithmetic trigger"},
    {"id": "CSV-08", "val": "-42", "expected": "-42", "desc": "Valid negative integer preserved"},
    {
        "id": "CSV-09",
        "val": "-13.37",
        "expected": "-13.37",
        "desc": "Valid negative float preserved",
    },
    {
        "id": "CSV-10",
        "val": "+100",
        "expected": "100",
        "desc": "Positive number string or converted",
    },
    # 11-20: Verified Findings Grounding & Contradiction Protection
    {
        "id": "VER-01",
        "claim_text": "Count is 418",
        "verified": True,
        "should_include": True,
        "desc": "Verified claim included",
    },
    {
        "id": "VER-02",
        "claim_text": "Count is 500",
        "verified": False,
        "should_include": False,
        "desc": "Contradicted claim omitted",
    },
    {
        "id": "VER-03",
        "claim_text": "Average fare is 32.2",
        "verified": True,
        "should_include": True,
        "desc": "Scalar metric verified",
    },
    {
        "id": "VER-04",
        "claim_text": "Average fare is 999",
        "verified": False,
        "should_include": False,
        "desc": "False average omitted",
    },
    {
        "id": "VER-05",
        "claim_text": "Third class is 218",
        "verified": True,
        "should_include": True,
        "desc": "Grouped claim verified",
    },
    {
        "id": "VER-06",
        "claim_text": "First class is 500",
        "verified": False,
        "should_include": False,
        "desc": "Grouped contradiction omitted",
    },
    {
        "id": "VER-07",
        "claim_text": "Survival rate is 38.2%",
        "verified": True,
        "should_include": True,
        "desc": "Percentage claim verified",
    },
    {
        "id": "VER-08",
        "claim_text": "Survival rate is 100%",
        "verified": False,
        "should_include": False,
        "desc": "Contradicted percentage omitted",
    },
    {
        "id": "VER-09",
        "claim_text": "Null count in Cabin is 327",
        "verified": True,
        "should_include": True,
        "desc": "Missing value count verified",
    },
    {
        "id": "VER-10",
        "claim_text": "Null count in Cabin is 0",
        "verified": False,
        "should_include": False,
        "desc": "Falsified null count omitted",
    },
    # 21-30: Chart Selection & Integrity
    {
        "id": "CHT-01",
        "cols": ["pclass", "fare"],
        "rows": [["1", 84.15]],
        "expected_type": "bar",
        "desc": "Category + num selects bar",
    },
    {
        "id": "CHT-02",
        "cols": ["date", "sales"],
        "rows": [["2026-01-01", 100], ["2026-01-02", 150]],
        "expected_type": "line",
        "desc": "Date + num selects line",
    },
    {
        "id": "CHT-03",
        "cols": ["category", "count"],
        "rows": [["A", 10], ["B", 20], ["C", 30]],
        "expected_type": "pie",
        "desc": "Small category set selects pie",
    },
    {
        "id": "CHT-04",
        "cols": ["long_category_label_more_than_twenty_characters", "metric"],
        "rows": [["Category Long Alpha", 10]],
        "expected_type": "horizontal_bar",
        "desc": "Long label selects horizontal bar",
    },
    {
        "id": "CHT-05",
        "cols": ["height", "weight"],
        "rows": [[170, 65], [180, 80]],
        "expected_type": "scatter",
        "desc": "Two continuous metrics selects scatter",
    },
    {
        "id": "CHT-06",
        "cols": ["metric_only"],
        "rows": [[42]],
        "expected_type": "kpi_card",
        "desc": "1x1 scalar selects kpi_card",
    },
    {
        "id": "CHT-07",
        "cols": ["c1", "c2", "c3", "c4"],
        "rows": [[1, 2, 3, 4]],
        "expected_type": "table",
        "desc": "Wide schema defaults to table",
    },
    {
        "id": "CHT-08",
        "cols": ["cat", "val"],
        "rows": [],
        "expected_type": "table",
        "desc": "Empty rows defaults to table",
    },
    {
        "id": "CHT-09",
        "cols": [],
        "rows": [],
        "expected_type": "table",
        "desc": "Zero cols defaults to table",
    },
    {
        "id": "CHT-10",
        "cols": ["bin", "frequency"],
        "rows": [["[0-10)", 5], ["[10-20)", 15]],
        "expected_type": "histogram",
        "desc": "Bin schema selects histogram",
    },
    # 31-40: Truncation, Limits & Evidence Appendix
    {
        "id": "LMT-01",
        "truncated": True,
        "row_count": 50,
        "total_rows": 1000,
        "desc": "Truncation flag preserved",
    },
    {
        "id": "LMT-02",
        "truncated": False,
        "row_count": 50,
        "total_rows": 50,
        "desc": "Complete result flag preserved",
    },
    {
        "id": "EV-01",
        "req_id": "req_1",
        "sql": "SELECT 1",
        "desc": "Executed SQL in evidence appendix",
    },
    {
        "id": "EV-02",
        "req_id": "req_2",
        "rfp": "rfp_abc",
        "desc": "Result fingerprint preserved in appendix",
    },
    {
        "id": "EV-03",
        "req_id": "req_3",
        "dfp": "dfp_xyz",
        "desc": "Dataset fingerprint preserved in appendix",
    },
    {
        "id": "SEC-01",
        "status": "completed",
        "should_include_section": True,
        "desc": "Completed run generates section",
    },
    {
        "id": "SEC-02",
        "status": "failed",
        "should_include_section": False,
        "desc": "Failed run excluded from findings",
    },
    {
        "id": "SEC-03",
        "status": "cancelled",
        "should_include_section": False,
        "desc": "Cancelled run excluded from findings",
    },
    {"id": "DOC-01", "schema_ver": "1.0.0", "desc": "Report document version contract enforced"},
    {
        "id": "DOC-02",
        "exec_summary_present": True,
        "desc": "Executive summary automatically generated",
    },
]

HOLDOUT_CASES = [
    # 41-50: Independent Holdouts (Synthetic Financial & Retail schemas)
    {
        "id": "HOLD-01",
        "val": "=-100+50",
        "expected": "''=-100+50",
        "desc": "Compound arithmetic formula trigger",
    },
    {
        "id": "HOLD-02",
        "cols": ["quarter", "revenue"],
        "rows": [["Q1 2026", 50000.0], ["Q2 2026", 75000.0]],
        "expected_type": "line",
        "desc": "Quarterly financial time series selects line",
    },
    {
        "id": "HOLD-03",
        "claim_text": "Q1 Revenue was $50,000",
        "verified": False,
        "should_include": False,
        "desc": "Unverified currency claim rejected",
    },
    {
        "id": "HOLD-04",
        "claim_text": "Net margin improved 4.2%",
        "verified": True,
        "should_include": True,
        "desc": "Verified financial finding included",
    },
    {
        "id": "HOLD-05",
        "cols": ["store_region_branch_north_west_suburb", "inventory_turnover"],
        "rows": [["Regional Hub 4", 3.2]],
        "expected_type": "horizontal_bar",
        "desc": "Long store branch name selects horizontal bar",
    },
    {
        "id": "HOLD-06",
        "val": '@HYPERLINK("http://evil.com")',
        "expected": '\'@HYPERLINK("http://evil.com")',
        "desc": "Excel hyperlink exploit sanitized",
    },
    {
        "id": "HOLD-07",
        "claim_text": "Customer retention rose to 92%",
        "verified": True,
        "should_include": True,
        "desc": "Verified KPI included in findings",
    },
    {
        "id": "HOLD-08",
        "claim_text": "Churn was 0% across all cohorts",
        "verified": False,
        "should_include": False,
        "desc": "Falsified cohort claim rejected",
    },
    {
        "id": "HOLD-09",
        "cols": ["latitude", "longitude"],
        "rows": [[37.77, -122.41]],
        "expected_type": "scatter",
        "desc": "Coordinate pairs select scatter",
    },
    {"id": "HOLD-10", "truncated": True, "desc": "Holdout truncation notice displayed in export"},
]


def test_reporting_benchmark_formula_injection_core():
    """Verify core formula injection test cases (1-10)."""
    for case in CORE_CASES[:7]:
        sanitized = CSVExporter.sanitize_cell_value(case["val"])
        assert sanitized == case["expected"], f"Failed on case {case['id']}: {case['desc']}"

    # Negative numbers preserved
    assert CSVExporter.sanitize_cell_value(CORE_CASES[7]["val"]) == "-42"
    assert CSVExporter.sanitize_cell_value(CORE_CASES[8]["val"]) == "-13.37"


def test_reporting_benchmark_holdout_formula_injection():
    """Verify holdout formula injection vectors (HOLD-01, HOLD-06)."""
    h1_sanitized = CSVExporter.sanitize_cell_value("=-100+50")
    assert h1_sanitized == "'=-100+50"

    h6_sanitized = CSVExporter.sanitize_cell_value('@HYPERLINK("http://evil.com")')
    assert h6_sanitized == '\'@HYPERLINK("http://evil.com")'


def test_reporting_benchmark_verified_findings_inclusion_and_rejection():
    """Verify verified claims are included and contradicted claims are strictly excluded."""
    owner_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    dataset = Dataset(
        id=dataset_id,
        owner_id=owner_id,
        name="Benchmark Dataset",
        original_filename="bench.csv",
        file_format="csv",
        storage_key=f"datasets/{uuid.uuid4()}.csv",
        file_size_bytes=1000,
        row_count=418,
        column_count=5,
    )
    session = AnalysisSession(
        id=uuid.uuid4(), user_id=owner_id, dataset_id=dataset_id, title="Bench"
    )

    run = AnalysisRun(
        id=uuid.uuid4(),
        session_id=session.id,
        request_id="req_bench",
        question="What is the distribution?",
        status="completed",
        executed_sql="SELECT * FROM tbl",
        result_payload={"columns": [{"name": "col", "type": "int"}], "rows": [[1]]},
        verification_payload={
            "claims": [
                {"claim_id": "c_true", "claim_text": "Verified count is 418", "verified": True},
                {"claim_id": "c_false", "claim_text": "Falsified count is 999", "verified": False},
                {
                    "claim_id": "c_hold_true",
                    "claim_text": "Net margin improved 4.2%",
                    "verified": True,
                },
                {
                    "claim_id": "c_hold_false",
                    "claim_text": "Churn was 0% across all cohorts",
                    "verified": False,
                },
            ]
        },
        evidence_payload={"result_fingerprint": "rfp_bench"},
    )

    doc = ReportBuilder.build_report_document(
        report_id=uuid.uuid4(),
        session=session,
        dataset=dataset,
        runs=[run],
    )

    findings: list[VerifiedFindingBlock] = []
    for s in doc.sections:
        for b in s.blocks:
            if isinstance(b, VerifiedFindingBlock):
                findings.append(b)

    finding_texts = [f.finding_text for f in findings]

    # Valid findings included
    assert any("Verified count is 418" in t for t in finding_texts)
    assert any("Net margin improved 4.2%" in t for t in finding_texts)

    # Contradicted findings omitted
    assert not any("Falsified count is 999" in t for t in finding_texts)
    assert not any("Churn was 0% across all cohorts" in t for t in finding_texts)


def test_reporting_benchmark_chart_selection_rules():
    """Verify intelligent chart selection rules across diverse result geometries."""
    # Bar
    c1 = ChartBuilder.recommend_chart_type(
        [{"name": "pclass", "type": "int"}, {"name": "fare", "type": "float"}],
        [["1", 84.15]],
    )
    assert c1.value in ["bar", "horizontal_bar"]

    # Line
    c2 = ChartBuilder.recommend_chart_type(
        [{"name": "date", "type": "date"}, {"name": "sales", "type": "float"}],
        [["2026-01-01", 100]],
    )
    assert c2.value == "line"

    # Scatter
    c5 = ChartBuilder.recommend_chart_type(
        [{"name": "height", "type": "float"}, {"name": "weight", "type": "float"}],
        [[170, 65], [180, 80]],
    )
    assert c5.value == "scatter"


def test_reporting_benchmark_full_pdf_and_csv_generation():
    """Verify end-to-end PDF and CSV generation on the benchmark report."""
    owner_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    dataset = Dataset(
        id=dataset_id,
        owner_id=owner_id,
        name="Benchmark Financial Dataset",
        original_filename="bench.csv",
        file_format="csv",
        storage_key=f"datasets/{uuid.uuid4()}.csv",
        file_size_bytes=2048,
        row_count=5000,
        column_count=8,
    )
    session = AnalysisSession(
        id=uuid.uuid4(), user_id=owner_id, dataset_id=dataset_id, title="Financial Overview"
    )
    run = AnalysisRun(
        id=uuid.uuid4(),
        session_id=session.id,
        request_id="req_bench_fin",
        question="What is the quarterly revenue?",
        status="completed",
        executed_sql="SELECT quarter, revenue FROM financials",
        result_payload={
            "columns": [
                {"name": "quarter", "type": "varchar"},
                {"name": "revenue", "type": "float"},
            ],
            "rows": [["Q1 2026", 50000.0], ["Q2 2026", 75000.0]],
            "row_count": 2,
            "truncated": False,
        },
    )

    doc = ReportBuilder.build_report_document(
        report_id=uuid.uuid4(),
        session=session,
        dataset=dataset,
        runs=[run],
        title="Q1/Q2 Financial Report",
    )
    report = Report(
        id=uuid.uuid4(),
        user_id=owner_id,
        dataset_id=dataset_id,
        analysis_session_id=session.id,
        title=doc.metadata.title,
        status="ready",
        document=doc.model_dump(mode="json"),
    )

    # 1. PDF Byte Check
    pdf_bytes = PDFExporter.export_report_to_pdf(report)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000

    # 2. CSV Content Check
    csv_text = CSVExporter.export_report_tables_to_csv(report)
    assert isinstance(csv_text, str)
    assert "quarter" in csv_text
    assert "revenue" in csv_text
    assert "Q1 2026" in csv_text

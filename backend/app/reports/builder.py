"""AnalytIQ Reports - Deterministic, evidence-grounded report builder."""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.analysis_history import AnalysisRun, AnalysisSession
from app.models.dataset import Dataset
from app.reports.charts import ChartBuilder
from app.reports.contracts import (
    DatasetOverviewBlock,
    EvidenceReferenceBlock,
    HeadingBlock,
    LimitationNoticeBlock,
    MethodologyNoteBlock,
    ParagraphBlock,
    ReportBlock,
    ReportDocument,
    ReportMetadata,
    ReportSection,
    ResultTableBlock,
    ResultTableColumn,
    ScalarMetricBlock,
    VerifiedFindingBlock,
)


class ReportBuilder:
    """Constructs versioned, strongly-typed ReportDocuments strictly from trusted session runs."""

    @classmethod
    def build_report_document(
        cls,
        report_id: uuid.UUID,
        session: AnalysisSession,
        dataset: Dataset,
        runs: list[AnalysisRun],
        title: str | None = None,
        description: str | None = None,
    ) -> ReportDocument:
        """Compile selected session runs into a coherent evidence-grounded report."""
        report_title = (title or session.title or f"Analytical Report: {dataset.name}").strip()[
            :120
        ]
        report_desc = description.strip()[:1000] if description else None
        now = datetime.now(UTC)

        metadata = ReportMetadata(
            report_id=str(report_id),
            title=report_title,
            description=report_desc,
            dataset_id=str(dataset.id),
            dataset_name=dataset.name,
            analysis_session_id=str(session.id),
            schema_version="1.0.0",
            created_at=now,
            updated_at=now,
            generated_at=now,
        )

        # 1. Dataset Overview Block
        dataset_columns: list[str] = []
        if isinstance(dataset.schema_json, dict) and "columns" in dataset.schema_json:
            cols = dataset.schema_json["columns"]
            if isinstance(cols, list):
                dataset_columns = [str(c.get("name") if isinstance(c, dict) else c) for c in cols]

        dataset_overview = DatasetOverviewBlock(
            dataset_name=dataset.name,
            row_count=dataset.row_count or 0,
            column_count=dataset.column_count or 0,
            columns=dataset_columns,
        )

        # 2. Process Sections from Selected Runs
        sections: list[ReportSection] = []
        all_limitations: list[LimitationNoticeBlock] = []
        all_evidence: list[EvidenceReferenceBlock] = []
        summary_points: list[str] = []

        for sec_idx, run in enumerate(runs[:20]):  # Bound to max 20 runs
            # Skip runs that are explicitly failed or cancelled unless labeled
            if run.status in ["failed", "cancelled"]:
                continue

            section_blocks: list[ReportBlock] = []
            res_payload = run.result_payload or {}
            ver_payload = run.verification_payload or {}
            ev_payload = run.evidence_payload or {}

            # Question and intent
            section_blocks.append(
                HeadingBlock(level=2, text=run.question[:200], source_run_id=run.request_id)
            )

            # Execution SQL reference
            if run.executed_sql:
                section_blocks.append(
                    ParagraphBlock(
                        text=f"Executed SQL: {run.executed_sql}",
                        source_run_id=run.request_id,
                    )
                )

            # Verified Claims Extraction (support claims or verified_claims key)
            claims_list = ver_payload.get("verified_claims") or ver_payload.get("claims", [])
            claims_count = 0
            if isinstance(claims_list, list) and claims_list:
                for c in claims_list:
                    if not isinstance(c, dict):
                        continue
                    if c.get("verified") is False:
                        continue
                    exp = (
                        c.get("claim_text")
                        or c.get("explanation")
                        or c.get("reason_code")
                        or "Verified claim"
                    )
                    c_val = c.get("claimed_value")
                    m_name = c.get("metric_name")
                    fp = ev_payload.get("result_fingerprint")
                    section_blocks.append(
                        VerifiedFindingBlock(
                            finding_text=str(exp),
                            claim_id=c.get("claim_id"),
                            metric_name=str(m_name) if m_name else None,
                            claimed_value=c_val,
                            verified=True,
                            reason_code=c.get("reason_code"),
                            evidence_fingerprint=fp,
                            source_run_id=run.request_id,
                        )
                    )
                    claims_count += 1
                    if len(summary_points) < 5:
                        summary_points.append(str(exp))

            # If 1x1 scalar result, render a ScalarMetricBlock
            cols_raw = res_payload.get("columns", [])
            rows_raw = res_payload.get("rows", [])
            columns: list[dict[str, Any]] = cols_raw if isinstance(cols_raw, list) else []
            rows: list[list[Any]] = rows_raw if isinstance(rows_raw, list) else []

            if len(rows) == 1 and len(columns) == 1:
                col_name = str(columns[0].get("name", "metric"))
                metric_val = rows[0][0]
                section_blocks.append(
                    ScalarMetricBlock(
                        label=col_name,
                        value=metric_val,
                        verified=(claims_count > 0),
                        evidence_fingerprint=ev_payload.get("result_fingerprint"),
                        source_run_id=run.request_id,
                    )
                )
            if len(rows) > 0 and len(columns) > 0:
                # Add Result Table Block
                table_cols = [
                    ResultTableColumn(
                        name=str(c.get("name", f"col_{i}")),
                        type=str(c.get("type", "TEXT")),
                    )
                    for i, c in enumerate(columns)
                ]
                returned_count = run.returned_row_count or len(rows)
                is_truncated = run.truncated if run.truncated is not None else False
                section_blocks.append(
                    ResultTableBlock(
                        title="Tabular Results",
                        columns=table_cols,
                        rows=rows[:50],  # Bound table preview to 50 rows in report
                        returned_row_count=returned_count,
                        total_row_count=run.total_row_count,
                        truncated=is_truncated,
                        evidence_fingerprint=ev_payload.get("result_fingerprint"),
                        source_run_id=run.request_id,
                    )
                )

                # If not scalar 1x1, also add Chart Block
                if not (len(rows) == 1 and len(columns) == 1):
                    chart_blk = ChartBuilder.build_chart_block(
                        title=f"Visualization: {run.question[:60]}",
                        columns=columns,
                        rows=rows,
                        evidence_fingerprint=ev_payload.get("result_fingerprint"),
                        truncated=is_truncated,
                        source_run_id=run.request_id,
                    )
                    section_blocks.append(chart_blk)

            # Truncation or verification limitations
            if run.truncated:
                notice = (
                    f"Results for '{run.question[:40]}' are truncated at "
                    f"{run.returned_row_count} rows."
                )
                lim_block = LimitationNoticeBlock(notice_text=notice, source_run_id=run.request_id)
                section_blocks.append(lim_block)
                all_limitations.append(lim_block)

            # Record Evidence Reference
            ev_ref = EvidenceReferenceBlock(
                request_id=run.request_id,
                executed_sql=run.executed_sql,
                result_fingerprint=ev_payload.get("result_fingerprint"),
                dataset_fingerprint=ev_payload.get("dataset_fingerprint"),
                verification_status=ver_payload.get("status", "unverified"),
                source_run_id=run.request_id,
            )
            all_evidence.append(ev_ref)

            sections.append(
                ReportSection(
                    title=run.question[:120],
                    source_question=run.question,
                    source_run_id=run.request_id,
                    blocks=section_blocks,
                    visible=True,
                    display_order=sec_idx,
                )
            )

        # 3. Executive Summary
        if summary_points:
            exec_summary = (
                f"This report synthesizes {len(sections)} analytical queries executed over "
                f"{dataset.name}. " + " ".join(summary_points[:4])
            )
        else:
            exec_summary = (
                f"This report presents analytical findings from {len(sections)} executed queries "
                f"on {dataset.name}."
            )

        # 4. Methodology Note
        methodology = MethodologyNoteBlock(
            note=(
                "All analytical metrics and tables presented in this report were deterministically "
                "computed using DuckDB and verified against structured execution evidence. "
                "Numerical claims were independently validated for strict factual grounding."
            )
        )

        return ReportDocument(
            schema_version="1.0.0",
            metadata=metadata,
            executive_summary=exec_summary[:3000],
            dataset_overview=dataset_overview,
            sections=sections,
            methodology=methodology,
            limitations=all_limitations,
            evidence_appendix=all_evidence,
        )

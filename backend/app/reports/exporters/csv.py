"""AnalytIQ Reports - Deterministic CSV export service with formula injection protection."""

import csv
import io
from typing import Any

from app.models.report import Report
from app.reports.contracts import ReportDocument, ResultTableBlock


class CSVExporter:
    """Exports structured tabular result data to CSV with security guarantees."""

    FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")

    @classmethod
    def sanitize_cell_value(cls, val: Any) -> Any:
        """Sanitize text cells starting with spreadsheet formula triggers."""
        if val is None:
            return ""
        if isinstance(val, (int, float, bool)):
            return val
        s_val = str(val)
        # Protect against formula injection if first char is a formula trigger
        if s_val.startswith(cls.FORMULA_TRIGGERS):
            # If it's a valid negative number, preserve it
            try:
                float(s_val)
                return s_val
            except ValueError:
                return f"'{s_val}"
        return s_val

    @classmethod
    def export_report_tables_to_csv(cls, report: Report) -> str:
        """Export all tabular results from a report document into a clean, formatted CSV."""
        doc = ReportDocument.model_validate(report.document)
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Write Report Header
        writer.writerow(["# AnalytIQ Analytical Report Export"])
        writer.writerow(["# Title", doc.metadata.title])
        writer.writerow(["# Dataset", doc.metadata.dataset_name])
        writer.writerow(["# Generated", doc.metadata.generated_at.isoformat()])
        writer.writerow([])

        # Collect table blocks across visible sections
        table_count = 0
        for sec in doc.sections:
            if not sec.visible:
                continue
            for blk in sec.blocks:
                if isinstance(blk, ResultTableBlock):
                    table_count += 1
                    writer.writerow([f"## Section: {sec.title}"])
                    if blk.truncated:
                        writer.writerow(
                            [f"# Notice: Results truncated at {blk.returned_row_count} rows"]
                        )

                    # Column headers
                    headers = [c.name for c in blk.columns]
                    writer.writerow(headers)

                    # Data rows
                    for r in blk.rows:
                        sanitized_row = [cls.sanitize_cell_value(cell) for cell in r]
                        writer.writerow(sanitized_row)

                    writer.writerow([])  # Spacing between tables

        if table_count == 0:
            writer.writerow(["No tabular data available in this report."])

        return output.getvalue()

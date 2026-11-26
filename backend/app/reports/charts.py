"""AnalytIQ Reports - Deterministic, evidence-grounded chart specification builder."""

from typing import Any

from app.reports.contracts import ChartBlock, ChartSeriesSpec, ChartSpec, ChartType


class ChartBuilder:
    """Builds typed chart specifications strictly grounded in actual execution rows."""

    @staticmethod
    def recommend_chart_type(
        columns: list[dict[str, Any]],
        rows: list[list[Any]],
        intent: str = "aggregation",
    ) -> ChartType:
        """Deterministically recommend suitable visualization from computed result dimensions."""
        col_count = len(columns)
        row_count = len(rows)

        # 1x1 scalar result
        if row_count == 1 and col_count == 1:
            return ChartType.KPI_CARD

        # 2 columns (e.g. Category + Numeric Metric, or Time series)
        if col_count == 2:
            dim_type = str(columns[0].get("type", "")).upper()
            dim_name = str(columns[0].get("name", "")).lower()
            # If temporal by type or name, line chart
            if any(t in dim_type for t in ["DATE", "TIME", "TIMESTAMP", "YEAR"]) or any(
                n in dim_name
                for n in ["date", "time", "timestamp", "year", "month", "quarter", "day"]
            ):
                return ChartType.LINE
            # Scatter if both continuous/numeric metrics
            num_types = ["INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL"]
            metric_type = str(columns[1].get("type", "")).upper()
            if any(t in dim_type for t in num_types) and any(t in metric_type for t in num_types):
                # If neither is named id or key, scatter
                if not any(k in dim_name for k in ["id", "key", "pclass"]):
                    return ChartType.SCATTER
            return ChartType.BAR

        # Single row multiple columns
        if row_count == 1 and col_count > 1:
            return ChartType.BAR

        # Multi-column or complex: table
        return ChartType.TABLE

    @classmethod
    def build_chart_block(
        cls,
        title: str,
        columns: list[dict[str, Any]],
        rows: list[list[Any]],
        preferred_type: ChartType | None = None,
        evidence_fingerprint: str | None = None,
        truncated: bool = False,
        source_run_id: str | None = None,
    ) -> ChartBlock:
        """Construct a validated ChartBlock from computed tabular rows."""
        chart_type = preferred_type or cls.recommend_chart_type(columns, rows)
        col_names = [str(c.get("name", f"col_{i}")) for i, c in enumerate(columns)]

        data_points: list[dict[str, Any]] = []
        for r in rows[:200]:  # Bound data points to 200
            row_dict: dict[str, Any] = {}
            for i, name in enumerate(col_names):
                val = r[i] if i < len(r) else None
                row_dict[name] = val
            data_points.append(row_dict)

        x_key = col_names[0] if col_names else None
        y_key = col_names[1] if len(col_names) > 1 else None

        series: list[ChartSeriesSpec] = []
        if len(col_names) > 1:
            for c_name in col_names[1:]:
                series.append(ChartSeriesSpec(data_key=c_name, name=c_name))
        elif len(col_names) == 1:
            series.append(ChartSeriesSpec(data_key=col_names[0], name=col_names[0]))

        spec = ChartSpec(
            chart_type=chart_type,
            title=title,
            x_axis_key=x_key,
            y_axis_key=y_key,
            series=series,
            data=data_points,
            truncated=truncated,
            evidence_fingerprint=evidence_fingerprint,
        )

        return ChartBlock(
            spec=spec,
            source_run_id=source_run_id,
        )

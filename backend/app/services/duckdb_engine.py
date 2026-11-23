"""AnalytIQ DuckDB Engine - Deterministic analytical queries, preview, and profiling."""

import logging
import math
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
from app.core.config import get_settings
from app.services.storage import StorageSecurityError, storage_service

logger = logging.getLogger(__name__)


def sanitize_json_value(val: Any) -> Any:
    """Ensure all extracted database values are strictly JSON compliant."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(val, bytes):
        return val.hex()
    return val


def escape_duckdb_path(path: Path) -> str:
    """Safely escape single quotes in a file path for DuckDB string literals."""
    return str(path.resolve()).replace("'", "''")


class DuckDBEngine:
    """Executes deterministic analytical queries against normalized Parquet files."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a fresh in-memory connection with configured memory, thread, and safety limits."""
        con = duckdb.connect(database=":memory:")
        con.execute(f"SET memory_limit = '{self._settings.duckdb_memory_limit}'")
        con.execute("SET threads = 2")
        con.execute("SET autoinstall_known_extensions = false")
        con.execute("SET autoload_known_extensions = false")
        return con

    def _validate_parquet_file(self, parquet_path: Path) -> Path:
        """Verify the Parquet file exists and resides within the approved storage root."""
        resolved = parquet_path.resolve()
        try:
            resolved.relative_to(storage_service.root_path)
        except ValueError as err:
            msg = f"Access denied: '{parquet_path}' is outside storage root."
            raise StorageSecurityError(msg) from err

        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"Normalized Parquet file not found: {parquet_path}")
        return resolved

    def get_preview(
        self,
        parquet_path: Path,
        offset: int = 0,
        limit: int = 25,
        schema_columns: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Fetch a paginated row preview with column metadata and inferred logical types."""
        safe_path = self._validate_parquet_file(parquet_path)
        path_str = escape_duckdb_path(safe_path)

        clamped_limit = min(max(1, limit), 100)
        clamped_offset = max(0, offset)

        con = self._get_connection()
        try:
            count_sql = f"SELECT COUNT(*) FROM read_parquet('{path_str}')"  # noqa: S608
            total_rows = con.execute(count_sql).fetchone()[0]  # type: ignore[index]

            desc_sql = f"DESCRIBE SELECT * FROM read_parquet('{path_str}')"  # noqa: S608
            desc_rows = con.execute(desc_sql).fetchall()

            logical_type_map = {
                c["name"]: c.get("logical_type") for c in (schema_columns or []) if "name" in c
            }
            columns = [
                {
                    "name": r[0],
                    "duckdb_type": r[1],
                    "logical_type": logical_type_map.get(r[0]),
                }
                for r in desc_rows
            ]

            query = (
                f"SELECT * FROM read_parquet('{path_str}') "  # noqa: S608
                f"LIMIT {clamped_limit} OFFSET {clamped_offset}"
            )
            raw_data = con.execute(query).fetchall()

            rows: list[dict[str, Any]] = []
            for raw_row in raw_data:
                row_dict: dict[str, Any] = {}
                for idx, col_info in enumerate(columns):
                    col_name = col_info["name"]
                    row_dict[col_name] = sanitize_json_value(raw_row[idx])
                rows.append(row_dict)

            return {
                "columns": columns,
                "rows": rows,
                "total_rows": total_rows,
                "offset": clamped_offset,
                "limit": clamped_limit,
            }
        finally:
            con.close()

    def compute_profile_and_quality(
        self,
        parquet_path: Path,
        schema_columns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute comprehensive column statistics and data quality indicators."""
        safe_path = self._validate_parquet_file(parquet_path)
        path_str = escape_duckdb_path(safe_path)

        con = self._get_connection()
        try:
            count_sql = f"SELECT COUNT(*) FROM read_parquet('{path_str}')"  # noqa: S608
            total_rows: int = con.execute(count_sql).fetchone()[0]  # type: ignore[index]
            total_cols = len(schema_columns)

            # Compute duplicate rows: total rows minus distinct rows
            dup_query = (
                f"SELECT (SELECT COUNT(*) FROM read_parquet('{path_str}')) - "  # noqa: S608
                f"(SELECT COUNT(*) FROM (SELECT DISTINCT * FROM read_parquet('{path_str}')))"
            )
            duplicate_rows: int = con.execute(dup_query).fetchone()[0]  # type: ignore[index]

            column_profiles: list[dict[str, Any]] = []
            missing_cells_total = 0
            columns_with_missing = 0
            all_null_columns: list[str] = []
            constant_columns: list[str] = []

            for col_info in schema_columns:
                col_name = col_info["name"]
                col_type = col_info["logical_type"]
                # Quote column name safely for SQL identifiers
                quoted_col = '"' + col_name.replace('"', '""') + '"'

                stats_query = (
                    f"SELECT COUNT(*) - COUNT({quoted_col}) AS null_count, "  # noqa: S608
                    f"COUNT(DISTINCT {quoted_col}) AS distinct_count "
                    f"FROM read_parquet('{path_str}')"
                )
                null_cnt, dist_cnt = con.execute(stats_query).fetchone()  # type: ignore[misc]

                null_percentage = (
                    round((null_cnt / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
                )
                missing_cells_total += null_cnt

                if null_cnt > 0:
                    columns_with_missing += 1
                if null_cnt == total_rows:
                    all_null_columns.append(col_name)
                elif dist_cnt == 1 and null_cnt == 0:
                    constant_columns.append(col_name)

                profile_entry: dict[str, Any] = {
                    "name": col_name,
                    "logical_type": col_type,
                    "null_count": null_cnt,
                    "null_percentage": null_percentage,
                    "distinct_count": dist_cnt,
                    "min": None,
                    "max": None,
                    "mean": None,
                    "top_values": [],
                }

                # Numeric metrics
                if col_type in {"integer", "float"}:
                    num_query = (
                        f"SELECT MIN({quoted_col}), MAX({quoted_col}), AVG({quoted_col}) "  # noqa: S608
                        f"FROM read_parquet('{path_str}') WHERE {quoted_col} IS NOT NULL"
                    )
                    min_val, max_val, avg_val = con.execute(num_query).fetchone()  # type: ignore[misc]
                    profile_entry["min"] = sanitize_json_value(min_val)
                    profile_entry["max"] = sanitize_json_value(max_val)
                    profile_entry["mean"] = round(avg_val, 4) if avg_val is not None else None

                    # Deterministic distinction for low-cardinality discrete integers
                    # (e.g. Survived, Pclass)
                    if col_type == "integer" and 0 < dist_cnt <= 10:
                        top_query = (
                            f"SELECT {quoted_col}, COUNT(*) AS cnt "  # noqa: S608
                            f"FROM read_parquet('{path_str}') "
                            f"WHERE {quoted_col} IS NOT NULL "
                            f"GROUP BY {quoted_col} "
                            f"ORDER BY cnt DESC, {quoted_col} ASC"
                        )
                        top_rows = con.execute(top_query).fetchall()
                        profile_entry["top_values"] = [
                            {"value": str(r[0]), "count": r[1]} for r in top_rows
                        ]
                        profile_entry["is_discrete"] = True

                # Date / Timestamp metrics
                elif col_type in {"date", "timestamp"}:
                    dt_query = (
                        f"SELECT MIN({quoted_col}), MAX({quoted_col}) "  # noqa: S608
                        f"FROM read_parquet('{path_str}') WHERE {quoted_col} IS NOT NULL"
                    )
                    min_dt, max_dt = con.execute(dt_query).fetchone()  # type: ignore[misc]
                    profile_entry["min"] = sanitize_json_value(min_dt)
                    profile_entry["max"] = sanitize_json_value(max_dt)

                # Categorical / String top values
                elif col_type in {"string", "boolean"}:
                    # Deterministic high-cardinality check (>=90% unique in >=20 rows)
                    is_high_cardinality = (
                        col_type == "string" and total_rows >= 20 and (dist_cnt / total_rows) >= 0.9
                    )
                    if is_high_cardinality:
                        profile_entry["is_high_cardinality"] = True

                    top_query = (
                        f"SELECT {quoted_col}, COUNT(*) AS cnt "  # noqa: S608
                        f"FROM read_parquet('{path_str}') "
                        f"WHERE {quoted_col} IS NOT NULL "
                        f"GROUP BY {quoted_col} "
                        f"ORDER BY cnt DESC, {quoted_col} ASC "
                        f"LIMIT 5"
                    )
                    top_rows = con.execute(top_query).fetchall()
                    # For predominantly unique strings with frequency 1,
                    # avoid presenting arbitrary values as top categories
                    if is_high_cardinality and top_rows and top_rows[0][1] == 1:
                        profile_entry["top_values"] = []
                    else:
                        profile_entry["top_values"] = [
                            {"value": str(r[0]), "count": r[1]} for r in top_rows
                        ]

                column_profiles.append(profile_entry)

            # Generate verified quality findings with natural, grammatically correct text
            quality_findings: list[dict[str, Any]] = []

            if duplicate_rows > 0:
                row_word = "row" if duplicate_rows == 1 else "rows"
                msg = f"{duplicate_rows} duplicate {row_word} detected across dataset."
                quality_findings.append(
                    {
                        "type": "duplicate_rows",
                        "severity": "warning",
                        "message": msg,
                    }
                )

            if columns_with_missing > 0:
                col_word = "column" if columns_with_missing == 1 else "columns"
                cell_word = "cell" if missing_cells_total == 1 else "cells"
                verb = "contains" if columns_with_missing == 1 else "contain"
                quality_findings.append(
                    {
                        "type": "missing_values",
                        "severity": "warning",
                        "message": (
                            f"{columns_with_missing} {col_word} {verb} missing values, "
                            f"affecting {missing_cells_total} {cell_word}."
                        ),
                    }
                )

            for all_null_col in all_null_columns:
                quality_findings.append(
                    {
                        "type": "all_null_column",
                        "severity": "warning",
                        "message": f"Column '{all_null_col}' contains 100% missing values.",
                    }
                )

            for const_col in constant_columns:
                msg = f"Column '{const_col}' contains a single constant value across all rows."
                quality_findings.append(
                    {
                        "type": "constant_column",
                        "severity": "info",
                        "message": msg,
                    }
                )

            if not quality_findings:
                msg = "No duplicate rows or missing values detected. Dataset structure is clean."
                quality_findings.append(
                    {
                        "type": "clean_dataset",
                        "severity": "info",
                        "message": msg,
                    }
                )

            # Prioritized per-column missing values breakdown (sorted descending by null percentage)
            columns_breakdown = [
                {
                    "name": p["name"],
                    "logical_type": p["logical_type"],
                    "null_count": p["null_count"],
                    "null_percentage": p["null_percentage"],
                    "distinct_count": p["distinct_count"],
                }
                for p in column_profiles
                if p["null_count"] > 0
            ]
            columns_breakdown.sort(key=lambda x: x["null_percentage"], reverse=True)

            total_cells = total_rows * total_cols
            missing_percentage = (
                round((missing_cells_total / total_cells) * 100.0, 2) if total_cells > 0 else 0.0
            )

            summary = {
                "total_rows": total_rows,
                "total_columns": total_cols,
                "duplicate_rows": duplicate_rows,
                "missing_cells": missing_cells_total,
                "missing_percentage": missing_percentage,
                "columns_with_missing": columns_with_missing,
                "all_null_columns_count": len(all_null_columns),
                "constant_columns_count": len(constant_columns),
            }

            return {
                "summary": summary,
                "columns": column_profiles,
                "quality_findings": quality_findings,
                "columns_breakdown": columns_breakdown,
            }
        finally:
            con.close()


duckdb_engine = DuckDBEngine()

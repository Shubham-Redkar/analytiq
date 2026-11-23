"""AnalytIQ Dataset Parser - Deterministic CSV and XLSX normalization to Parquet."""

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
from app.core.config import get_settings
from app.services.schema import (
    infer_value_type,
    map_logical_to_duckdb_type,
    resolve_column_type,
)

logger = logging.getLogger(__name__)


class ParseValidationError(Exception):
    """Raised when file contents violate structure or limits."""


def detect_csv_delimiter(sample_text: str) -> str:
    """Detect delimiter among standard candidates (comma, tab, semicolon, pipe)."""
    candidates = [",", "\t", ";", "|"]
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample_text, delimiters=",;\t|")
        if dialect.delimiter in candidates:
            return dialect.delimiter
    except Exception as exc:
        logger.debug("Sniffer failed to detect delimiter: %s", exc)

    # Fallback frequency heuristic
    counts = {c: sample_text.count(c) for c in candidates}
    best = max(counts, key=counts.get)  # type: ignore[arg-type]
    return best if counts[best] > 0 else ","


def validate_headers(headers: list[str], max_columns: int) -> list[str]:
    """Validate header row for presence, uniqueness, non-emptiness, and bounds."""
    if not headers or all(not h.strip() for h in headers):
        raise ParseValidationError("Dataset header row is empty or missing.")

    cleaned_headers = [h.strip() for h in headers]

    for idx, h in enumerate(cleaned_headers, start=1):
        if not h:
            raise ParseValidationError(f"Column {idx} has an empty header name.")

    if len(cleaned_headers) > max_columns:
        raise ParseValidationError(
            f"Dataset has {len(cleaned_headers)} columns, exceeding maximum limit of {max_columns}."
        )

    # Check for duplicate headers
    seen: set[str] = set()
    for h in cleaned_headers:
        if h in seen:
            raise ParseValidationError(
                f"Duplicate column header detected: '{h}'. All headers must be unique."
            )
        seen.add(h)

    return cleaned_headers


def build_pyarrow_array(values: list[Any], logical_type: str) -> pa.Array:
    """Build a strongly typed PyArrow array for normalized values."""
    if logical_type == "integer":
        int_vals: list[int | None] = []
        for v in values:
            if v is None or v == "":
                int_vals.append(None)
            else:
                try:
                    int_vals.append(int(v))
                except (ValueError, TypeError):
                    int_vals.append(None)
        return pa.array(int_vals, type=pa.int64())

    if logical_type == "float":
        float_vals: list[float | None] = []
        for v in values:
            if v is None or v == "":
                float_vals.append(None)
            else:
                try:
                    float_vals.append(float(v))
                except (ValueError, TypeError):
                    float_vals.append(None)
        return pa.array(float_vals, type=pa.float64())

    if logical_type == "boolean":
        bool_vals: list[bool | None] = []
        for v in values:
            if v is None or v == "":
                bool_vals.append(None)
            elif isinstance(v, bool):
                bool_vals.append(v)
            else:
                sv = str(v).strip().lower()
                if sv in {"true", "1", "yes", "t"}:
                    bool_vals.append(True)
                elif sv in {"false", "0", "no", "f"}:
                    bool_vals.append(False)
                else:
                    bool_vals.append(None)
        return pa.array(bool_vals, type=pa.bool_())

    if logical_type == "date":
        date_vals: list[date | None] = []
        for v in values:
            if v is None or v == "":
                date_vals.append(None)
            elif isinstance(v, date):
                date_vals.append(v)
            else:
                try:
                    date_vals.append(date.fromisoformat(str(v).strip().replace("/", "-")))
                except ValueError:
                    date_vals.append(None)
        return pa.array(date_vals, type=pa.date32())

    if logical_type == "timestamp":
        ts_vals: list[datetime | None] = []
        for v in values:
            if v is None or v == "":
                ts_vals.append(None)
            elif isinstance(v, datetime):
                ts_vals.append(v)
            else:
                try:
                    ts_vals.append(datetime.fromisoformat(str(v).strip().replace("/", "-")))
                except ValueError:
                    ts_vals.append(None)
        return pa.array(ts_vals, type=pa.timestamp("us"))

    # Default to string
    str_vals = [None if (v is None or v == "") else str(v) for v in values]
    return pa.array(str_vals, type=pa.string())


class DatasetParser:
    """Parses and normalizes CSV/XLSX datasets to standard Parquet files."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def parse_and_convert(
        self,
        source_path: Path,
        parquet_path: Path,
        file_format: str,
    ) -> dict[str, Any]:
        """Normalize source dataset to Parquet and return schema metadata."""
        if file_format.upper() == "CSV":
            return self._parse_csv(source_path, parquet_path)
        if file_format.upper() == "XLSX":
            return self._parse_xlsx(source_path, parquet_path)
        raise ParseValidationError(f"Unsupported format: {file_format}")

    def _parse_csv(self, source_path: Path, parquet_path: Path) -> dict[str, Any]:
        """Parse CSV file, enforce limits, infer schema, and write Parquet."""
        max_rows = self._settings.max_parsed_rows
        max_cols = self._settings.max_parsed_columns

        # Read sample bytes to detect delimiter and encoding
        with open(source_path, "rb") as bf:
            sample_bytes = bf.read(65536)

        if not sample_bytes:
            raise ParseValidationError("CSV file is completely empty.")

        # Decode with utf-8-sig to cleanly strip BOM if present
        try:
            sample_str = sample_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as err:
            raise ParseValidationError("CSV file is not valid UTF-8.") from err

        delimiter = detect_csv_delimiter(sample_str)

        columns_data: dict[str, list[Any]] = {}
        observed_types: dict[str, set[str]] = {}
        headers: list[str] = []
        row_count = 0

        with open(source_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter=delimiter)
            try:
                raw_headers = next(reader, None)
            except csv.Error as err:
                raise ParseValidationError(f"Malformed CSV: {err}") from err

            if raw_headers is None:
                raise ParseValidationError("CSV file has no header row.")

            headers = validate_headers(raw_headers, max_cols)
            for h in headers:
                columns_data[h] = []
                observed_types[h] = set()

            for row_idx, row in enumerate(reader, start=1):
                if row_idx > max_rows:
                    raise ParseValidationError(
                        f"Dataset row count exceeds maximum allowed limit of {max_rows} rows."
                    )
                # Pad or truncate row to header length
                padded_row = row + [""] * (len(headers) - len(row))
                for col_idx, h in enumerate(headers):
                    val = padded_row[col_idx].strip()
                    columns_data[h].append(val)
                    observed_types[h].add(infer_value_type(val))
                row_count += 1

        if row_count == 0:
            raise ParseValidationError("CSV dataset contains headers but zero data rows.")

        return self._write_parquet_and_build_schema(
            columns_data, observed_types, headers, row_count, parquet_path
        )

    def _parse_xlsx(self, source_path: Path, parquet_path: Path) -> dict[str, Any]:
        """Parse XLSX workbook, enforce limits, infer schema, and write Parquet."""
        max_rows = self._settings.max_parsed_rows
        max_cols = self._settings.max_parsed_columns

        try:
            # openpyxl read_only=True and data_only=True prevents formula execution and saves memory
            wb = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
        except Exception as err:
            raise ParseValidationError(f"Invalid or corrupted XLSX workbook: {err}") from err

        try:
            if not wb.worksheets:
                raise ParseValidationError("XLSX workbook contains no worksheets.")

            ws = wb.worksheets[0]
            row_iter = ws.iter_rows(values_only=True)

            raw_headers_tuple = next(row_iter, None)
            if raw_headers_tuple is None:
                raise ParseValidationError("XLSX worksheet is empty.")

            raw_headers = [str(cell) if cell is not None else "" for cell in raw_headers_tuple]
            # Strip trailing empty headers often present in Excel
            while raw_headers and not raw_headers[-1].strip():
                raw_headers.pop()

            headers = validate_headers(raw_headers, max_cols)

            columns_data: dict[str, list[Any]] = {h: [] for h in headers}
            observed_types: dict[str, set[str]] = {h: set() for h in headers}
            row_count = 0

            for row_tuple in row_iter:
                # Skip fully empty rows
                if all(cell is None or str(cell).strip() == "" for cell in row_tuple):
                    continue

                row_count += 1
                if row_count > max_rows:
                    raise ParseValidationError(
                        f"Dataset row count exceeds maximum allowed limit of {max_rows} rows."
                    )

                row_list = list(row_tuple)
                padded_row = row_list + [None] * (len(headers) - len(row_list))
                for col_idx, h in enumerate(headers):
                    val = padded_row[col_idx]
                    columns_data[h].append(val)
                    observed_types[h].add(infer_value_type(val))

            if row_count == 0:
                raise ParseValidationError("XLSX worksheet contains headers but zero data rows.")

            return self._write_parquet_and_build_schema(
                columns_data, observed_types, headers, row_count, parquet_path
            )
        finally:
            wb.close()

    def _write_parquet_and_build_schema(
        self,
        columns_data: dict[str, list[Any]],
        observed_types: dict[str, set[str]],
        headers: list[str],
        row_count: int,
        parquet_path: Path,
    ) -> dict[str, Any]:
        """Convert column data to PyArrow arrays, save to Parquet, and assemble schema."""
        arrow_arrays: list[pa.Array] = []
        schema_columns: list[dict[str, Any]] = []

        for h in headers:
            vals = columns_data[h]
            types_seen = observed_types[h]
            logical_type = resolve_column_type(types_seen)
            duckdb_type = map_logical_to_duckdb_type(logical_type)

            arr = build_pyarrow_array(vals, logical_type)
            arrow_arrays.append(arr)

            has_null = arr.null_count > 0
            schema_columns.append(
                {
                    "name": h,
                    "logical_type": logical_type,
                    "duckdb_type": duckdb_type,
                    "nullable": has_null,
                }
            )

        arrow_table = pa.Table.from_arrays(arrow_arrays, names=headers)
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(arrow_table, parquet_path, compression="SNAPPY")

        return {
            "columns": schema_columns,
            "row_count": row_count,
            "column_count": len(headers),
        }


dataset_parser = DatasetParser()

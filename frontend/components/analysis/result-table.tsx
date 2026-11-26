"use client";

import React, { useState, useMemo } from "react";
import type { AnalyticalResultColumn } from "../../lib/analysis-types";
import { ChevronLeft, ChevronRight, ArrowUpDown, Copy, Check } from "lucide-react";

interface ResultTableProps {
  columns: AnalyticalResultColumn[];
  rows: (string | number | boolean | null)[][];
  totalRowCount?: number | null;
  datasetRowCount?: number | null;
  truncated?: boolean;
  highlightCoordinates?: { row: number; colName: string } | null;
}

export function ResultTable({
  columns,
  rows,
  truncated = false,
  highlightCoordinates,
}: ResultTableProps) {
  const [pageSize, setPageSize] = useState<number>(10);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortAsc, setSortAsc] = useState<boolean>(true);
  const [copiedCell, setCopiedCell] = useState<string | null>(null);

  // Preserve original indices for evidence highlight tracking
  const indexedRows = useMemo(() => {
    return rows.map((r, originalIndex) => ({
      originalIndex,
      data: r,
    }));
  }, [rows]);

  const sortedRows = useMemo(() => {
    if (sortCol === null) return indexedRows;
    return [...indexedRows].sort((a, b) => {
      const valA = a.data[sortCol];
      const valB = b.data[sortCol];
      if (valA === null || valA === undefined) return sortAsc ? 1 : -1;
      if (valB === null || valB === undefined) return sortAsc ? -1 : 1;
      if (valA < valB) return sortAsc ? -1 : 1;
      if (valA > valB) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [indexedRows, sortCol, sortAsc]);

  const totalPages = Math.ceil(sortedRows.length / pageSize) || 1;
  const pagedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [sortedRows, currentPage, pageSize]);

  const handleSort = (colIdx: number) => {
    if (sortCol === colIdx) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(colIdx);
      setSortAsc(true);
    }
  };

  const copyValue = (val: unknown, id: string) => {
    navigator.clipboard.writeText(String(val ?? ""));
    setCopiedCell(id);
    setTimeout(() => setCopiedCell(null), 1500);
  };

  if (!rows || rows.length === 0) {
    return (
      <div className="p-4 text-center text-sm text-muted-foreground border rounded-lg bg-card/50">
        Query completed with 0 matching rows.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between text-[13px] text-muted-foreground gap-2">
        <div className="flex items-center gap-2">
          <span>
            Showing {Math.min((currentPage - 1) * pageSize + 1, sortedRows.length)}–
            {Math.min(currentPage * pageSize, sortedRows.length)} of {sortedRows.length} returned
            rows
          </span>
          {truncated && (
            <span className="text-amber-500 font-medium">(Result truncated at query limit)</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span>Rows per page:</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setCurrentPage(1);
            }}
            className="border border-input rounded-md px-2.5 py-1 bg-background text-foreground text-xs cursor-pointer shadow-2xs"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </div>

      <div className="border border-border rounded-xl overflow-x-auto bg-card shadow-2xs">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold text-xs uppercase tracking-wider">
              {columns.map((col, idx) => (
                <th
                  key={col.name}
                  onClick={() => handleSort(idx)}
                  className="px-3.5 py-2.5 cursor-pointer hover:bg-muted/70 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>{col.name}</span>
                    <ArrowUpDown className="h-3 w-3 opacity-60" />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pagedRows.map(({ originalIndex, data }) => (
              <tr
                key={originalIndex}
                className="border-b border-border/60 last:border-0 hover:bg-muted/30 transition"
              >
                {data.map((cell, colIdx) => {
                  const colName = columns[colIdx]?.name;
                  const isHighlighted =
                    highlightCoordinates &&
                    highlightCoordinates.row === originalIndex &&
                    highlightCoordinates.colName === colName;
                  const cellId = `${originalIndex}-${colIdx}`;

                  return (
                    <td
                      key={colIdx}
                      className={`px-3.5 py-2.5 font-mono text-sm whitespace-nowrap group relative ${
                        isHighlighted
                          ? "bg-amber-500/20 font-semibold ring-1 ring-amber-500/40 rounded-sm"
                          : ""
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span>
                          {cell === null ? (
                            <span className="text-muted-foreground italic text-xs">NULL</span>
                          ) : typeof cell === "number" ? (
                            cell.toLocaleString(undefined, { maximumFractionDigits: 4 })
                          ) : (
                            String(cell)
                          )}
                        </span>
                        <button
                          onClick={() => copyValue(cell, cellId)}
                          className="opacity-0 group-hover:opacity-100 p-1 hover:text-foreground text-muted-foreground transition rounded cursor-pointer"
                          title="Copy cell value"
                        >
                          {copiedCell === cellId ? (
                            <Check className="h-3 w-3 text-emerald-500" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
              disabled={currentPage === 1}
              className="p-1 rounded border hover:bg-muted disabled:opacity-40 transition"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
              disabled={currentPage === totalPages}
              className="p-1 rounded border hover:bg-muted disabled:opacity-40 transition"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

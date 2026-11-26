"use client";

import { Suspense, use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Database,
  FileSpreadsheet,
  FileText,
  Info,
  Layers,
  Search,
  Table as TableIcon,
  Trash2,
  X,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api, ApiError } from "@/lib/api";
import type {
  ColumnProfile,
  Dataset,
  DatasetPreviewResponse,
  DatasetProfileResponse,
  DatasetQualityResponse,
} from "@/lib/types";
import { Button } from "@/components/ui/button";

function getFriendlyTypeLabel(logicalType?: string, duckdbType?: string): string {
  const t = (logicalType || duckdbType || "").toLowerCase();
  if (t === "integer" || t.includes("int")) return "Integer";
  if (t === "float" || t.includes("double") || t.includes("decimal") || t.includes("real"))
    return "Decimal";
  if (t === "boolean" || t.includes("bool")) return "Boolean";
  if (t === "date") return "Date";
  if (t === "timestamp" || t.includes("time")) return "Date & Time";
  return "Text";
}

function isNumericColumn(logicalType?: string, duckdbType?: string): boolean {
  const t = (logicalType || duckdbType || "").toLowerCase();
  return (
    t === "integer" ||
    t === "float" ||
    t.includes("int") ||
    t.includes("double") ||
    t.includes("decimal") ||
    t.includes("real")
  );
}

export function DatasetDetailContent({ id }: { id: string }) {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<"preview" | "schema" | "profile" | "quality">("preview");
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Preview state
  const [preview, setPreview] = useState<DatasetPreviewResponse | null>(null);
  const [previewOffset, setPreviewOffset] = useState(0);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewLimit = 25;

  // Profile & Quality state
  const [profile, setProfile] = useState<DatasetProfileResponse | null>(null);
  const [quality, setQuality] = useState<DatasetQualityResponse | null>(null);

  // Profiling search & filter state
  const [columnSearch, setColumnSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // Deletion modal state
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Scroll hint dismiss state
  const [scrollHintDismissed, setScrollHintDismissed] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push(`/login?redirect=/datasets/${id}`);
    }
  }, [user, authLoading, router, id]);

  // Load core dataset metadata
  useEffect(() => {
    let ignore = false;
    async function fetchDatasetData() {
      if (!user) return;
      try {
        setLoading(true);
        setError(null);
        const data = await api.getDataset(id);
        if (!ignore) {
          setDataset(data);
        }
      } catch (err: unknown) {
        if (!ignore) {
          if (err instanceof ApiError && err.status === 404) {
            setError("Dataset not found or you do not have permission to access it.");
          } else if (err instanceof ApiError) {
            setError(err.message);
          } else {
            setError("Failed to load dataset details.");
          }
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    if (user) {
      void fetchDatasetData();
    }

    return () => {
      ignore = true;
    };
  }, [user, id]);

  // Load preview data when preview tab is active
  useEffect(() => {
    let ignore = false;
    async function loadPreview() {
      if (!user || activeTab !== "preview") return;
      try {
        setPreviewLoading(true);
        const res = await api.getDatasetPreview(id, previewOffset, previewLimit);
        if (!ignore) {
          setPreview(res);
        }
      } catch {
        // Preview error handled in UI
      } finally {
        if (!ignore) {
          setPreviewLoading(false);
        }
      }
    }

    if (user && activeTab === "preview") {
      void loadPreview();
    }

    return () => {
      ignore = true;
    };
  }, [user, id, activeTab, previewOffset]);

  // Load profile data when profile tab is active
  useEffect(() => {
    let ignore = false;
    async function loadProfile() {
      if (!user || activeTab !== "profile" || profile) return;
      try {
        const res = await api.getDatasetProfile(id);
        if (!ignore) {
          setProfile(res);
        }
      } catch {
        // Error handled in UI
      }
    }

    if (user && activeTab === "profile" && !profile) {
      void loadProfile();
    }

    return () => {
      ignore = true;
    };
  }, [user, id, activeTab, profile]);

  // Load quality findings when quality tab is active
  useEffect(() => {
    let ignore = false;
    async function loadQuality() {
      if (!user || activeTab !== "quality" || quality) return;
      try {
        const res = await api.getDatasetQuality(id);
        if (!ignore) {
          setQuality(res);
        }
      } catch {
        // Error handled in UI
      }
    }

    if (user && activeTab === "quality" && !quality) {
      void loadQuality();
    }

    return () => {
      ignore = true;
    };
  }, [user, id, activeTab, quality]);

  const handleDelete = async () => {
    try {
      setIsDeleting(true);
      setDeleteError(null);
      await api.deleteDataset(id);
      router.push("/datasets");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setDeleteError(err.message);
      } else {
        setDeleteError("Failed to delete dataset. Please try again.");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  if (authLoading || loading) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-6">
          <div className="h-8 w-40 animate-pulse rounded-lg bg-muted" />
          <div className="h-28 w-full animate-pulse rounded-2xl bg-muted" />
          <div className="h-96 w-full animate-pulse rounded-2xl bg-muted" />
        </div>
      </main>
    );
  }

  if (error || !dataset) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <Link
          href="/datasets"
          className="inline-flex items-center text-sm font-medium text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="mr-1.5 h-4 w-4" />
          Back to datasets
        </Link>
        <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-8 text-center max-w-lg mx-auto">
          <AlertCircle className="mx-auto h-10 w-10 text-destructive mb-3" />
          <h2 className="text-lg font-bold text-destructive">Dataset Unavailable</h2>
          <p className="mt-1 text-sm text-destructive/80">{error || "Unable to load dataset."}</p>
          <Link href="/datasets" className="mt-6 inline-block">
            <Button variant="outline" size="sm" className="cursor-pointer">
              Return to dataset list
            </Button>
          </Link>
        </div>
      </main>
    );
  }

  const columns = dataset.schema_json?.columns || [];

  // Filter columns for profiling tab
  const filteredColumns: ColumnProfile[] = (profile?.columns || []).filter((col) => {
    const matchesSearch = col.name.toLowerCase().includes(columnSearch.toLowerCase().trim());
    if (!matchesSearch) return false;
    if (typeFilter === "all") return true;
    if (typeFilter === "numeric") {
      return col.logical_type === "integer" || col.logical_type === "float";
    }
    if (typeFilter === "text") {
      return col.logical_type === "string";
    }
    if (typeFilter === "datetime") {
      return col.logical_type === "date" || col.logical_type === "timestamp";
    }
    if (typeFilter === "boolean") {
      return col.logical_type === "boolean";
    }
    return true;
  });

  // Calculate missing values summary safely from quality_summary or quality state
  const missingSummary = dataset.quality_summary || quality?.summary;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Navigation & Header */}
      <div className="mb-6">
        <Link
          href="/datasets"
          className="inline-flex items-center text-sm font-medium text-muted-foreground hover:text-foreground transition-colors mb-3"
        >
          <ArrowLeft className="mr-1.5 h-4 w-4" />
          Back to datasets
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/80 pb-6">
          <div className="flex items-start gap-3.5">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground shrink-0 mt-0.5">
              {dataset.file_format === "CSV" ? (
                <FileText className="h-6 w-6 text-primary" />
              ) : (
                <FileSpreadsheet className="h-6 w-6 text-emerald-600" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
                  {dataset.name}
                </h1>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-semibold ${
                    dataset.file_format === "CSV"
                      ? "bg-primary/10 text-primary"
                      : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  }`}
                >
                  {dataset.file_format}
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground">
                  {(dataset.file_size_bytes / 1024).toFixed(1)} KB
                </span>
              </div>
              <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
                Original file: <span className="font-mono text-foreground/80">{dataset.original_filename}</span> • Ingested on{" "}
                {new Date(dataset.created_at).toLocaleString()}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {dataset.status === "ready" && (
              <Link
                href={`/analysis?dataset_id=${dataset.id}`}
                className="inline-flex items-center justify-center rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition shadow-xs"
              >
                Analyze Dataset
              </Link>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDeleteModal(true)}
              className="cursor-pointer text-destructive hover:bg-destructive/10 hover:text-destructive"
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              Delete
            </Button>
          </div>
        </div>

        {/* Deletion incomplete alert banner */}
        {dataset.status === "deletion_failed" && (
          <div className="mt-4 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <div>
                <p className="font-semibold">Dataset deletion incomplete</p>
                <p className="text-xs text-destructive/90">
                  A previous attempt to remove storage files failed. You can safely retry permanent deletion.
                </p>
              </div>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowDeleteModal(true)}
              className="cursor-pointer shrink-0 font-medium"
            >
              Retry Deletion
            </Button>
          </div>
        )}
      </div>

      {/* Summary KPI Strip - Refinement A: Missing Values replaces internal storage details */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
          <p className="text-xs font-medium text-muted-foreground">Total Rows</p>
          <p className="mt-1 text-xl sm:text-2xl font-bold font-mono text-foreground">
            {dataset.row_count !== null ? dataset.row_count.toLocaleString() : "—"}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
          <p className="text-xs font-medium text-muted-foreground">Total Columns</p>
          <p className="mt-1 text-xl sm:text-2xl font-bold font-mono text-foreground">
            {dataset.column_count !== null ? dataset.column_count : "—"}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
          <p className="text-xs font-medium text-muted-foreground">Status</p>
          <div className="mt-1 flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                dataset.status === "ready"
                  ? "bg-emerald-500"
                  : dataset.status === "deleting"
                  ? "bg-amber-500"
                  : dataset.status === "deletion_failed"
                  ? "bg-destructive"
                  : "bg-muted-foreground"
              }`}
            />
            <p className="text-base sm:text-lg font-semibold capitalize text-foreground">
              {dataset.status === "deletion_failed" ? "Deletion Failed" : dataset.status}
            </p>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
          <p className="text-xs font-medium text-muted-foreground">Missing Values</p>
          <p className="mt-1 text-xl sm:text-2xl font-bold font-mono text-foreground">
            {missingSummary ? (
              <>
                {missingSummary.missing_cells.toLocaleString()}
                <span className="text-xs sm:text-sm font-normal text-muted-foreground ml-1.5">
                  ({missingSummary.missing_percentage}%)
                </span>
              </>
            ) : (
              <span className="text-sm sm:text-base font-normal text-muted-foreground">
                Not computed
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-border/80 mb-6">
        <nav className="flex space-x-6 text-sm font-semibold" aria-label="Dataset Exploration Tabs">
          <button
            onClick={() => setActiveTab("preview")}
            className={`pb-3.5 border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === "preview"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <TableIcon className="h-4 w-4" />
            Data Preview
          </button>
          <button
            onClick={() => setActiveTab("schema")}
            className={`pb-3.5 border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === "schema"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="h-4 w-4" />
            Schema Definition ({columns.length})
          </button>
          <button
            onClick={() => setActiveTab("profile")}
            className={`pb-3.5 border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === "profile"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Database className="h-4 w-4" />
            Column Profiling
          </button>
          <button
            onClick={() => setActiveTab("quality")}
            className={`pb-3.5 border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === "quality"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <CheckCircle2 className="h-4 w-4" />
            Data Quality
          </button>
        </nav>
      </div>

      {/* TAB 1: DATA PREVIEW - Refinement B: Sticky row-num, friendly types, numeric alignment, horizontal hint */}
      {activeTab === "preview" && (
        <div className="space-y-4">
          <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-xs">
            {previewLoading ? (
              <div className="p-8 space-y-3">
                <div className="h-8 w-full animate-pulse rounded bg-muted" />
                <div className="h-8 w-full animate-pulse rounded bg-muted" />
                <div className="h-8 w-full animate-pulse rounded bg-muted" />
                <div className="h-8 w-full animate-pulse rounded bg-muted" />
              </div>
            ) : preview && preview.rows.length > 0 ? (
              <div>
                {/* Horizontal scroll discoverability banner */}
                {preview.columns.length > 5 && !scrollHintDismissed && (
                  <div className="px-4 py-2 bg-muted/20 border-b border-border/60 flex items-center justify-between text-xs text-muted-foreground">
                    <span>Horizontal scroll enabled for wide dataset viewing</span>
                    <div className="flex items-center gap-3">
                      <span className="font-mono">{preview.columns.length} columns</span>
                      <button
                        onClick={() => setScrollHintDismissed(true)}
                        className="cursor-pointer hover:text-foreground p-0.5 rounded transition-colors"
                        aria-label="Dismiss scroll hint"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                )}

                <div className="overflow-x-auto max-h-[600px] relative">
                  <table className="w-full text-left border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-border/80 bg-muted/95 backdrop-blur-xs sticky top-0 z-10">
                        <th className="sticky left-0 bg-muted/95 backdrop-blur-xs z-20 px-4 py-3 font-mono text-xs text-muted-foreground w-12 text-center border-r border-border/80">
                          #
                        </th>
                        {preview.columns.map((col) => {
                          const isNumeric = isNumericColumn(col.logical_type, col.duckdb_type);
                          const displayType = getFriendlyTypeLabel(col.logical_type, col.duckdb_type);
                          return (
                            <th
                              key={col.name}
                              className={`px-4 py-3 font-semibold text-foreground whitespace-nowrap ${
                                isNumeric ? "text-right" : "text-left"
                              }`}
                            >
                              <div
                                className={`flex items-center gap-2 ${
                                  isNumeric ? "justify-end" : "justify-start"
                                }`}
                              >
                                <span>{col.name}</span>
                                <span className="text-[11px] font-sans font-normal text-muted-foreground px-1.5 py-0.5 rounded bg-muted border border-border/40">
                                  {displayType}
                                </span>
                              </div>
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {preview.rows.map((row, rowIdx) => (
                        <tr key={rowIdx} className="group hover:bg-muted/40 transition-colors">
                          <td className="sticky left-0 bg-card group-hover:bg-muted/40 transition-colors z-10 px-4 py-2.5 font-mono text-xs text-muted-foreground/70 text-center border-r border-border/80">
                            {previewOffset + rowIdx + 1}
                          </td>
                          {preview.columns.map((col) => {
                            const val = row[col.name];
                            const isNumeric = isNumericColumn(col.logical_type, col.duckdb_type);
                            return (
                              <td
                                key={col.name}
                                className={`px-4 py-2.5 whitespace-nowrap ${
                                  isNumeric ? "text-right" : "text-left"
                                }`}
                              >
                                {val === null || val === undefined ? (
                                  <span className="italic text-muted-foreground/60 text-xs font-mono">
                                    null
                                  </span>
                                ) : typeof val === "boolean" ? (
                                  <span className="font-mono text-xs font-semibold text-primary">
                                    {val ? "true" : "false"}
                                  </span>
                                ) : typeof val === "number" ? (
                                  <span className="font-mono text-foreground">
                                    {val.toLocaleString()}
                                  </span>
                                ) : (
                                  <span className="text-foreground">{String(val)}</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-muted-foreground">
                No rows available to preview.
              </div>
            )}
          </div>

          {/* Pagination bar */}
          {preview && preview.total_rows > 0 && (() => {
            const totalPages = Math.max(1, Math.ceil(preview.total_rows / previewLimit));
            const currentPage = Math.floor(previewOffset / previewLimit) + 1;
            const startRow = preview.rows.length === 0 ? 0 : previewOffset + 1;
            const endRow = previewOffset + preview.rows.length;

            return (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-2 text-sm text-muted-foreground">
                <div className="flex items-center gap-2 flex-wrap">
                  <span>
                    Showing rows {startRow.toLocaleString()}–{endRow.toLocaleString()} of{" "}
                    {preview.total_rows.toLocaleString()}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border/50">
                    Page {currentPage} of {totalPages}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={previewOffset === 0 || previewLoading}
                    onClick={() => setPreviewOffset(0)}
                    aria-label="First page"
                    className="cursor-pointer px-2 text-xs"
                  >
                    <ChevronsLeft className="h-4 w-4" />
                    <span className="sr-only sm:not-sr-only sm:ml-1">First</span>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={previewOffset === 0 || previewLoading}
                    onClick={() => setPreviewOffset((prev) => Math.max(0, prev - previewLimit))}
                    aria-label="Previous page"
                    className="cursor-pointer px-2.5 text-xs"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    <span className="sr-only sm:not-sr-only sm:ml-1">Previous</span>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={previewOffset + previewLimit >= preview.total_rows || previewLoading}
                    onClick={() => setPreviewOffset((prev) => prev + previewLimit)}
                    aria-label="Next page"
                    className="cursor-pointer px-2.5 text-xs"
                  >
                    <span className="sr-only sm:not-sr-only sm:mr-1">Next</span>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={previewOffset + previewLimit >= preview.total_rows || previewLoading}
                    onClick={() => setPreviewOffset((totalPages - 1) * previewLimit)}
                    aria-label="Last page"
                    className="cursor-pointer px-2 text-xs"
                  >
                    <span className="sr-only sm:not-sr-only sm:mr-1">Last</span>
                    <ChevronsRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* TAB 2: SCHEMA DEFINITION */}
      {activeTab === "schema" && (
        <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-border/80 bg-muted/30 text-xs font-semibold text-muted-foreground">
                  <th className="px-6 py-3.5">#</th>
                  <th className="px-6 py-3.5">Column Name</th>
                  <th className="px-6 py-3.5">Logical Type</th>
                  <th className="px-6 py-3.5">Engine Physical Type</th>
                  <th className="px-6 py-3.5">Nullable</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {columns.map((col, idx) => (
                  <tr key={col.name} className="hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4 font-mono text-xs text-muted-foreground">
                      {idx + 1}
                    </td>
                    <td className="px-6 py-4 font-semibold text-foreground font-mono">
                      {col.name}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary capitalize">
                        {col.logical_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-muted-foreground">
                      {col.duckdb_type}
                    </td>
                    <td className="px-6 py-4">
                      {col.nullable ? (
                        <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
                          Yes
                        </span>
                      ) : (
                        <span className="text-xs font-medium text-muted-foreground">
                          No
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: COLUMN PROFILING - Refinement C: Search, filter, discrete frequencies, high-cardinality clarity */}
      {activeTab === "profile" && (
        <div className="space-y-6">
          {profile ? (
            <>
              {/* Profiling Controls */}
              <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
                <div className="relative flex-1 max-w-sm">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    type="search"
                    placeholder="Search columns by name..."
                    aria-label="Search columns by name"
                    value={columnSearch}
                    onChange={(e) => setColumnSearch(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background pl-9 pr-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                  />
                </div>

                {/* Type Filter Buttons */}
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0" role="group" aria-label="Filter columns by type">
                  {[
                    { id: "all", label: "All" },
                    { id: "numeric", label: "Numeric" },
                    { id: "text", label: "Text" },
                    { id: "datetime", label: "Date/Time" },
                    { id: "boolean", label: "Boolean" },
                  ].map((filter) => (
                    <button
                      key={filter.id}
                      onClick={() => setTypeFilter(filter.id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer shrink-0 ${
                        typeFilter === filter.id
                          ? "bg-primary text-primary-foreground font-semibold"
                          : "bg-muted text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
              </div>

              {filteredColumns.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border/80 bg-muted/15 p-12 text-center">
                  <p className="text-sm font-medium text-foreground">No columns match your filter criteria.</p>
                  <p className="mt-1 text-xs text-muted-foreground">Try clearing your search query or selecting &quot;All&quot; types.</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setColumnSearch("");
                      setTypeFilter("all");
                    }}
                    className="mt-4 cursor-pointer"
                  >
                    Reset filters
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {filteredColumns.map((col) => (
                    <div
                      key={col.name}
                      className="rounded-2xl border border-border bg-card p-5 shadow-2xs flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between pb-3 border-b border-border/60">
                          <h4 className="font-bold text-foreground font-mono text-base truncate">
                            {col.name}
                          </h4>
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary capitalize">
                            {col.logical_type}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-4 py-4 text-xs sm:text-sm">
                          <div>
                            <span className="text-muted-foreground">Missing Values:</span>
                            <p className="font-semibold text-foreground mt-0.5 font-mono">
                              {col.null_count.toLocaleString()} ({col.null_percentage}%)
                            </p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Distinct Values:</span>
                            <p className="font-semibold text-foreground mt-0.5 font-mono">
                              {col.distinct_count.toLocaleString()}
                            </p>
                          </div>

                          {col.min !== null && (
                            <div>
                              <span className="text-muted-foreground">Minimum:</span>
                              <p className="font-semibold text-foreground mt-0.5 font-mono truncate">
                                {String(col.min)}
                              </p>
                            </div>
                          )}

                          {col.max !== null && (
                            <div>
                              <span className="text-muted-foreground">Maximum:</span>
                              <p className="font-semibold text-foreground mt-0.5 font-mono truncate">
                                {String(col.max)}
                              </p>
                            </div>
                          )}

                          {col.mean !== null && (
                            <div className="col-span-2 sm:col-span-1">
                              <span className="text-muted-foreground">
                                {col.is_discrete ? "Arithmetic Mean:" : "Average (Mean):"}
                              </span>
                              <p className="font-semibold text-foreground mt-0.5 font-mono">
                                {col.mean.toLocaleString()}
                              </p>
                            </div>
                          )}
                        </div>

                        {/* High Cardinality explanation for text */}
                        {col.is_high_cardinality && (
                          <div className="py-2.5 px-3 rounded-lg bg-muted/40 border border-border/40 text-xs text-muted-foreground mb-3">
                            <span className="font-medium text-foreground">High-cardinality text:</span>{" "}
                            {col.distinct_count.toLocaleString()} unique values. Values are mostly distinct and may represent identifiers or unstructured text.
                          </div>
                        )}

                        {/* Frequent Values / Discrete Categories */}
                        {col.top_values && col.top_values.length > 0 && (
                          <div className="pt-3 border-t border-border/60">
                            <span className="text-xs font-semibold text-muted-foreground">
                              {col.is_discrete ? "Descriptive Frequency Summary:" : "Top Frequent Values:"}
                            </span>
                            <div className="mt-2 space-y-1.5">
                              {col.top_values.map((item, idx) => (
                                <div
                                  key={idx}
                                  className="flex items-center justify-between text-xs font-mono bg-muted/40 px-2.5 py-1 rounded"
                                >
                                  <span className="truncate max-w-[200px] text-foreground">
                                    {item.value}
                                  </span>
                                  <span className="text-muted-foreground font-semibold">
                                    {item.count.toLocaleString()}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="h-64 animate-pulse rounded-2xl bg-muted" />
          )}
        </div>
      )}

      {/* TAB 4: DATA QUALITY - Refinement D: Per-column breakdown, natural text, metric explanations */}
      {activeTab === "quality" && (
        <div className="space-y-6">
          {quality ? (
            <>
              {/* Quality KPI overview */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
                  <p className="text-xs font-medium text-muted-foreground">Duplicate Rows</p>
                  <p className="mt-1 text-2xl font-bold font-mono text-foreground">
                    {quality.summary.duplicate_rows.toLocaleString()}
                  </p>
                </div>
                <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
                  <p className="text-xs font-medium text-muted-foreground">Missing Cells</p>
                  <p className="mt-1 text-2xl font-bold font-mono text-foreground">
                    {quality.summary.missing_cells.toLocaleString()} ({quality.summary.missing_percentage}%)
                  </p>
                </div>
                <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
                  <p className="text-xs font-medium text-muted-foreground">Columns with Missing Data</p>
                  <p className="mt-1 text-2xl font-bold font-mono text-foreground">
                    {quality.summary.columns_with_missing} of {quality.summary.total_columns}
                  </p>
                </div>
              </div>

              {/* Per-column missing-value breakdown table */}
              {quality.columns_breakdown && quality.columns_breakdown.length > 0 && (
                <div className="rounded-2xl border border-border bg-card p-6 shadow-xs space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-semibold text-foreground">Missing Values by Column</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Prioritized breakdown of all columns containing missing data.
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground font-medium px-2 py-0.5 rounded bg-muted">
                      {quality.columns_breakdown.length} affected {quality.columns_breakdown.length === 1 ? "column" : "columns"}
                    </span>
                  </div>

                  <div className="overflow-x-auto rounded-xl border border-border/70">
                    <table className="w-full text-left border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-border/80 bg-muted/40 text-xs font-semibold text-muted-foreground">
                          <th className="px-4 py-3">Column</th>
                          <th className="px-4 py-3">Type</th>
                          <th className="px-4 py-3 text-right">Missing Cells</th>
                          <th className="px-4 py-3 text-right">Missing %</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {quality.columns_breakdown.map((item) => (
                          <tr key={item.name} className="hover:bg-muted/30 transition-colors">
                            <td className="px-4 py-2.5 font-mono font-semibold text-foreground">
                              {item.name}
                            </td>
                            <td className="px-4 py-2.5">
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground capitalize">
                                {item.logical_type}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 font-mono text-right text-foreground">
                              {item.null_count.toLocaleString()}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-right font-semibold text-amber-600 dark:text-amber-400">
                              {item.null_percentage}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Verified Quality Findings list */}
              <div className="rounded-2xl border border-border bg-card p-6 shadow-xs space-y-4">
                <h3 className="text-base font-semibold text-foreground">Verified Quality Findings</h3>
                <div className="space-y-3">
                  {quality.quality_findings.map((finding, idx) => (
                    <div
                      key={idx}
                      className={`flex items-start gap-3 rounded-xl p-4 border text-sm ${
                        finding.severity === "warning"
                          ? "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200"
                          : "border-border/80 bg-muted/40 text-foreground"
                      }`}
                    >
                      {finding.severity === "warning" ? (
                        <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                      ) : (
                        <Info className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                      )}
                      <div>
                        <p className="font-medium">{finding.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Quality Metric Explanations */}
              <div className="rounded-2xl border border-border/80 bg-muted/15 p-6 space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Understanding Quality Indicators
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs text-muted-foreground">
                  <div>
                    <span className="font-semibold text-foreground">Duplicate Rows:</span> Rows that share identical values across every column.
                  </div>
                  <div>
                    <span className="font-semibold text-foreground">Missing Cells:</span> Null or empty values where observation data was expected.
                  </div>
                  <div>
                    <span className="font-semibold text-foreground">High Cardinality:</span> Columns with predominantly unique values, which may indicate identifiers or unstructured text.
                  </div>
                  <div>
                    <span className="font-semibold text-foreground">Constant Columns:</span> Columns possessing identical values across all records with zero variance.
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="h-64 animate-pulse rounded-2xl bg-muted" />
          )}
        </div>
      )}

      {/* Delete Confirmation Modal - Refinement F */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl">
            <h3 className="text-lg font-bold text-card-foreground">
              Delete Dataset
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Are you sure you want to delete <span className="font-semibold text-foreground">&quot;{dataset.name}&quot;</span>? This action cannot be undone and will permanently remove the dataset, its metadata, and normalized storage files.
            </p>

            {deleteError && (
              <div className="mt-4 rounded-lg bg-destructive/10 p-3 text-xs text-destructive flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{deleteError}</span>
              </div>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <Button
                variant="outline"
                disabled={isDeleting}
                onClick={() => setShowDeleteModal(false)}
                className="cursor-pointer"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={isDeleting}
                onClick={() => void handleDelete()}
                className="cursor-pointer font-semibold"
              >
                {isDeleting ? "Deleting..." : "Delete Permanently"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function DatasetDetailAsync({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <DatasetDetailContent id={id} />;
}

export default function DatasetDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <Suspense
      fallback={
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="space-y-6">
            <div className="h-8 w-40 animate-pulse rounded-lg bg-muted" />
            <div className="h-28 w-full animate-pulse rounded-2xl bg-muted" />
            <div className="h-96 w-full animate-pulse rounded-2xl bg-muted" />
          </div>
        </main>
      }
    >
      <DatasetDetailAsync params={params} />
    </Suspense>
  );
}

"use client";

import { Suspense, use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  FileText,
  Info,
  Layers,
  Table as TableIcon,
  Trash2,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api, ApiError } from "@/lib/api";
import type {
  Dataset,
  DatasetPreviewResponse,
  DatasetProfileResponse,
  DatasetQualityResponse,
} from "@/lib/types";
import { Button } from "@/components/ui/button";

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

  // Deletion modal state
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

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
      </div>

      {/* Summary KPI Strip */}
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
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <p className="text-base sm:text-lg font-semibold capitalize text-foreground">
              {dataset.status}
            </p>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
          <p className="text-xs font-medium text-muted-foreground">Engine Storage</p>
          <p className="mt-1 text-sm font-semibold text-foreground">
            Normalized Parquet
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

      {/* TAB 1: DATA PREVIEW */}
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
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border/80 bg-muted/40">
                      <th className="px-4 py-3 font-mono text-xs text-muted-foreground w-12 text-center">
                        #
                      </th>
                      {preview.columns.map((col) => (
                        <th key={col.name} className="px-4 py-3 font-semibold text-foreground whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <span>{col.name}</span>
                            <span className="text-[11px] font-mono font-normal text-muted-foreground/80 px-1.5 py-0.5 rounded bg-muted">
                              {col.duckdb_type}
                            </span>
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {preview.rows.map((row, rowIdx) => (
                      <tr key={rowIdx} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground/70 text-center">
                          {previewOffset + rowIdx + 1}
                        </td>
                        {preview.columns.map((col) => {
                          const val = row[col.name];
                          return (
                            <td key={col.name} className="px-4 py-2.5 whitespace-nowrap">
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
            ) : (
              <div className="p-8 text-center text-muted-foreground">
                No rows available to preview.
              </div>
            )}
          </div>

          {/* Pagination bar */}
          {preview && preview.total_rows > 0 && (
            <div className="flex items-center justify-between px-2 text-sm text-muted-foreground">
              <span>
                Showing rows {previewOffset + 1} to{" "}
                {Math.min(previewOffset + previewLimit, preview.total_rows)} of{" "}
                {preview.total_rows.toLocaleString()}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={previewOffset === 0 || previewLoading}
                  onClick={() => setPreviewOffset((prev) => Math.max(0, prev - previewLimit))}
                  className="cursor-pointer"
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={previewOffset + previewLimit >= preview.total_rows || previewLoading}
                  onClick={() => setPreviewOffset((prev) => prev + previewLimit)}
                  className="cursor-pointer"
                >
                  Next
                </Button>
              </div>
            </div>
          )}
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
                  <th className="px-6 py-3.5">DuckDB Engine Type</th>
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

      {/* TAB 3: COLUMN PROFILING */}
      {activeTab === "profile" && (
        <div className="space-y-6">
          {profile ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {profile.columns.map((col) => (
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
                        <div>
                          <span className="text-muted-foreground">Average (Mean):</span>
                          <p className="font-semibold text-foreground mt-0.5 font-mono">
                            {col.mean.toLocaleString()}
                          </p>
                        </div>
                      )}
                    </div>

                    {col.top_values && col.top_values.length > 0 && (
                      <div className="pt-3 border-t border-border/60">
                        <span className="text-xs font-semibold text-muted-foreground">
                          Top Frequent Values:
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
          ) : (
            <div className="h-64 animate-pulse rounded-2xl bg-muted" />
          )}
        </div>
      )}

      {/* TAB 4: DATA QUALITY */}
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

              {/* Findings list */}
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
            </>
          ) : (
            <div className="h-64 animate-pulse rounded-2xl bg-muted" />
          )}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl">
            <h3 className="text-lg font-bold text-card-foreground">
              Delete Dataset
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Are you sure you want to delete <span className="font-semibold text-foreground">&quot;{dataset.name}&quot;</span>? This action cannot be undone and will remove the normalized Parquet files.
            </p>

            {deleteError && (
              <div className="mt-4 rounded-lg bg-destructive/10 p-3 text-xs text-destructive">
                {deleteError}
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

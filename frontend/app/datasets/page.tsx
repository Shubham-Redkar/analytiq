"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Database, FileSpreadsheet, FileText, Plus, Trash2 } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api, ApiError } from "@/lib/api";
import type { Dataset } from "@/lib/types";
import { Button } from "@/components/ui/button";

export default function DatasetsListPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // Deletion modal state
  const [datasetToDelete, setDatasetToDelete] = useState<Dataset | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login?redirect=/datasets");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    let ignore = false;
    async function loadData() {
      if (!user) return;
      try {
        setError(null);
        const res = await api.listDatasets(page, 10);
        if (!ignore) {
          setDatasets(res.items);
          setTotal(res.total);
          setTotalPages(res.total_pages);
        }
      } catch (err: unknown) {
        if (!ignore) {
          if (err instanceof ApiError) {
            setError(err.message);
          } else {
            setError("Failed to load datasets. Please check your network connection.");
          }
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    if (user) {
      void loadData();
    }

    return () => {
      ignore = true;
    };
  }, [user, page, reloadKey]);

  const handleDeleteConfirm = async () => {
    if (!datasetToDelete) return;
    try {
      setIsDeleting(true);
      setDeleteError(null);
      await api.deleteDataset(datasetToDelete.id);
      setDatasetToDelete(null);
      setReloadKey((k) => k + 1);
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

  if (authLoading || (!user && loading)) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-6">
          <div className="h-9 w-48 animate-pulse rounded-lg bg-muted" />
          <div className="h-64 animate-pulse rounded-2xl bg-muted" />
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/80 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
            Datasets
          </h1>
          <p className="mt-1.5 text-sm sm:text-base text-muted-foreground">
            Manage your ingested CSV and Excel datasets.
          </p>
        </div>
        <Link href="/datasets/upload">
          <Button className="cursor-pointer font-semibold shadow-xs">
            <Plus className="mr-1.5 h-4 w-4" />
            Upload Dataset
          </Button>
        </Link>
      </div>

      {/* Main Content Area */}
      <div className="mt-8">
        {loading ? (
          <div className="space-y-4">
            <div className="h-16 w-full animate-pulse rounded-xl bg-muted" />
            <div className="h-16 w-full animate-pulse rounded-xl bg-muted" />
            <div className="h-16 w-full animate-pulse rounded-xl bg-muted" />
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-6 text-center">
            <AlertCircle className="mx-auto h-8 w-8 text-destructive mb-2" />
            <h3 className="text-base font-semibold text-destructive">Error Loading Datasets</h3>
            <p className="mt-1 text-sm text-destructive/80">{error}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReloadKey((k) => k + 1)}
              className="mt-4 cursor-pointer"
            >
              Retry
            </Button>
          </div>
        ) : datasets.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/80 bg-muted/15 p-12 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground mb-4">
              <Database className="h-7 w-7 text-foreground/70" />
            </div>
            <h3 className="text-lg font-semibold text-foreground">No datasets uploaded yet</h3>
            <p className="mt-2 text-sm text-muted-foreground max-w-sm mx-auto">
              Get started by uploading a CSV or XLSX spreadsheet to explore schemas, preview rows,
              and analyze quality.
            </p>
            <Link href="/datasets/upload" className="mt-6 inline-block">
              <Button className="cursor-pointer font-semibold">
                <Plus className="mr-1.5 h-4 w-4" />
                Upload your first dataset
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border/80 bg-muted/30 text-xs sm:text-sm font-semibold text-muted-foreground">
                      <th className="px-6 py-3.5">Name</th>
                      <th className="px-6 py-3.5">Format</th>
                      <th className="px-6 py-3.5">Rows</th>
                      <th className="px-6 py-3.5">Columns</th>
                      <th className="px-6 py-3.5">Size</th>
                      <th className="px-6 py-3.5">Uploaded</th>
                      <th className="px-6 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60 text-sm">
                    {datasets.map((dataset) => (
                      <tr key={dataset.id} className="hover:bg-muted/30 transition-colors">
                        <td className="px-6 py-4 font-semibold text-foreground">
                          <Link
                            href={`/datasets/${dataset.id}`}
                            className="hover:underline flex items-center gap-2"
                          >
                            {dataset.file_format === "CSV" ? (
                              <FileText className="h-4 w-4 text-primary shrink-0" />
                            ) : (
                              <FileSpreadsheet className="h-4 w-4 text-emerald-600 shrink-0" />
                            )}
                            <span className="truncate max-w-xs">{dataset.name}</span>
                          </Link>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                                dataset.file_format === "CSV"
                                  ? "bg-primary/10 text-primary"
                                  : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              }`}
                            >
                              {dataset.file_format}
                            </span>
                            {dataset.status === "deletion_failed" && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-destructive/15 text-destructive">
                                Deletion Failed
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-muted-foreground font-mono">
                          {dataset.row_count !== null ? dataset.row_count.toLocaleString() : "—"}
                        </td>
                        <td className="px-6 py-4 text-muted-foreground font-mono">
                          {dataset.column_count !== null ? dataset.column_count : "—"}
                        </td>
                        <td className="px-6 py-4 text-muted-foreground">
                          {(dataset.file_size_bytes / 1024).toFixed(1)} KB
                        </td>
                        <td className="px-6 py-4 text-muted-foreground">
                          {new Date(dataset.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Link href={`/datasets/${dataset.id}`}>
                              <Button variant="ghost" size="sm" className="cursor-pointer text-xs">
                                Explore
                              </Button>
                            </Link>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDatasetToDelete(dataset)}
                              className="cursor-pointer text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-2 text-sm text-muted-foreground">
                <span>
                  Showing {datasets.length} of {total} datasets
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="cursor-pointer"
                  >
                    Previous
                  </Button>
                  <span className="text-xs font-medium px-2">
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="cursor-pointer"
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {datasetToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl">
            <h3 className="text-lg font-bold text-card-foreground">Delete Dataset</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Are you sure you want to delete{" "}
              <span className="font-semibold text-foreground">
                &quot;{datasetToDelete.name}&quot;
              </span>
              ? This action cannot be undone and will permanently remove the dataset, its metadata,
              and normalized storage files.
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
                onClick={() => setDatasetToDelete(null)}
                className="cursor-pointer"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={isDeleting}
                onClick={() => void handleDeleteConfirm()}
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

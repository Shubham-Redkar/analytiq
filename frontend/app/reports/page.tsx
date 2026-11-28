"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  Plus,
  Search,
  ExternalLink,
  Copy,
  Trash2,
  Calendar,
  Layers,
  Download,
  AlertCircle,
  Database,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import type { ReportSummary } from "@/lib/report-types";

export default function ReportsListPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page] = useState(1);
  const [pageSize] = useState(12);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  // Delete dialog state
  const [reportToDelete, setReportToDelete] = useState<ReportSummary | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login?redirect=/reports");
    }
  }, [user, loading, router]);

  useEffect(() => {
    let ignore = false;
    async function fetchReports() {
      if (!user) return;
      try {
        setIsLoading(true);
        setActionError(null);
        const res = await api.listReports(page, pageSize);
        if (!ignore) {
          if (!res || !Array.isArray(res.items) || typeof res.total !== "number") {
            throw new Error("Invalid response format received from reports service.");
          }
          setReports(res.items);
          setTotal(res.total);
        }
      } catch {
        if (!ignore) {
          setActionError("Failed to load reports. Please try again.");
          setReports([]);
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    if (user) {
      void fetchReports();
    }

    return () => {
      ignore = true;
    };
  }, [user, page, pageSize]);

  const handleDuplicate = async (reportId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      setActionError(null);
      const duplicate = await api.duplicateReport(reportId);
      setReports((prev) => [duplicate, ...prev]);
      setTotal((prev) => prev + 1);
    } catch {
      setActionError("Unable to duplicate report.");
    }
  };

  const confirmDelete = async () => {
    if (!reportToDelete) return;
    try {
      setIsDeleting(true);
      setActionError(null);
      await api.deleteReport(reportToDelete.id);
      setReports((prev) => prev.filter((r) => r.id !== reportToDelete.id));
      setTotal((prev) => Math.max(0, prev - 1));
      setReportToDelete(null);
    } catch {
      setActionError("Unable to delete report.");
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredReports = (reports || []).filter(
    (r) =>
      (r?.title || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r?.dataset_name && r.dataset_name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/60 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <FileText className="h-7 w-7 text-primary" />
            <span>Analytical Reports</span>
          </h1>
          <p className="mt-1.5 text-sm sm:text-base text-muted-foreground">
            Professional, evidence-grounded reports compiled directly from verified analyses.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/analysis">
            <Button className="cursor-pointer font-semibold shadow-xs">
              <Plus className="mr-1.5 h-4 w-4" />
              New Report from Analysis
            </Button>
          </Link>
        </div>
      </div>

      {actionError && (
        <div className="mt-4 flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Filter / Search Bar */}
      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search reports by title or dataset..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-border bg-card pl-10 pr-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>
        <span className="text-xs sm:text-sm font-medium text-muted-foreground">
          {total} {total === 1 ? "report" : "reports"} total
        </span>
      </div>

      {/* Reports Grid */}
      <div className="mt-6">
        {isLoading ? (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-56 animate-pulse rounded-2xl bg-muted/60" />
            ))}
          </div>
        ) : filteredReports.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-card/40 p-12 text-center">
            <FileText className="mx-auto h-12 w-12 text-muted-foreground/60" />
            <h3 className="mt-4 text-base font-semibold text-foreground">
              {searchQuery ? "No matching reports found" : "No reports generated yet"}
            </h3>
            <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
              {searchQuery
                ? "Try searching with different keywords."
                : "Run queries in the Analytical Workspace, then click 'Create Report' to produce executive summaries, charts, and PDF exports."}
            </p>
            {!searchQuery && (
              <Link href="/analysis" className="mt-5 inline-block">
                <Button className="cursor-pointer">Go to Analysis Workspace</Button>
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {filteredReports.map((report) => (
              <div
                key={report.id}
                className="group relative flex flex-col justify-between rounded-2xl border border-border bg-card p-6 shadow-2xs hover:shadow-md transition-all hover:border-primary/40"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
                      <Layers className="h-3 w-3" />v{report.revision}
                    </span>
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <button
                        title="Duplicate report"
                        onClick={(e) => handleDuplicate(report.id, e)}
                        className="rounded-lg p-1.5 hover:bg-muted hover:text-foreground transition cursor-pointer"
                      >
                        <Copy className="h-4 w-4" />
                      </button>
                      <button
                        title="Delete report"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setReportToDelete(report);
                        }}
                        className="rounded-lg p-1.5 hover:bg-destructive/10 hover:text-destructive transition cursor-pointer"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  <Link
                    href={`/reports/${report.id}`}
                    className="block mt-3 group-hover:text-primary transition"
                  >
                    <h3 className="text-base font-semibold text-foreground group-hover:text-primary transition line-clamp-2">
                      {report.title}
                    </h3>
                  </Link>

                  {report.description && (
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                      {report.description}
                    </p>
                  )}

                  <div className="mt-4 flex flex-col gap-1.5 text-xs text-muted-foreground">
                    {report.dataset_name && (
                      <div className="flex items-center gap-1.5">
                        <Database className="h-3.5 w-3.5 text-primary/70 shrink-0" />
                        <span className="truncate">{report.dataset_name}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-1.5">
                      <Calendar className="h-3.5 w-3.5 shrink-0" />
                      <span>
                        {new Date(report.updated_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-5 pt-4 border-t border-border/60 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <a
                      href={api.getReportPdfUrl(report.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground hover:underline"
                    >
                      <Download className="h-3.5 w-3.5" />
                      PDF
                    </a>
                    <span className="text-muted-foreground/40">·</span>
                    <a
                      href={api.getReportCsvUrl(report.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground hover:underline"
                    >
                      <Download className="h-3.5 w-3.5" />
                      CSV
                    </a>
                  </div>

                  <Link
                    href={`/reports/${report.id}`}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
                  >
                    <span>View report</span>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Alert Dialog */}
      <AlertDialog
        open={!!reportToDelete}
        onOpenChange={(open) => {
          if (!open && !isDeleting) setReportToDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete report?</AlertDialogTitle>
            <AlertDialogDescription className="break-words">
              This will permanently delete &lsquo;{reportToDelete?.title}&rsquo; and its compiled
              report document. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90 cursor-pointer"
            >
              {isDeleting ? "Deleting..." : "Delete report"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

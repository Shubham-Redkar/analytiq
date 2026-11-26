"use client";

import { Suspense, use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Download,
  ArrowLeft,
  CheckCircle2,
  Calendar,
  Database,
  Layers,
  AlertTriangle,
  Info,
  ShieldCheck,
  Edit2,
  Save,
  RotateCcw,
  Eye,
  EyeOff,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type {
  ReportDetail,
  ReportBlock,
  ReportSection,
  HeadingBlock,
  ParagraphBlock,
  VerifiedFindingBlock,
  ScalarMetricBlock,
  ChartBlock,
  ResultTableBlock,
} from "@/lib/report-types";

// Dynamic Recharts import for client visualization
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

function ReportDetailContent({ reportId }: { reportId: string }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [report, setReport] = useState<ReportDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit Mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editedTitle, setEditedTitle] = useState("");
  const [editedDescription, setEditedDescription] = useState("");
  const [editedSummary, setEditedSummary] = useState("");
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push(`/login?redirect=/reports/${reportId}`);
    }
  }, [user, loading, router, reportId]);

  useEffect(() => {
    let ignore = false;
    async function fetchReport() {
      if (!user) return;
      try {
        setIsLoading(true);
        setError(null);
        const res = await api.getReport(reportId);
        if (!ignore) {
          setReport(res);
          setEditedTitle(res.title);
          setEditedDescription(res.description || "");
          setEditedSummary(res.document.executive_summary || "");
          setSections(res.document.sections || []);
        }
      } catch {
        if (!ignore) {
          setError("Unable to load report details. Please check your connection.");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    if (user) {
      void fetchReport();
    }

    return () => {
      ignore = true;
    };
  }, [user, reportId]);

  const handleSave = async () => {
    if (!report) return;
    try {
      setIsSaving(true);
      setError(null);
      setSaveSuccess(false);

      const updatedDoc = {
        ...report.document,
        metadata: {
          ...report.document.metadata,
          title: editedTitle,
          description: editedDescription,
        },
        executive_summary: editedSummary,
        sections: sections,
      };

      const updated = await api.updateReport(report.id, {
        title: editedTitle,
        description: editedDescription,
        document: updatedDoc as unknown as Record<string, unknown>,
        revision: report.revision,
      });

      setReport(updated);
      setEditedTitle(updated.title);
      setEditedDescription(updated.description || "");
      setEditedSummary(updated.document.executive_summary || "");
      setSections(updated.document.sections || []);
      setIsEditing(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch {
      setError("Failed to save changes. Concurrency conflict or network error.");
    } finally {
      setIsSaving(false);
    }
  };

  const toggleSectionVisibility = (secId: string) => {
    setSections((prev) => prev.map((s) => (s.id === secId ? { ...s, visible: !s.visible } : s)));
  };

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
        <div className="h-10 w-48 animate-pulse rounded-lg bg-muted/60 mb-6" />
        <div className="h-64 animate-pulse rounded-2xl bg-muted/40" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-destructive/10 text-destructive mb-4">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <h2 className="text-xl font-bold text-foreground">Report Not Available</h2>
        <p className="mt-2 text-sm text-muted-foreground">{error || "Report not found."}</p>
        <Link href="/reports" className="mt-6 inline-block">
          <Button variant="outline">Back to Reports</Button>
        </Link>
      </div>
    );
  }

  const doc = report.document;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Navigation & Controls Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/60 pb-6">
        <div className="flex items-center gap-3">
          <Link href="/reports">
            <Button variant="ghost" size="sm" className="gap-1 cursor-pointer">
              <ArrowLeft className="h-4 w-4" />
              <span>All Reports</span>
            </Button>
          </Link>
          <span className="text-muted-foreground/40">/</span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
            <Layers className="h-3 w-3" />
            Revision {report.revision}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {isEditing ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setIsEditing(false);
                  setEditedTitle(report.title);
                  setEditedDescription(report.description || "");
                  setEditedSummary(doc.executive_summary || "");
                  setSections(doc.sections || []);
                }}
                disabled={isSaving}
                className="cursor-pointer"
              >
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={isSaving}
                className="cursor-pointer font-semibold shadow-xs"
              >
                <Save className="mr-1.5 h-3.5 w-3.5" />
                {isSaving ? "Saving..." : "Save Changes"}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsEditing(true)}
                className="cursor-pointer"
              >
                <Edit2 className="mr-1.5 h-3.5 w-3.5" />
                Customize Report
              </Button>
              <a
                href={api.getReportPdfUrl(report.id)}
                target="_blank"
                rel="noopener noreferrer"
                download
              >
                <Button size="sm" variant="outline" className="cursor-pointer font-medium">
                  <Download className="mr-1.5 h-3.5 w-3.5" />
                  Download PDF
                </Button>
              </a>
              <a
                href={api.getReportCsvUrl(report.id)}
                target="_blank"
                rel="noopener noreferrer"
                download
              >
                <Button size="sm" variant="outline" className="cursor-pointer font-medium">
                  <Download className="mr-1.5 h-3.5 w-3.5" />
                  Export CSV
                </Button>
              </a>
            </>
          )}
        </div>
      </div>

      {saveSuccess && (
        <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2.5 text-xs text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>Report updated successfully.</span>
        </div>
      )}

      {/* Report Document Sheet */}
      <article className="mt-8 rounded-2xl border border-border bg-card p-6 sm:p-10 shadow-sm space-y-10">
        {/* Document Header */}
        <header className="border-b border-border/60 pb-8 space-y-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary">
            <ShieldCheck className="h-4 w-4" />
            <span>AnalytIQ Verified Analytical Report</span>
          </div>

          {isEditing ? (
            <div className="space-y-3">
              <label className="block text-xs font-semibold text-muted-foreground">
                Report Title
              </label>
              <input
                type="text"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                className="w-full rounded-xl border border-border bg-background px-4 py-2 text-xl font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
              <label className="block text-xs font-semibold text-muted-foreground">
                Report Description
              </label>
              <textarea
                value={editedDescription}
                onChange={(e) => setEditedDescription(e.target.value)}
                rows={2}
                className="w-full rounded-xl border border-border bg-background px-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
          ) : (
            <div>
              <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-foreground">
                {report.title}
              </h1>
              {report.description && (
                <p className="mt-2 text-base text-muted-foreground">{report.description}</p>
              )}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-6 pt-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Database className="h-4 w-4 text-primary" />
              <span className="font-medium text-foreground">{doc.metadata.dataset_name}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" />
              <span>
                Generated{" "}
                {new Date(doc.metadata.generated_at).toLocaleDateString(undefined, {
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                })}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <span>100% Deterministically Grounded</span>
            </div>
          </div>
        </header>

        {/* Executive Summary */}
        <section className="space-y-3 rounded-2xl border border-border/80 bg-muted/20 p-6">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-primary" />
            <h2 className="text-base font-bold text-foreground uppercase tracking-wider text-xs">
              Executive Summary
            </h2>
          </div>
          {isEditing ? (
            <textarea
              value={editedSummary}
              onChange={(e) => setEditedSummary(e.target.value)}
              rows={4}
              className="w-full rounded-xl border border-border bg-background p-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          ) : (
            <p className="text-sm sm:text-base leading-relaxed text-foreground font-medium">
              {doc.executive_summary}
            </p>
          )}
        </section>

        {/* Dataset Overview Block */}
        <section className="space-y-3">
          <h2 className="text-lg font-bold tracking-tight text-foreground">Dataset Overview</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 rounded-xl border border-border bg-card p-4">
            <div>
              <span className="text-xs text-muted-foreground">Dataset Name</span>
              <p className="text-sm font-semibold text-foreground truncate">
                {doc.dataset_overview.dataset_name}
              </p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Total Records</span>
              <p className="text-sm font-semibold text-foreground">
                {doc.dataset_overview.row_count.toLocaleString()}
              </p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Total Columns</span>
              <p className="text-sm font-semibold text-foreground">
                {doc.dataset_overview.column_count}
              </p>
            </div>
          </div>
        </section>

        {/* Report Sections */}
        <div className="space-y-12">
          {sections.map((section, idx) => (
            <section
              key={section.id}
              className={`space-y-6 pt-6 border-t border-border/60 ${
                !section.visible ? "opacity-40" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-primary">Query {idx + 1}</span>
                  <h3 className="text-xl font-bold tracking-tight text-foreground">
                    {section.title}
                  </h3>
                </div>
                {isEditing && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleSectionVisibility(section.id)}
                    className="cursor-pointer gap-1.5 text-xs"
                  >
                    {section.visible ? (
                      <>
                        <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
                        Hide in PDF
                      </>
                    ) : (
                      <>
                        <Eye className="h-3.5 w-3.5 text-primary" />
                        Show in PDF
                      </>
                    )}
                  </Button>
                )}
              </div>

              {/* Render Section Blocks */}
              <div className="space-y-6">{section.blocks.map((block) => renderBlock(block))}</div>
            </section>
          ))}
        </div>

        {/* Methodology Note */}
        {doc.methodology && (
          <section className="rounded-xl border border-border/60 bg-muted/30 p-5 text-xs text-muted-foreground space-y-1.5">
            <div className="flex items-center gap-1.5 font-semibold text-foreground">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <span>Verification Methodology</span>
            </div>
            <p className="leading-relaxed">{doc.methodology.note}</p>
          </section>
        )}

        {/* Evidence Appendix */}
        {doc.evidence_appendix && doc.evidence_appendix.length > 0 && (
          <section className="space-y-3 pt-6 border-t border-border/60">
            <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
              Evidence Appendix & Reproducibility
            </h3>
            <div className="space-y-3">
              {doc.evidence_appendix.map((ev, i) => (
                <div
                  key={ev.id || i}
                  className="rounded-xl border border-border bg-card p-4 text-xs space-y-2"
                >
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span className="font-mono">Request: {ev.request_id}</span>
                    <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {ev.verification_status || "verified"}
                    </span>
                  </div>
                  {ev.executed_sql && (
                    <div className="rounded-lg bg-muted p-2 font-mono text-[11px] overflow-x-auto">
                      <code>{ev.executed_sql}</code>
                    </div>
                  )}
                  {ev.result_fingerprint && (
                    <div className="text-[11px] font-mono text-muted-foreground">
                      Result Fingerprint: {ev.result_fingerprint}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </article>
    </div>
  );
}

function renderBlock(block: ReportBlock) {
  switch (block.block_type) {
    case "heading": {
      const heading = block as HeadingBlock;
      return (
        <h4 key={block.id} className="text-lg font-bold text-foreground">
          {heading.text}
        </h4>
      );
    }

    case "paragraph": {
      const para = block as ParagraphBlock;
      return (
        <p key={block.id} className="text-sm sm:text-base leading-relaxed text-muted-foreground">
          {para.text}
        </p>
      );
    }

    case "verified_finding": {
      const finding = block as VerifiedFindingBlock;
      return (
        <div
          key={block.id}
          className="flex items-start gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4"
        >
          <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              Verified Finding
            </span>
            <p className="mt-0.5 text-sm font-medium text-foreground">{finding.finding_text}</p>
          </div>
        </div>
      );
    }

    case "scalar_metric": {
      const scalar = block as ScalarMetricBlock;
      return (
        <div
          key={block.id}
          className="inline-flex flex-col rounded-xl border border-border bg-card p-4 min-w-[160px]"
        >
          <span className="text-xs font-medium text-muted-foreground">{scalar.label}</span>
          <span className="mt-1 text-2xl font-extrabold text-foreground tracking-tight">
            {String(scalar.value)}
          </span>
        </div>
      );
    }

    case "chart": {
      const chart = block as ChartBlock;
      const spec = chart.spec;
      const data = spec.data || [];
      const xKey = spec.x_axis_key || "name";
      const series = spec.series || [];

      return (
        <div key={block.id} className="rounded-2xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h5 className="text-sm font-semibold text-foreground">{spec.title}</h5>
            <span className="text-xs font-mono text-muted-foreground uppercase">
              {spec.chart_type}
            </span>
          </div>
          {data.length > 0 ? (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                {spec.chart_type === "line" ? (
                  <LineChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                    <XAxis dataKey={xKey} stroke="#888888" fontSize={11} tickLine={false} />
                    <YAxis stroke="#888888" fontSize={11} tickLine={false} />
                    <Tooltip />
                    {series.map((s, idx) => (
                      <Line
                        key={s.data_key}
                        type="monotone"
                        dataKey={s.data_key}
                        stroke={s.color || (idx === 0 ? "#2563EB" : "#10B981")}
                        strokeWidth={2}
                      />
                    ))}
                  </LineChart>
                ) : (
                  <BarChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                    <XAxis dataKey={xKey} stroke="#888888" fontSize={11} tickLine={false} />
                    <YAxis stroke="#888888" fontSize={11} tickLine={false} />
                    <Tooltip />
                    {series.map((s, idx) => (
                      <Bar
                        key={s.data_key}
                        dataKey={s.data_key}
                        fill={s.color || (idx === 0 ? "#2563EB" : "#10B981")}
                        radius={[4, 4, 0, 0]}
                      />
                    ))}
                  </BarChart>
                )}
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-32 flex items-center justify-center text-xs text-muted-foreground">
              No chart data points available.
            </div>
          )}
        </div>
      );
    }

    case "result_table": {
      const table = block as ResultTableBlock;
      return (
        <div key={block.id} className="rounded-2xl border border-border bg-card overflow-hidden">
          <div className="border-b border-border/60 px-4 py-3 flex items-center justify-between">
            <h5 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {table.title}
            </h5>
            <span className="text-xs text-muted-foreground">{table.returned_row_count} rows</span>
          </div>
          <div className="overflow-x-auto max-h-72">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b border-border font-medium text-foreground sticky top-0">
                <tr>
                  {table.columns.map((col, idx) => (
                    <th key={idx} className="px-4 py-2.5">
                      {col.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {table.rows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-muted/20">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="px-4 py-2 font-mono text-[11px] text-foreground">
                        {cell === null ? (
                          <span className="text-muted-foreground italic">null</span>
                        ) : (
                          String(cell)
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    }

    default:
      return null;
  }
}

function ReportDetailAsync({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <ReportDetailContent reportId={id} />;
}

export default function ReportDetailPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
          <div className="h-10 w-48 animate-pulse rounded-lg bg-muted/60 mb-6" />
          <div className="h-64 animate-pulse rounded-2xl bg-muted/40" />
        </div>
      }
    >
      <ReportDetailAsync params={params} />
    </Suspense>
  );
}

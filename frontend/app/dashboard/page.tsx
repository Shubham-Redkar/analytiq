"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Database, LineChart, Plus, Sparkles } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [datasetCount, setDatasetCount] = useState<number | null>(null);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [datasetError, setDatasetError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login?redirect=/dashboard");
    }
  }, [user, loading, router]);

  useEffect(() => {
    let ignore = false;
    async function loadDatasetStats() {
      if (!user) return;
      try {
        setDatasetsLoading(true);
        setDatasetError(null);
        const res = await api.listDatasets(1, 1);
        if (!ignore) {
          setDatasetCount(res.total);
        }
      } catch {
        if (!ignore) {
          setDatasetError("Unable to load dataset metrics. Please check your connection.");
        }
      } finally {
        if (!ignore) {
          setDatasetsLoading(false);
        }
      }
    }

    if (user) {
      void loadDatasetStats();
    }

    return () => {
      ignore = true;
    };
  }, [user]);

  if (loading) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-6">
          <div className="h-9 w-64 animate-pulse rounded-lg bg-muted" />
          <div className="h-5 w-80 animate-pulse rounded-lg bg-muted" />
          <div className="grid grid-cols-1 gap-6 pt-6 sm:grid-cols-2">
            <div className="h-32 animate-pulse rounded-2xl bg-muted" />
            <div className="h-32 animate-pulse rounded-2xl bg-muted" />
          </div>
          <div className="h-44 animate-pulse rounded-2xl bg-muted" />
        </div>
      </main>
    );
  }

  if (!user) {
    return null;
  }

  const displayName = user.display_name?.trim();
  const welcomeHeading = displayName ? `Welcome back, ${displayName}` : "Welcome back";

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Welcome Section */}
      <section className="border-b border-border/80 pb-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
              {welcomeHeading}
            </h1>
            <p className="mt-1.5 text-sm sm:text-base text-muted-foreground">
              Your analytics workspace at a glance.
            </p>
          </div>
          <Link href="/datasets/upload">
            <Button className="cursor-pointer font-semibold shadow-xs">
              <Plus className="mr-1.5 h-4 w-4" />
              Upload Dataset
            </Button>
          </Link>
        </div>
      </section>

      {/* Workspace Overview */}
      <section className="mt-8">
        <h2 className="text-lg sm:text-xl font-semibold tracking-tight text-foreground mb-4">
          Workspace Overview
        </h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          {/* Datasets Card */}
          <div className="rounded-2xl border border-border bg-card p-6 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                    <Database className="h-5 w-5 text-foreground/80" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-card-foreground">Datasets</h3>
                    <p className="text-xs sm:text-sm text-muted-foreground">Data ingestion & exploration</p>
                  </div>
                </div>
                {datasetCount !== null && datasetCount > 0 && (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary">
                    {datasetCount} {datasetCount === 1 ? "dataset" : "datasets"}
                  </span>
                )}
              </div>

              <div className="mt-5">
                {datasetsLoading ? (
                  <div className="h-10 w-full animate-pulse rounded-xl bg-muted/60" />
                ) : datasetError ? (
                  <div className="flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/10 px-4 py-2.5 text-xs sm:text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{datasetError}</span>
                  </div>
                ) : datasetCount === 0 ? (
                  <div className="rounded-xl border border-border/60 bg-muted/30 px-4 py-3">
                    <span className="text-xs sm:text-sm font-medium text-muted-foreground">
                      No datasets connected yet
                    </span>
                  </div>
                ) : (
                  <div className="rounded-xl border border-border/60 bg-muted/30 px-4 py-3 flex items-center justify-between">
                    <span className="text-xs sm:text-sm font-medium text-foreground">
                      {datasetCount} active {datasetCount === 1 ? "dataset" : "datasets"} ready for exploration
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-5 pt-4 border-t border-border/60 flex items-center justify-between">
              <Link
                href="/datasets"
                className="text-sm font-semibold text-primary hover:underline transition-colors"
              >
                View all datasets &rarr;
              </Link>
              <Link href="/datasets/upload">
                <Button variant="outline" size="sm" className="cursor-pointer text-xs">
                  Upload new
                </Button>
              </Link>
            </div>
          </div>

          {/* Analyses Card (Natural product language without milestone jargon) */}
          <div className="rounded-2xl border border-border bg-card p-6 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                    <LineChart className="h-5 w-5 text-foreground/80" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-card-foreground">Analyses</h3>
                    <p className="text-xs sm:text-sm text-muted-foreground">Analytical sessions & reports</p>
                  </div>
                </div>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-muted text-muted-foreground">
                  Coming soon
                </span>
              </div>
              <div className="mt-5 rounded-xl border border-border/60 bg-muted/30 px-4 py-3">
                <span className="text-xs sm:text-sm font-medium text-muted-foreground">
                  Explore your datasets with intelligent analysis tools.
                </span>
              </div>
            </div>

            <div className="mt-5 pt-4 border-t border-border/60">
              <span className="text-xs sm:text-sm text-muted-foreground">
                Automated analytical reasoning and report generation will be available here.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Workspace State */}
      <section className="mt-8 rounded-2xl border border-dashed border-border/80 bg-muted/15 p-8 sm:p-10 text-center">
        <div className="mx-auto max-w-md flex flex-col items-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground mb-4">
            <Sparkles className="h-6 w-6 text-foreground/70" />
          </div>
          <h3 className="text-lg sm:text-xl font-semibold text-foreground">
            Your workspace is ready
          </h3>
          <p className="mt-2 text-sm sm:text-base text-muted-foreground leading-relaxed">
            {datasetCount !== null && datasetCount > 0
              ? `You have ${datasetCount} active dataset(s) ready in your workspace. Explore schemas, previews, and quality metrics.`
              : "Upload your first CSV or Excel dataset to generate schema definitions, examine column statistics, and inspect data quality."}
          </p>
          <div className="mt-5">
            {datasetCount !== null && datasetCount > 0 ? (
              <Link href="/datasets">
                <Button className="cursor-pointer font-semibold">
                  Explore Datasets &rarr;
                </Button>
              </Link>
            ) : (
              <Link href="/datasets/upload">
                <Button className="cursor-pointer font-semibold">
                  <Plus className="mr-1.5 h-4 w-4" />
                  Upload your first dataset
                </Button>
              </Link>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

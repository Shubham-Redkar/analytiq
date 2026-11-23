"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login?redirect=/dashboard");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="space-y-4">
          <div className="h-8 w-48 animate-pulse rounded bg-muted" />
          <div className="h-4 w-96 animate-pulse rounded bg-muted" />
          <div className="grid grid-cols-1 gap-6 pt-6 sm:grid-cols-3">
            <div className="h-32 animate-pulse rounded-xl bg-muted" />
            <div className="h-32 animate-pulse rounded-xl bg-muted" />
            <div className="h-32 animate-pulse rounded-xl bg-muted" />
          </div>
        </div>
      </main>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            Welcome, {user.display_name}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage your analytics workspace, datasets, and verified evidence plans.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Authenticated Session
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void logout()}
            className="cursor-pointer"
          >
            Sign out
          </Button>
        </div>
      </div>

      {/* User Identity Profile Card */}
      <section className="mt-6 rounded-xl border border-border bg-card p-6 shadow-xs">
        <h2 className="text-lg font-semibold text-card-foreground">
          User Identity & Ownership Foundation
        </h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3 text-sm">
          <div className="rounded-lg border border-border/60 bg-muted/40 p-4">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Email Address
            </span>
            <p className="mt-1 font-medium text-foreground">{user.email}</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-muted/40 p-4">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              User ID
            </span>
            <p className="mt-1 font-mono text-xs text-foreground truncate">{user.id}</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-muted/40 p-4">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Account Status
            </span>
            <p className="mt-1 font-medium text-emerald-600 dark:text-emerald-400">
              {user.is_active ? "Active" : "Inactive"}
            </p>
          </div>
        </div>
      </section>

      {/* Workspace Metric Cards */}
      <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-6 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Datasets</span>
            <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">M2</span>
          </div>
          <p className="mt-4 text-3xl font-bold text-foreground">0</p>
          <p className="mt-1 text-xs text-muted-foreground">CSV & Parquet files uploaded</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Analyses</span>
            <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">M3</span>
          </div>
          <p className="mt-4 text-3xl font-bold text-foreground">0</p>
          <p className="mt-1 text-xs text-muted-foreground">Executed analytical sessions</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Milestone</span>
            <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">Active</span>
          </div>
          <p className="mt-4 text-2xl font-bold text-foreground">M1 Foundation</p>
          <p className="mt-1 text-xs text-muted-foreground">Auth & session lifecycle active</p>
        </div>
      </div>

      {/* Empty State / Roadmap Guide */}
      <section className="mt-8 rounded-xl border border-dashed border-border p-8 text-center">
        <div className="mx-auto max-w-md">
          <h3 className="text-base font-semibold text-foreground">
            No datasets connected yet
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Milestone M2 will introduce robust dataset ingestion, DuckDB-powered schema profiling, and secure parquet storage under user ownership.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Button disabled variant="outline" size="sm">
              Upload Dataset (M2)
            </Button>
            <Button disabled variant="outline" size="sm">
              New Analysis (M3)
            </Button>
          </div>
        </div>
      </section>
    </main>
  );
}

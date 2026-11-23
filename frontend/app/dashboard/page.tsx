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
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-6">
          <div className="h-9 w-56 animate-pulse rounded-lg bg-muted" />
          <div className="h-5 w-96 animate-pulse rounded-lg bg-muted" />
          <div className="grid grid-cols-1 gap-6 pt-6 sm:grid-cols-3">
            <div className="h-36 animate-pulse rounded-2xl bg-muted" />
            <div className="h-36 animate-pulse rounded-2xl bg-muted" />
            <div className="h-36 animate-pulse rounded-2xl bg-muted" />
          </div>
        </div>
      </main>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="flex flex-col gap-4 border-b border-border/80 pb-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight text-foreground">
            Welcome, {user.display_name}
          </h1>
          <p className="mt-1.5 text-sm sm:text-base text-muted-foreground">
            Manage your analytics workspace, datasets, and verified evidence plans.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-1 text-xs sm:text-sm font-semibold text-emerald-700 dark:text-emerald-300">
            <span className="h-2 w-2 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20" />
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
      <section className="mt-8 rounded-2xl border border-border bg-card p-6 sm:p-7 shadow-xs">
        <h2 className="text-lg sm:text-xl font-semibold tracking-tight text-card-foreground">
          User Identity & Ownership Foundation
        </h2>
        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3 text-sm sm:text-base">
          <div className="rounded-xl border border-border/70 bg-muted/40 p-4 sm:p-5">
            <span className="text-xs sm:text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Email Address
            </span>
            <p className="mt-1.5 font-semibold text-foreground break-all">{user.email}</p>
          </div>
          <div className="rounded-xl border border-border/70 bg-muted/40 p-4 sm:p-5">
            <span className="text-xs sm:text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              User ID
            </span>
            <p className="mt-1.5 font-mono text-xs sm:text-sm font-medium text-foreground truncate">
              {user.id}
            </p>
          </div>
          <div className="rounded-xl border border-border/70 bg-muted/40 p-4 sm:p-5">
            <span className="text-xs sm:text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Account Status
            </span>
            <p className="mt-1.5 font-semibold text-emerald-700 dark:text-emerald-300 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              {user.is_active ? "Active" : "Inactive"}
            </p>
          </div>
        </div>
      </section>

      {/* Workspace Metric Cards */}
      <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div className="rounded-2xl border border-border bg-card p-6 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-sm sm:text-base font-medium text-muted-foreground">Datasets</span>
            <span className="rounded-md bg-muted px-2.5 py-0.5 text-xs font-semibold text-muted-foreground border border-border/60">
              M2
            </span>
          </div>
          <p className="mt-4 text-3xl sm:text-4xl font-extrabold text-foreground">0</p>
          <p className="mt-1.5 text-xs sm:text-sm text-muted-foreground">CSV & Parquet files uploaded</p>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-sm sm:text-base font-medium text-muted-foreground">Analyses</span>
            <span className="rounded-md bg-muted px-2.5 py-0.5 text-xs font-semibold text-muted-foreground border border-border/60">
              M3
            </span>
          </div>
          <p className="mt-4 text-3xl sm:text-4xl font-extrabold text-foreground">0</p>
          <p className="mt-1.5 text-xs sm:text-sm text-muted-foreground">Executed analytical sessions</p>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-sm sm:text-base font-medium text-muted-foreground">Milestone</span>
            <span className="rounded-md bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary border border-primary/20">
              Active
            </span>
          </div>
          <p className="mt-4 text-2xl sm:text-3xl font-extrabold text-foreground">M1 Foundation</p>
          <p className="mt-1.5 text-xs sm:text-sm text-muted-foreground">Auth & session lifecycle active</p>
        </div>
      </div>

      {/* Empty State / Roadmap Guide */}
      <section className="mt-8 rounded-2xl border border-dashed border-border/90 bg-muted/20 p-8 sm:p-10 text-center">
        <div className="mx-auto max-w-lg">
          <h3 className="text-lg sm:text-xl font-semibold text-foreground">
            No datasets connected yet
          </h3>
          <p className="mt-2.5 text-sm sm:text-base text-muted-foreground leading-relaxed">
            Milestone M2 will introduce robust dataset ingestion, DuckDB-powered schema profiling, and secure parquet storage under user ownership.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
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

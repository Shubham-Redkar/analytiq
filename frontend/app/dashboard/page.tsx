"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Database, LineChart, Sparkles } from "lucide-react";
import { useAuth } from "@/context/auth-context";

export default function DashboardPage() {
  const { user, loading } = useAuth();
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
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
          {welcomeHeading}
        </h1>
        <p className="mt-1.5 text-sm sm:text-base text-muted-foreground">
          Your analytics workspace at a glance.
        </p>
      </section>

      {/* Workspace Overview */}
      <section className="mt-8">
        <h2 className="text-lg sm:text-xl font-semibold tracking-tight text-foreground mb-4">
          Workspace Overview
        </h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          {/* Datasets Card */}
          <div className="rounded-2xl border border-border bg-card p-6 shadow-xs">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                <Database className="h-5 w-5 text-foreground/80" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-card-foreground">Datasets</h3>
                <p className="text-xs sm:text-sm text-muted-foreground">Data ingestion & profiles</p>
              </div>
            </div>
            <div className="mt-5 rounded-xl border border-border/60 bg-muted/30 px-4 py-3">
              <span className="text-xs sm:text-sm font-medium text-muted-foreground">
                No datasets connected yet
              </span>
            </div>
          </div>

          {/* Analyses Card */}
          <div className="rounded-2xl border border-border bg-card p-6 shadow-xs">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                <LineChart className="h-5 w-5 text-foreground/80" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-card-foreground">Analyses</h3>
                <p className="text-xs sm:text-sm text-muted-foreground">Analytical sessions & reports</p>
              </div>
            </div>
            <div className="mt-5 rounded-xl border border-border/60 bg-muted/30 px-4 py-3">
              <span className="text-xs sm:text-sm font-medium text-muted-foreground">
                No analytical sessions yet
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Product-Oriented Empty State */}
      <section className="mt-8 rounded-2xl border border-dashed border-border/80 bg-muted/15 p-8 sm:p-10 text-center">
        <div className="mx-auto max-w-md flex flex-col items-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground mb-4">
            <Sparkles className="h-6 w-6 text-foreground/70" />
          </div>
          <h3 className="text-lg sm:text-xl font-semibold text-foreground">
            Your workspace is ready
          </h3>
          <p className="mt-2 text-sm sm:text-base text-muted-foreground leading-relaxed">
            Your datasets and analytical insights will appear here once you begin working with data.
          </p>
        </div>
      </section>
    </main>
  );
}

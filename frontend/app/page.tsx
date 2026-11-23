"use client";

import Link from "next/link";
import { useAuth } from "@/context/auth-context";
import { Button } from "@/components/ui/button";

export default function Home() {
  const { user, loading } = useAuth();

  return (
    <main className="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center px-4 py-16 sm:px-6 sm:py-24 lg:py-28">
      <div className="mx-auto max-w-3xl text-center">
        {/* Brand */}
        <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl md:text-6xl">
          AnalytIQ
        </h1>

        {/* Tagline */}
        <p className="mt-4 text-xl font-semibold tracking-tight text-foreground/90 sm:text-2xl md:text-3xl">
          Intelligent Analysis. Verified Insights.
        </p>

        {/* Description */}
        <p className="mt-6 text-base leading-relaxed text-muted-foreground sm:text-lg md:text-xl">
          An evidence-grounded, multi-agent AI data analytics platform that combines autonomous reasoning with deterministic, verified data processing.
        </p>

        {/* Architectural Principles Pills */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-2 sm:gap-3 text-xs sm:text-sm font-medium text-foreground/80">
          <span className="rounded-full border border-border bg-card px-3.5 py-1.5 shadow-2xs">
            AI-Driven Planning
          </span>
          <span className="rounded-full border border-border bg-card px-3.5 py-1.5 shadow-2xs">
            Deterministic Tools
          </span>
          <span className="rounded-full border border-border bg-card px-3.5 py-1.5 shadow-2xs">
            Evidence Validation
          </span>
          <span className="rounded-full border border-border bg-card px-3.5 py-1.5 shadow-2xs">
            Clear Explanations
          </span>
        </div>

        {/* Action Buttons */}
        <div className="mt-8 sm:mt-10 flex flex-col sm:flex-row items-center justify-center gap-3.5 sm:gap-4">
          {loading ? (
            <div className="h-11 w-36 animate-pulse rounded-lg bg-muted" />
          ) : user ? (
            <Link href="/dashboard" className="w-full sm:w-auto">
              <Button size="lg" className="w-full sm:w-auto cursor-pointer">
                Go to Dashboard
              </Button>
            </Link>
          ) : (
            <>
              <Link href="/register" className="w-full sm:w-auto">
                <Button size="lg" className="w-full sm:w-auto cursor-pointer">
                  Get Started
                </Button>
              </Link>
              <Link href="/login" className="w-full sm:w-auto">
                <Button variant="outline" size="lg" className="w-full sm:w-auto cursor-pointer">
                  Sign In
                </Button>
              </Link>
            </>
          )}
        </div>

        {/* Status badge */}
        <div className="mt-10 sm:mt-14 inline-flex items-center gap-2.5 rounded-full border border-border bg-muted/80 px-4 py-2 text-xs sm:text-sm font-medium text-foreground/80 shadow-2xs">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20"
            aria-hidden="true"
          />
          <span>Under Development — Milestone M1: Authentication Active</span>
        </div>
      </div>
    </main>
  );
}

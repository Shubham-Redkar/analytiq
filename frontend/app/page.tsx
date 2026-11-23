"use client";

import Link from "next/link";
import { useAuth } from "@/context/auth-context";
import { Button } from "@/components/ui/button";

export default function Home() {
  const { user, loading } = useAuth();

  return (
    <main className="flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center bg-background px-6 py-24">
      <div className="mx-auto max-w-2xl text-center">
        {/* Brand */}
        <h1 className="text-5xl font-bold tracking-tight text-foreground sm:text-6xl">
          AnalytIQ
        </h1>

        {/* Tagline */}
        <p className="mt-4 text-xl font-medium text-muted-foreground sm:text-2xl">
          Intelligent Analysis. Verified Insights.
        </p>

        {/* Description */}
        <p className="mt-6 text-base leading-relaxed text-muted-foreground sm:text-lg">
          An evidence-grounded, multi-agent AI data analytics platform that combines AI-driven reasoning with deterministic data processing.
        </p>

        {/* Action Buttons */}
        <div className="mt-8 flex items-center justify-center gap-4">
          {loading ? (
            <div className="h-9 w-32 animate-pulse rounded-md bg-muted" />
          ) : user ? (
            <Link href="/dashboard">
              <Button size="lg" className="cursor-pointer">
                Go to Dashboard
              </Button>
            </Link>
          ) : (
            <div className="flex items-center gap-3">
              <Link href="/login">
                <Button variant="outline" size="lg" className="cursor-pointer">
                  Sign In
                </Button>
              </Link>
              <Link href="/register">
                <Button size="lg" className="cursor-pointer">
                  Get Started
                </Button>
              </Link>
            </div>
          )}
        </div>

        {/* Status badge */}
        <div className="mt-12 inline-flex items-center gap-2 rounded-full border border-border bg-muted px-4 py-2 text-sm text-muted-foreground">
          <span
            className="inline-block h-2 w-2 rounded-full bg-emerald-500"
            aria-hidden="true"
          />
          <span>Under Development — Milestone M1: Authentication & Application Foundation</span>
        </div>
      </div>
    </main>
  );
}

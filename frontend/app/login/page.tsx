"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectPath = searchParams.get("redirect") || "/dashboard";

  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(email, password);
      router.push(redirectPath);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.category === "throttled") {
          setError(
            err.message ||
              "Account is temporarily locked due to multiple failed login attempts. Please try again later."
          );
        } else if (err.category === "credentials") {
          setError("Invalid email or password.");
        } else if (err.category === "security") {
          setError("Security validation failed. Please refresh the page and try again.");
        } else if (err.category === "network") {
          setError("Unable to connect to the server. Please verify your connection.");
        } else if (err.category === "server") {
          setError("A server error occurred. Please try again shortly.");
        } else {
          setError(err.message || "An unexpected error occurred during login.");
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred during login.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
      <div className="mb-6 text-center">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-card-foreground">
          Sign in to AnalytIQ
        </h1>
        <p className="mt-2 text-sm sm:text-base text-muted-foreground">
          Enter your credentials to access your analytics workspace
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 rounded-lg border border-destructive/30 bg-destructive/10 p-3.5 text-sm sm:text-[15px] font-medium text-destructive"
        >
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5">
        <div>
          <label
            htmlFor="email"
            className="block text-sm sm:text-[15px] font-medium text-foreground mb-1.5"
          >
            Email address
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="analyst@example.com"
            className="w-full h-10 sm:h-11 rounded-lg border border-input bg-background px-3.5 py-2 text-sm sm:text-base text-foreground shadow-2xs placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-ring transition-colors"
          />
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-sm sm:text-[15px] font-medium text-foreground mb-1.5"
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full h-10 sm:h-11 rounded-lg border border-input bg-background px-3.5 py-2 text-sm sm:text-base text-foreground shadow-2xs placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-ring transition-colors"
          />
        </div>

        <Button
          type="submit"
          disabled={isSubmitting}
          className="w-full h-10 sm:h-11 text-sm sm:text-base font-semibold cursor-pointer mt-2"
        >
          {isSubmitting ? "Signing in..." : "Sign in"}
        </Button>
      </form>

      <div className="mt-6 text-center text-sm sm:text-[15px] text-muted-foreground">
        Don&apos;t have an account?{" "}
        <Link
          href="/register"
          className="font-semibold text-primary hover:underline transition-colors"
        >
          Create one now
        </Link>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="flex min-h-[calc(100vh-4rem)] items-center justify-center p-4 sm:p-6">
      <Suspense
        fallback={
          <div className="h-72 w-full max-w-md animate-pulse rounded-2xl bg-muted" />
        }
      >
        <LoginForm />
      </Suspense>
    </main>
  );
}

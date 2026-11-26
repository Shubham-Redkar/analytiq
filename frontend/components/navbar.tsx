"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { Button } from "@/components/ui/button";

export function Navbar() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  const isDashboard = pathname === "/dashboard";
  const isDatasets = pathname?.startsWith("/datasets");
  const isAnalysis = pathname?.startsWith("/analysis");
  const isReports = pathname?.startsWith("/reports");

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
              AnalytIQ
            </span>
          </Link>
          {user && (
            <nav
              className="flex items-center gap-6 text-sm sm:text-base font-medium"
              aria-label="Main Navigation"
            >
              <Link
                href="/dashboard"
                aria-current={isDashboard ? "page" : undefined}
                className={`transition-colors hover:text-foreground ${
                  isDashboard
                    ? "text-foreground font-semibold"
                    : "text-muted-foreground font-medium"
                }`}
              >
                Dashboard
              </Link>
              <Link
                href="/datasets"
                aria-current={isDatasets ? "page" : undefined}
                className={`transition-colors hover:text-foreground ${
                  isDatasets ? "text-foreground font-semibold" : "text-muted-foreground font-medium"
                }`}
              >
                Datasets
              </Link>
              <Link
                href="/analysis"
                aria-current={isAnalysis ? "page" : undefined}
                className={`transition-colors hover:text-foreground ${
                  isAnalysis ? "text-foreground font-semibold" : "text-muted-foreground font-medium"
                }`}
              >
                Analysis
              </Link>
              <Link
                href="/reports"
                aria-current={isReports ? "page" : undefined}
                className={`transition-colors hover:text-foreground ${
                  isReports ? "text-foreground font-semibold" : "text-muted-foreground font-medium"
                }`}
              >
                Reports
              </Link>
            </nav>
          )}
        </div>

        <div className="flex items-center gap-3">
          {loading ? (
            <div className="h-9 w-24 animate-pulse rounded-lg bg-muted" />
          ) : user ? (
            <div className="flex items-center gap-4">
              <span className="hidden md:inline-block text-sm sm:text-base font-medium text-foreground">
                {user.display_name}
              </span>
              <Button variant="outline" size="sm" onClick={handleLogout} className="cursor-pointer">
                Sign out
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2 sm:gap-3">
              <Link href="/login">
                <Button variant="ghost" size="sm" className="cursor-pointer">
                  Sign in
                </Button>
              </Link>
              <Link href="/register">
                <Button size="sm" className="cursor-pointer">
                  Get Started
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

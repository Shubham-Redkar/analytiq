"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { Button } from "@/components/ui/button";

export function Navbar() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-lg font-bold tracking-tight text-foreground">
              AnalytIQ
            </span>
            <span className="hidden rounded bg-primary/10 px-1.5 py-0.5 text-xs font-medium text-primary sm:inline-block">
              v1.0-dev
            </span>
          </Link>
          {user && (
            <nav className="flex items-center gap-4 text-sm font-medium">
              <Link
                href="/dashboard"
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                Dashboard
              </Link>
            </nav>
          )}
        </div>

        <div className="flex items-center gap-3">
          {loading ? (
            <div className="h-8 w-20 animate-pulse rounded-md bg-muted" />
          ) : user ? (
            <div className="flex items-center gap-3">
              <span className="hidden text-sm text-muted-foreground md:inline-block">
                {user.display_name}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className="cursor-pointer"
              >
                Sign out
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
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

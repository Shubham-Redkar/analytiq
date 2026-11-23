export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-background px-6 py-24">
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
          An evidence-grounded, multi-agent AI data analytics platform.
        </p>

        {/* Status badge */}
        <div className="mt-10 inline-flex items-center gap-2 rounded-full border border-border bg-muted px-4 py-2 text-sm text-muted-foreground">
          <span
            className="inline-block h-2 w-2 rounded-full bg-amber-500"
            aria-hidden="true"
          />
          <span>Under Development — M0 Engineering Foundation</span>
        </div>
      </div>
    </main>
  );
}

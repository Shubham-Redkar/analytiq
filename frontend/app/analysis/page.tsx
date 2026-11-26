"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Navbar } from "../../components/navbar";
import { AnalysisWorkspace } from "../../components/analysis/analysis-workspace";
import { useAuth } from "@/context/auth-context";
import { api } from "../../lib/api";
import type { Dataset } from "../../lib/types";

function AnalysisContent() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedDatasetId = searchParams.get("dataset_id");

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login?redirect=/analysis");
    }
  }, [user, loading, router]);

  useEffect(() => {
    let ignore = false;
    async function loadDatasets() {
      if (!user) return;
      try {
        setDatasetsLoading(true);
        const res = await api.listDatasets(1, 100);
        if (!ignore) {
          setDatasets(res.items || []);
        }
      } catch {
        // Handled in workspace empty state
      } finally {
        if (!ignore) {
          setDatasetsLoading(false);
        }
      }
    }

    if (user) {
      void loadDatasets();
    }
    return () => {
      ignore = true;
    };
  }, [user]);

  if (loading || (datasetsLoading && !datasets.length)) {
    return (
      <div className="flex flex-1 items-center justify-center py-24">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <AnalysisWorkspace
      initialDatasets={datasets}
      selectedDatasetId={requestedDatasetId}
    />
  );
}

export default function AnalysisPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navbar />
      <Suspense
        fallback={
          <div className="flex flex-1 items-center justify-center py-24">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        }
      >
        <AnalysisContent />
      </Suspense>
    </div>
  );
}

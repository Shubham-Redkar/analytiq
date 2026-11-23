"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  FileSpreadsheet,
  FileText,
  UploadCloud,
  X,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function UploadDatasetPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login?redirect=/datasets/upload");
    }
  }, [user, authLoading, router]);

  const validateAndSetFile = (selectedFile: File) => {
    setError(null);
    const validExtensions = [".csv", ".xlsx"];
    const ext = selectedFile.name.substring(selectedFile.name.lastIndexOf(".")).toLowerCase();

    if (!validExtensions.includes(ext)) {
      setError("Unsupported file format. Please upload a .csv or .xlsx file.");
      return;
    }

    if (selectedFile.size > 25 * 1024 * 1024) {
      setError("File exceeds the maximum upload size limit of 25 MiB.");
      return;
    }

    setFile(selectedFile);
    if (!name) {
      const defaultName = selectedFile.name.substring(0, selectedFile.name.lastIndexOf("."));
      setName(defaultName);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a dataset file to upload.");
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      const dataset = await api.uploadDataset(file, name);
      router.push(`/datasets/${dataset.id}`);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred during dataset ingestion. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading || !user) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="h-64 animate-pulse rounded-2xl bg-muted" />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <Link
          href="/datasets"
          className="inline-flex items-center text-sm font-medium text-muted-foreground hover:text-foreground transition-colors mb-4"
        >
          <ArrowLeft className="mr-1.5 h-4 w-4" />
          Back to datasets
        </Link>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
          Upload Dataset
        </h1>
        <p className="mt-1.5 text-sm sm:text-base text-muted-foreground">
          Upload a structured CSV or XLSX file. We will infer the schema and calculate deterministic statistics.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-6 flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold">Upload failed</h4>
            <p className="mt-0.5">{error}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Drag and Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 sm:p-12 text-center transition-colors ${
            isDragging
              ? "border-primary bg-primary/5"
              : "border-border/80 hover:border-border hover:bg-muted/10"
          }`}
        >
          <input
            id="file-upload"
            type="file"
            accept=".csv,.xlsx"
            onChange={handleFileInputChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            aria-label="Upload dataset file"
          />

          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground mb-4">
            <UploadCloud className="h-7 w-7 text-foreground/70" />
          </div>

          <h3 className="text-base sm:text-lg font-semibold text-foreground">
            Drop your dataset file here, or <span className="text-primary hover:underline">browse</span>
          </h3>
          <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
            Supported formats: CSV (UTF-8) and XLSX (first worksheet). Max file size: 25 MiB.
          </p>
        </div>

        {/* Selected File Card */}
        {file && (
          <div className="flex items-center justify-between rounded-xl border border-border bg-card p-4 shadow-2xs">
            <div className="flex items-center gap-3 truncate">
              {file.name.endsWith(".csv") ? (
                <FileText className="h-6 w-6 text-primary shrink-0" />
              ) : (
                <FileSpreadsheet className="h-6 w-6 text-emerald-600 shrink-0" />
              )}
              <div className="truncate">
                <p className="text-sm font-semibold text-foreground truncate">{file.name}</p>
                <p className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setFile(null);
                setName("");
              }}
              className="cursor-pointer text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Dataset Display Name */}
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-foreground mb-1.5">
            Dataset Name (optional)
          </label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. 2026 Sales Invoices"
            className="w-full h-10 rounded-lg border border-input bg-background px-3.5 py-2 text-sm text-foreground shadow-2xs placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
          />
        </div>

        {/* Submit Button */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-border/80">
          <Link href="/datasets">
            <Button type="button" variant="outline" className="cursor-pointer">
              Cancel
            </Button>
          </Link>
          <Button
            type="submit"
            disabled={!file || isSubmitting}
            className="cursor-pointer font-semibold shadow-xs min-w-[140px]"
          >
            {isSubmitting ? "Ingesting & profiling..." : "Ingest Dataset"}
          </Button>
        </div>
      </form>
    </main>
  );
}

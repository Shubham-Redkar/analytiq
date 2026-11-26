/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom/vitest" />

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import DatasetsListPage from "../app/datasets/page";
import UploadDatasetPage from "../app/datasets/upload/page";
import { DatasetDetailContent } from "../app/datasets/[id]/page";
import * as authContext from "../context/auth-context";
import { api, ApiError } from "../lib/api";
import type { Dataset, DatasetQualityResponse } from "../lib/types";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

const mockUser = {
  id: "user-uuid-1234",
  email: "analyst@example.com",
  display_name: "Data Analyst",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

const sampleDataset: Dataset = {
  id: "d1234567-89ab-cdef-0123-456789abcdef",
  name: "Q4 Transactions",
  original_filename: "transactions.csv",
  file_format: "CSV",
  file_size_bytes: 4096,
  row_count: 100,
  column_count: 3,
  status: "ready",
  created_at: "2026-01-01T10:00:00Z",
  updated_at: "2026-01-01T10:00:00Z",
  quality_summary: {
    total_rows: 100,
    total_columns: 3,
    duplicate_rows: 2,
    missing_cells: 5,
    missing_percentage: 1.67,
    columns_with_missing: 1,
    all_null_columns_count: 0,
    constant_columns_count: 0,
  },
  schema_json: {
    columns: [
      { name: "id", logical_type: "integer", duckdb_type: "BIGINT", nullable: false },
      { name: "item", logical_type: "string", duckdb_type: "VARCHAR", nullable: false },
      { name: "amount", logical_type: "float", duckdb_type: "DOUBLE", nullable: true },
    ],
    row_count: 100,
    column_count: 3,
  },
};

const sampleQualityResponse: DatasetQualityResponse = {
  summary: {
    total_rows: 100,
    total_columns: 3,
    duplicate_rows: 2,
    missing_cells: 5,
    missing_percentage: 1.67,
    columns_with_missing: 1,
    all_null_columns_count: 0,
    constant_columns_count: 0,
  },
  quality_findings: [
    {
      type: "duplicate_rows",
      severity: "warning",
      message: "2 duplicate rows detected across dataset.",
    },
    {
      type: "missing_values",
      severity: "warning",
      message: "1 column contains missing values, affecting 5 cells.",
    },
  ],
  columns_breakdown: [
    {
      name: "amount",
      logical_type: "float",
      null_count: 5,
      null_percentage: 5.0,
      distinct_count: 90,
    },
  ],
};

describe("M2 Dataset Experience", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });
  });

  describe("DatasetsListPage", () => {
    it("renders empty state when no datasets exist", async () => {
      vi.spyOn(api, "listDatasets").mockResolvedValue({
        items: [],
        total: 0,
        page: 1,
        page_size: 10,
        total_pages: 0,
      });

      render(<DatasetsListPage />);

      await waitFor(() => {
        expect(screen.getByText(/no datasets uploaded yet/i)).toBeInTheDocument();
        expect(
          screen.getByRole("button", { name: /upload your first dataset/i })
        ).toBeInTheDocument();
      });
    });

    it("renders dataset table with rows and metadata", async () => {
      vi.spyOn(api, "listDatasets").mockResolvedValue({
        items: [sampleDataset],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1,
      });

      render(<DatasetsListPage />);

      await waitFor(() => {
        expect(screen.getByText("Q4 Transactions")).toBeInTheDocument();
        expect(screen.getByText("CSV")).toBeInTheDocument();
        expect(screen.getByText("100")).toBeInTheDocument();
      });
    });

    it("opens delete confirmation modal with dataset name and triggers deletion", async () => {
      vi.spyOn(api, "listDatasets").mockResolvedValue({
        items: [sampleDataset],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1,
      });
      const mockDelete = vi.spyOn(api, "deleteDataset").mockResolvedValue({
        status: "ok",
        message: "Deleted",
        dataset_id: sampleDataset.id,
      });

      render(<DatasetsListPage />);

      await waitFor(() => {
        expect(screen.getByText("Q4 Transactions")).toBeInTheDocument();
      });

      // Click delete trash icon
      const deleteButtons = screen.getAllByRole("button");
      const trashButton = deleteButtons.find((btn) => btn.querySelector("svg.lucide-trash-2"));
      expect(trashButton).toBeDefined();
      await userEvent.click(trashButton!);

      // Modal appears with dataset name
      expect(screen.getByText(/are you sure you want to delete/i)).toBeInTheDocument();
      expect(screen.getByText(/"Q4 Transactions"/i)).toBeInTheDocument();

      // Confirm delete
      const confirmButton = screen.getByRole("button", { name: /delete permanently/i });
      await userEvent.click(confirmButton);

      expect(mockDelete).toHaveBeenCalledWith(sampleDataset.id);
    });

    it("displays error banner when dataset deletion fails", async () => {
      vi.spyOn(api, "listDatasets").mockResolvedValue({
        items: [sampleDataset],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1,
      });
      vi.spyOn(api, "deleteDataset").mockRejectedValue(
        new ApiError("Database connection dropped", 500)
      );

      render(<DatasetsListPage />);

      await waitFor(() => {
        expect(screen.getByText("Q4 Transactions")).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole("button");
      const trashButton = deleteButtons.find((btn) => btn.querySelector("svg.lucide-trash-2"));
      await userEvent.click(trashButton!);

      const confirmButton = screen.getByRole("button", { name: /delete permanently/i });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText("Database connection dropped")).toBeInTheDocument();
      });
    });
  });

  describe("UploadDatasetPage", () => {
    it("renders drag and drop zone and format guidance", () => {
      render(<UploadDatasetPage />);

      expect(screen.getByRole("heading", { name: /upload dataset/i })).toBeInTheDocument();
      expect(screen.getByText(/supported formats: csv/i)).toBeInTheDocument();
    });

    it("rejects unsupported file format", async () => {
      render(<UploadDatasetPage />);

      const badFile = new File(['{"bad": true}'], "data.json", { type: "application/json" });
      const input = screen.getByLabelText(/upload dataset file/i);

      fireEvent.change(input, { target: { files: [badFile] } });

      expect(
        await screen.findByText(/unsupported file format\. please upload a \.csv or \.xlsx file/i)
      ).toBeInTheDocument();
    });

    it("submits valid file and navigates to detail page on success", async () => {
      const mockUpload = vi.spyOn(api, "uploadDataset").mockResolvedValue(sampleDataset);

      render(<UploadDatasetPage />);

      const validFile = new File(["id,name\n1,Alpha"], "sales.csv", { type: "text/csv" });
      const input = screen.getByLabelText(/upload dataset file/i);

      await userEvent.upload(input, validFile);

      const submitButton = screen.getByRole("button", { name: /ingest dataset/i });
      await userEvent.click(submitButton);

      expect(mockUpload).toHaveBeenCalledWith(validFile, "sales");
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith(`/datasets/${sampleDataset.id}`);
      });
    });
  });

  describe("DatasetDetailPage", () => {
    it("renders Missing Values KPI card instead of internal Parquet details", async () => {
      vi.spyOn(api, "getDataset").mockResolvedValue(sampleDataset);
      vi.spyOn(api, "getDatasetPreview").mockResolvedValue({
        columns: [],
        rows: [],
        total_rows: 0,
        offset: 0,
        limit: 25,
      });

      render(<DatasetDetailContent id={sampleDataset.id} />);

      await waitFor(() => {
        expect(screen.getByText("Missing Values")).toBeInTheDocument();
        expect(screen.getByText("5")).toBeInTheDocument();
        expect(screen.getByText("(1.67%)")).toBeInTheDocument();
      });
    });

    it("renders friendly type labels and right-aligned numeric headers in preview", async () => {
      vi.spyOn(api, "getDataset").mockResolvedValue(sampleDataset);
      vi.spyOn(api, "getDatasetPreview").mockResolvedValue({
        columns: [
          { name: "id", duckdb_type: "BIGINT", logical_type: "integer" },
          { name: "item", duckdb_type: "VARCHAR", logical_type: "string" },
          { name: "amount", duckdb_type: "DOUBLE", logical_type: "float" },
        ],
        rows: [
          { id: 1, item: "Widget", amount: 19.99 },
          { id: 2, item: "Gadget", amount: null },
        ],
        total_rows: 2,
        offset: 0,
        limit: 25,
      });

      render(<DatasetDetailContent id={sampleDataset.id} />);

      await waitFor(() => {
        expect(screen.getByText("Widget")).toBeInTheDocument();
      });

      // Friendly type badges
      expect(screen.getByText("Integer")).toBeInTheDocument();
      expect(screen.getByText("Text")).toBeInTheDocument();
      expect(screen.getByText("Decimal")).toBeInTheDocument();

      // Distinct null styling
      expect(screen.getByText("null")).toHaveClass("italic");
    });

    it("filters columns by search query in Profiling tab", async () => {
      vi.spyOn(api, "getDataset").mockResolvedValue(sampleDataset);
      vi.spyOn(api, "getDatasetPreview").mockResolvedValue({
        columns: [],
        rows: [],
        total_rows: 0,
        offset: 0,
        limit: 25,
      });
      vi.spyOn(api, "getDatasetProfile").mockResolvedValue({
        summary: sampleDataset.quality_summary!,
        columns: [
          {
            name: "id",
            logical_type: "integer",
            null_count: 0,
            null_percentage: 0,
            distinct_count: 100,
            min: 1,
            max: 100,
            mean: 50.5,
            top_values: [],
          },
          {
            name: "amount",
            logical_type: "float",
            null_count: 5,
            null_percentage: 5.0,
            distinct_count: 90,
            min: 10.0,
            max: 500.0,
            mean: 120.4,
            top_values: [],
          },
        ],
      });

      render(<DatasetDetailContent id={sampleDataset.id} />);

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "Q4 Transactions" })).toBeInTheDocument();
      });

      // Switch to Profile tab
      const profileTab = screen.getByRole("button", { name: /column profiling/i });
      await userEvent.click(profileTab);

      // Verify initial columns
      expect(await screen.findByRole("heading", { name: "id" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "amount" })).toBeInTheDocument();

      // Type search filter
      const searchInput = screen.getByLabelText(/search columns by name/i);
      await userEvent.type(searchInput, "amou");

      expect(screen.queryByRole("heading", { name: "id" })).not.toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "amount" })).toBeInTheDocument();

      // Search with no matches
      await userEvent.clear(searchInput);
      await userEvent.type(searchInput, "nonexistent");

      expect(screen.getByText(/no columns match your filter criteria/i)).toBeInTheDocument();
    });

    it("displays discrete categorical frequency summary for discrete integer columns", async () => {
      vi.spyOn(api, "getDataset").mockResolvedValue(sampleDataset);
      vi.spyOn(api, "getDatasetPreview").mockResolvedValue({
        columns: [],
        rows: [],
        total_rows: 0,
        offset: 0,
        limit: 25,
      });
      vi.spyOn(api, "getDatasetProfile").mockResolvedValue({
        summary: sampleDataset.quality_summary!,
        columns: [
          {
            name: "status_code",
            logical_type: "integer",
            null_count: 0,
            null_percentage: 0,
            distinct_count: 3,
            min: 1,
            max: 3,
            mean: 1.8,
            is_discrete: true,
            top_values: [
              { value: "1", count: 60 },
              { value: "2", count: 30 },
              { value: "3", count: 10 },
            ],
          },
        ],
      });

      render(<DatasetDetailContent id={sampleDataset.id} />);

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "Q4 Transactions" })).toBeInTheDocument();
      });

      const profileTab = screen.getByRole("button", { name: /column profiling/i });
      await userEvent.click(profileTab);

      await waitFor(() => {
        expect(screen.getByText(/descriptive frequency summary:/i)).toBeInTheDocument();
        expect(screen.getByText(/arithmetic mean:/i)).toBeInTheDocument();
      });
    });

    it("displays actionable per-column missing values breakdown in Quality tab", async () => {
      vi.spyOn(api, "getDataset").mockResolvedValue(sampleDataset);
      vi.spyOn(api, "getDatasetPreview").mockResolvedValue({
        columns: [],
        rows: [],
        total_rows: 0,
        offset: 0,
        limit: 25,
      });
      vi.spyOn(api, "getDatasetQuality").mockResolvedValue(sampleQualityResponse);

      render(<DatasetDetailContent id={sampleDataset.id} />);

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "Q4 Transactions" })).toBeInTheDocument();
      });

      const qualityTab = screen.getByRole("button", { name: /data quality/i });
      await userEvent.click(qualityTab);

      await waitFor(() => {
        expect(screen.getByText(/missing values by column/i)).toBeInTheDocument();
        expect(screen.getByText("amount")).toBeInTheDocument();
        expect(screen.getByText("5%")).toBeInTheDocument();
        expect(
          screen.getByText(/1 column contains missing values, affecting 5 cells/i)
        ).toBeInTheDocument();
        expect(screen.getByText(/understanding quality indicators/i)).toBeInTheDocument();
      });
    });

    it("supports full-dataset server-side pagination with First, Previous, Next, and Last controls", async () => {
      const largeDataset: Dataset = {
        ...sampleDataset,
        row_count: 2500,
      };
      vi.spyOn(api, "getDataset").mockResolvedValue(largeDataset);

      const mockPreview = vi
        .spyOn(api, "getDatasetPreview")
        .mockImplementation(async (_id, offset) => ({
          columns: [{ name: "id", duckdb_type: "BIGINT", logical_type: "integer" }],
          rows: Array.from({ length: 25 }, (_, i) => ({ id: (offset || 0) + i + 1 })),
          total_rows: 2500,
          offset: offset || 0,
          limit: 25,
          has_next: (offset || 0) + 25 < 2500,
          has_previous: (offset || 0) > 0,
        }));

      render(<DatasetDetailContent id={largeDataset.id} />);

      await waitFor(() => {
        expect(screen.getByText(/showing rows 1–25 of 2,500/i)).toBeInTheDocument();
        expect(screen.getByText(/page 1 of 100/i)).toBeInTheDocument();
      });

      // First and Previous should be disabled on page 1
      expect(screen.getByRole("button", { name: /first page/i })).toBeDisabled();
      expect(screen.getByRole("button", { name: /previous page/i })).toBeDisabled();

      // Next and Last should be enabled
      const nextBtn = screen.getByRole("button", { name: /next page/i });
      const lastBtn = screen.getByRole("button", { name: /last page/i });
      expect(nextBtn).toBeEnabled();
      expect(lastBtn).toBeEnabled();

      // Click Next -> moves to page 2 (offset 25)
      await userEvent.click(nextBtn);
      await waitFor(() => {
        expect(mockPreview).toHaveBeenCalledWith(largeDataset.id, 25, 25);
        expect(screen.getByText(/showing rows 26–50 of 2,500/i)).toBeInTheDocument();
        expect(screen.getByText(/page 2 of 100/i)).toBeInTheDocument();
      });

      // Click Last -> moves to page 100 (offset 2475)
      await userEvent.click(lastBtn);
      await waitFor(() => {
        expect(mockPreview).toHaveBeenCalledWith(largeDataset.id, 2475, 25);
        expect(screen.getByText(/showing rows 2,476–2,500 of 2,500/i)).toBeInTheDocument();
        expect(screen.getByText(/page 100 of 100/i)).toBeInTheDocument();
      });

      // On final page, Next and Last are disabled
      expect(screen.getByRole("button", { name: /next page/i })).toBeDisabled();
      expect(screen.getByRole("button", { name: /last page/i })).toBeDisabled();

      // Click First -> returns to page 1 (offset 0)
      const firstBtn = screen.getByRole("button", { name: /first page/i });
      expect(firstBtn).toBeEnabled();
      await userEvent.click(firstBtn);
      await waitFor(() => {
        expect(mockPreview).toHaveBeenCalledWith(largeDataset.id, 0, 25);
        expect(screen.getByText(/showing rows 1–25 of 2,500/i)).toBeInTheDocument();
      });
    });

    it("displays deletion incomplete banner when dataset is in deletion_failed status", async () => {
      const failedDataset: Dataset = {
        ...sampleDataset,
        status: "deletion_failed",
      };
      vi.spyOn(api, "getDataset").mockResolvedValue(failedDataset);
      vi.spyOn(api, "getDatasetPreview").mockResolvedValue({
        columns: [],
        rows: [],
        total_rows: 0,
        offset: 0,
        limit: 25,
      });

      render(<DatasetDetailContent id={failedDataset.id} />);

      await waitFor(() => {
        expect(screen.getByText(/dataset deletion incomplete/i)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /retry deletion/i })).toBeInTheDocument();
      });
    });

    it("displays 'Not computed' when quality_summary is null for older datasets", async () => {
      const legacyDataset: Dataset = {
        ...sampleDataset,
        quality_summary: null,
      };
      vi.spyOn(api, "getDataset").mockResolvedValue(legacyDataset);
      vi.spyOn(api, "getDatasetPreview").mockResolvedValue({
        columns: [],
        rows: [],
        total_rows: 0,
        offset: 0,
        limit: 25,
      });

      render(<DatasetDetailContent id={legacyDataset.id} />);

      await waitFor(() => {
        expect(screen.getByText("Missing Values")).toBeInTheDocument();
        expect(screen.getByText("Not computed")).toBeInTheDocument();
      });
    });

    it("allows dismissing the horizontal scroll hint banner on wide tables", async () => {
      vi.spyOn(api, "getDataset").mockResolvedValue(sampleDataset);
      vi.spyOn(api, "getDatasetPreview").mockResolvedValue({
        columns: [
          { name: "c1", duckdb_type: "VARCHAR", logical_type: "string" },
          { name: "c2", duckdb_type: "VARCHAR", logical_type: "string" },
          { name: "c3", duckdb_type: "VARCHAR", logical_type: "string" },
          { name: "c4", duckdb_type: "VARCHAR", logical_type: "string" },
          { name: "c5", duckdb_type: "VARCHAR", logical_type: "string" },
          { name: "c6", duckdb_type: "VARCHAR", logical_type: "string" },
        ],
        rows: [{ c1: "a", c2: "b", c3: "c", c4: "d", c5: "e", c6: "f" }],
        total_rows: 1,
        offset: 0,
        limit: 25,
      });

      render(<DatasetDetailContent id={sampleDataset.id} />);

      await waitFor(() => {
        expect(
          screen.getByText(/horizontal scroll enabled for wide dataset viewing/i)
        ).toBeInTheDocument();
      });

      const dismissBtn = screen.getByRole("button", { name: /dismiss scroll hint/i });
      await userEvent.click(dismissBtn);

      expect(
        screen.queryByText(/horizontal scroll enabled for wide dataset viewing/i)
      ).not.toBeInTheDocument();
    });
  });
});

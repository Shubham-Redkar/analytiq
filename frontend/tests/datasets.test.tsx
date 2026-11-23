/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom/vitest" />

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import DatasetsListPage from "../app/datasets/page";
import UploadDatasetPage from "../app/datasets/upload/page";
import { DatasetDetailContent } from "../app/datasets/[id]/page";
import * as authContext from "../context/auth-context";
import { api } from "../lib/api";
import type { Dataset } from "../lib/types";

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
        expect(screen.getByRole("button", { name: /upload your first dataset/i })).toBeInTheDocument();
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

    it("opens delete confirmation modal and triggers deletion", async () => {
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

      // Modal appears
      expect(screen.getByText(/are you sure you want to delete/i)).toBeInTheDocument();

      // Confirm delete
      const confirmButton = screen.getByRole("button", { name: /delete permanently/i });
      await userEvent.click(confirmButton);

      expect(mockDelete).toHaveBeenCalledWith(sampleDataset.id);
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
    it("renders dataset detail with tabs and loads preview", async () => {
      vi.spyOn(api, "getDataset").mockResolvedValue(sampleDataset);
      vi.spyOn(api, "getDatasetPreview").mockResolvedValue({
        columns: [
          { name: "id", duckdb_type: "BIGINT" },
          { name: "item", duckdb_type: "VARCHAR" },
          { name: "amount", duckdb_type: "DOUBLE" },
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
        expect(screen.getByRole("heading", { name: "Q4 Transactions" })).toBeInTheDocument();
        expect(screen.getByText("Widget")).toBeInTheDocument();
        expect(screen.getByText("null")).toBeInTheDocument();
      });
    });

    it("switches to Schema tab", async () => {
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
        expect(screen.getByRole("heading", { name: "Q4 Transactions" })).toBeInTheDocument();
      });

      const schemaTab = screen.getByRole("button", { name: /schema definition/i });
      await userEvent.click(schemaTab);

      expect(screen.getByText("DuckDB Engine Type")).toBeInTheDocument();
      expect(screen.getByText("BIGINT")).toBeInTheDocument();
    });
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReportsListPage from "@/app/reports/page";
import * as authContext from "@/context/auth-context";
import { api } from "@/lib/api";
import type { ReportListResponse, ReportSummary } from "@/lib/report-types";

vi.mock("@/lib/api", () => ({
  api: {
    listReports: vi.fn(),
    duplicateReport: vi.fn(),
    deleteReport: vi.fn(),
    getReportPdfUrl: vi.fn((id: string) => `/api/v1/reports/${id}/export/pdf`),
    getReportCsvUrl: vi.fn((id: string) => `/api/v1/reports/${id}/export/csv`),
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
  usePathname: () => "/reports",
}));

const mockUser = {
  id: "u123",
  email: "reporter@example.com",
  display_name: "Lead Analyst",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

const mockReports: ReportSummary[] = [
  {
    id: "rep-1",
    dataset_id: "ds-1",
    dataset_name: "Titanic Exploration",
    analysis_session_id: "sess-1",
    title: "Executive Passenger Report",
    description: "Detailed analysis of passenger class distribution.",
    status: "ready",
    revision: 1,
    created_at: "2026-11-26T10:00:00Z",
    updated_at: "2026-11-26T10:00:00Z",
  },
  {
    id: "rep-2",
    dataset_id: "ds-1",
    dataset_name: "Titanic Exploration",
    analysis_session_id: "sess-1",
    title: "Fare Variance by Class",
    description: null,
    status: "ready",
    revision: 2,
    created_at: "2026-11-26T11:00:00Z",
    updated_at: "2026-11-26T11:30:00Z",
  },
];

describe("ReportsListPage", () => {
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

  it("renders reports list successfully with reports data", async () => {
    vi.mocked(api.listReports).mockResolvedValueOnce({
      items: mockReports,
      total: 2,
      page: 1,
      page_size: 12,
      pages: 1,
    } as ReportListResponse);

    render(<ReportsListPage />);

    expect(screen.getByText(/Analytical Reports/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Executive Passenger Report")).toBeInTheDocument();
      expect(screen.getByText("Fare Variance by Class")).toBeInTheDocument();
    });

    expect(screen.getByText("2 reports total")).toBeInTheDocument();
  });

  it("renders empty state when no reports exist", async () => {
    vi.mocked(api.listReports).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 12,
      pages: 0,
    } as ReportListResponse);

    render(<ReportsListPage />);

    await waitFor(() => {
      expect(screen.getByText("No reports generated yet")).toBeInTheDocument();
      expect(screen.getByText("Go to Analysis Workspace")).toBeInTheDocument();
    });
  });

  it("filters reports by search query", async () => {
    vi.mocked(api.listReports).mockResolvedValueOnce({
      items: mockReports,
      total: 2,
      page: 1,
      page_size: 12,
      pages: 1,
    } as ReportListResponse);

    const user = userEvent.setup();

    render(<ReportsListPage />);

    await waitFor(() => {
      expect(screen.getByText("Executive Passenger Report")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search reports/i);
    await user.type(searchInput, "Variance");

    expect(screen.queryByText("Executive Passenger Report")).not.toBeInTheDocument();
    expect(screen.getByText("Fare Variance by Class")).toBeInTheDocument();
  });

  it("requires confirmation dialog before deleting a report", async () => {
    vi.mocked(api.listReports).mockResolvedValueOnce({
      items: mockReports,
      total: 2,
      page: 1,
      page_size: 12,
      pages: 1,
    } as ReportListResponse);
    vi.mocked(api.deleteReport).mockResolvedValueOnce(undefined);

    const user = userEvent.setup();

    render(<ReportsListPage />);

    await waitFor(() => {
      expect(screen.getByText("Executive Passenger Report")).toBeInTheDocument();
    });

    // Click delete on first report
    const deleteButtons = screen.getAllByTitle("Delete report");
    await user.click(deleteButtons[0]);

    // AlertDialog should appear
    expect(screen.getByText("Delete report?")).toBeInTheDocument();
    expect(
      screen.getByText(/This will permanently delete ‘Executive Passenger Report’/i)
    ).toBeInTheDocument();

    // Confirm deletion
    const confirmBtn = screen.getByRole("button", { name: "Delete report" });
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(api.deleteReport).toHaveBeenCalledWith("rep-1");
    });
  });
});

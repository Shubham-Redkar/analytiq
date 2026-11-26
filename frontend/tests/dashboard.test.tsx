/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom/vitest" />

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import DashboardPage from "../app/dashboard/page";
import { Navbar } from "../components/navbar";
import * as authContext from "../context/auth-context";
import { api } from "../lib/api";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  usePathname: () => "/dashboard",
}));

const mockUser = {
  id: "a1b2c3d4-e5f6-7890-1234-56789abcdef0",
  email: "analyst@example.com",
  display_name: "Lead Analyst",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

describe("Dashboard M2 Dynamic Integration & UX", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. renders dashboard for authenticated users", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });
    vi.spyOn(api, "listDatasets").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 1,
      total_pages: 0,
    });

    render(<DashboardPage />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByText(/your analytics workspace at a glance/i)).toBeInTheDocument();
  });

  it("2. personalized welcome uses the actual user display name", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });
    vi.spyOn(api, "listDatasets").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 1,
      total_pages: 0,
    });

    render(<DashboardPage />);
    expect(
      screen.getByRole("heading", { name: /welcome back, lead analyst/i })
    ).toBeInTheDocument();
  });

  it("3. handles missing display names gracefully without formatting artifacts", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: { ...mockUser, display_name: "" },
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });
    vi.spyOn(api, "listDatasets").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 1,
      total_pages: 0,
    });

    render(<DashboardPage />);
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Welcome back");
    expect(heading).not.toHaveTextContent("Welcome back,");
  });

  it("4. sign out remains functional in navbar and triggers logout redirect", async () => {
    const mockLogout = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: mockLogout,
      refresh: vi.fn(),
    });

    render(<Navbar />);
    const signoutButton = screen.getByRole("button", { name: /sign out/i });
    await userEvent.click(signoutButton);

    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("5. renders real dataset metrics when datasets exist", async () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });
    vi.spyOn(api, "listDatasets").mockResolvedValue({
      items: [
        {
          id: "123",
          name: "Sales",
          original_filename: "sales.csv",
          file_format: "CSV",
          file_size_bytes: 1024,
          row_count: 50,
          column_count: 3,
          status: "ready",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 3,
      page: 1,
      page_size: 1,
      total_pages: 3,
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/3 active datasets ready for exploration/i)).toBeInTheDocument();
    });
  });

  it("6. renders empty dataset state when total count is 0", async () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });
    vi.spyOn(api, "listDatasets").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 1,
      total_pages: 0,
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/no datasets connected yet/i)).toBeInTheDocument();
      expect(screen.getByText(/upload your first dataset/i)).toBeInTheDocument();
    });
  });

  it("7. provides functional Upload Dataset action button", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });
    vi.spyOn(api, "listDatasets").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 1,
      total_pages: 0,
    });

    render(<DashboardPage />);
    const uploadButtons = screen.getAllByRole("button", { name: /upload dataset/i });
    expect(uploadButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("8. analyses card uses polished product language without milestone jargon", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });
    vi.spyOn(api, "listDatasets").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 1,
      total_pages: 0,
    });
    vi.spyOn(api, "listAnalysisSessions").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 0,
    });

    render(<DashboardPage />);
    expect(screen.getByRole("heading", { name: "Analyses" })).toBeInTheDocument();
    expect(screen.getByText(/ask questions, formulate verified sql queries/i)).toBeInTheDocument();
  });

  it("9. dashboard redirects to login when unauthenticated", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: null,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(<DashboardPage />);
    expect(mockPush).toHaveBeenCalledWith("/login?redirect=/dashboard");
  });
});

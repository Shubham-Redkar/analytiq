/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom/vitest" />

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import DashboardPage from "../app/dashboard/page";
import { Navbar } from "../components/navbar";
import * as authContext from "../context/auth-context";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

const mockUser = {
  id: "a1b2c3d4-e5f6-7890-1234-56789abcdef0",
  email: "analyst@example.com",
  display_name: "Lead Analyst",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

describe("Dashboard UX & Product Readiness", () => {
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

    render(<DashboardPage />);
    expect(screen.getByRole("heading", { name: /welcome back, lead analyst/i })).toBeInTheDocument();
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

    render(<DashboardPage />);
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Welcome back");
    expect(heading).not.toHaveTextContent("Welcome back,");
  });

  it("4. exactly one visible Sign out action exists across the view", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    // Render together with Navbar as experienced by the user
    render(
      <div>
        <Navbar />
        <DashboardPage />
      </div>
    );

    const signoutButtons = screen.getAllByRole("button", { name: /sign out/i });
    expect(signoutButtons).toHaveLength(1);
  });

  it("5. sign out remains functional and triggers logout redirect", async () => {
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

  it("6. developer-facing milestone badges are absent from the dashboard", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(
      <div>
        <Navbar />
        <DashboardPage />
      </div>
    );

    expect(screen.queryByText(/^M1$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^M2$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^M3$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/m1 foundation/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/v1\.0-dev/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/authenticated session/i)).not.toBeInTheDocument();
  });

  it("7. user UUID is not displayed on the user-facing dashboard", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(<DashboardPage />);
    expect(screen.queryByText(mockUser.id)).not.toBeInTheDocument();
  });

  it("8. internal ownership and debug information is absent", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(<DashboardPage />);
    expect(screen.queryByText(/user identity & ownership foundation/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/account status/i)).not.toBeInTheDocument();
    expect(screen.queryByText(mockUser.email)).not.toBeInTheDocument();
  });

  it("9. product-oriented empty-state content renders cleanly", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(<DashboardPage />);
    expect(screen.getByRole("heading", { name: /your workspace is ready/i })).toBeInTheDocument();
    expect(
      screen.getByText(/your datasets and analytical insights will appear here once you begin working with data/i)
    ).toBeInTheDocument();
  });

  it("10. no fake numeric metrics are displayed as hardcoded counts", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(<DashboardPage />);
    // Workspace cards should provide descriptive readiness instead of hardcoded numbers
    expect(screen.getByText(/no datasets connected yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no analytical sessions yet/i)).toBeInTheDocument();
  });

  it("11. no disabled future-feature actions remain", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: mockUser,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(<DashboardPage />);
    expect(screen.queryByRole("button", { name: /upload dataset/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /new analysis/i })).not.toBeInTheDocument();
  });

  it("12. dashboard remains inaccessible without authentication and redirects to login", () => {
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

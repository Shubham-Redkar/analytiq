/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom/vitest" />

import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import DashboardPage from "../app/dashboard/page";
import * as authContext from "../context/auth-context";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects to login when unauthenticated", () => {
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

  it("renders authenticated user profile and dashboard shell", () => {
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: {
        id: "a1b2c3d4-e5f6-7890-1234-56789abcdef0",
        email: "analyst@example.com",
        display_name: "Lead Analyst",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(<DashboardPage />);

    expect(screen.getByRole("heading", { name: /welcome, lead analyst/i })).toBeInTheDocument();
    expect(screen.getByText("analyst@example.com")).toBeInTheDocument();
    expect(screen.getByText(/authenticated session/i)).toBeInTheDocument();
    expect(screen.getByText(/user identity & ownership foundation/i)).toBeInTheDocument();
    expect(screen.getByText(/no datasets connected yet/i)).toBeInTheDocument();
  });
});

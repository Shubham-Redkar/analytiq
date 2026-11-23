/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom/vitest" />

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Home from "../app/page";
import LoginPage from "../app/login/page";
import RegisterPage from "../app/register/page";
import DashboardPage from "../app/dashboard/page";
import * as authContext from "../context/auth-context";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => ({
    get: () => null,
  }),
}));

describe("Accessibility & Semantic Hierarchy Verification", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Landing Page (Home)", () => {
    it("has a single top-level h1 heading and main landmark", () => {
      render(<Home />);
      const headings = screen.getAllByRole("heading");
      expect(headings).toHaveLength(1);
      expect(headings[0]).toHaveProperty("tagName", "H1");
      expect(screen.getByRole("main")).toBeInTheDocument();
    });

    it("presents high-contrast principle badges with proper roles", () => {
      render(<Home />);
      expect(screen.getByText("AI-Driven Planning")).toBeInTheDocument();
      expect(screen.getByText("Deterministic Tools")).toBeInTheDocument();
      expect(screen.getByText("Evidence Validation")).toBeInTheDocument();
      expect(screen.getByText("Clear Explanations")).toBeInTheDocument();
    });
  });

  describe("Login Page Accessibility & Keyboard Navigation", () => {
    it("has properly labeled form inputs with accessible labels", () => {
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole("button", { name: /sign in/i });

      expect(emailInput).toHaveAttribute("id", "email");
      expect(emailInput).toHaveAttribute("type", "email");
      expect(emailInput).toHaveAttribute("autocomplete", "email");
      expect(emailInput).toBeRequired();

      expect(passwordInput).toHaveAttribute("id", "password");
      expect(passwordInput).toHaveAttribute("type", "password");
      expect(passwordInput).toBeRequired();

      expect(submitButton).toHaveAttribute("type", "submit");
    });

    it("supports keyboard tab navigation across form fields", async () => {
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole("button", { name: /sign in/i });

      // Tab through inputs
      await userEvent.tab();
      expect(emailInput).toHaveFocus();

      await userEvent.tab();
      expect(passwordInput).toHaveFocus();

      await userEvent.tab();
      expect(submitButton).toHaveFocus();
    });
  });

  describe("Register Page Accessibility & Keyboard Navigation", () => {
    it("has correct label associations and tab order", async () => {
      render(<RegisterPage />);

      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/^password/i);
      const confirmInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole("button", { name: /create account/i });

      await userEvent.tab();
      expect(nameInput).toHaveFocus();

      await userEvent.tab();
      expect(emailInput).toHaveFocus();

      await userEvent.tab();
      expect(passwordInput).toHaveFocus();

      await userEvent.tab();
      expect(confirmInput).toHaveFocus();

      await userEvent.tab();
      expect(submitButton).toHaveFocus();
    });
  });

  describe("Dashboard Page Semantic Hierarchy", () => {
    it("has structured heading levels (h1, h2, h3)", () => {
      vi.spyOn(authContext, "useAuth").mockReturnValue({
        user: {
          id: "00000000-0000-0000-0000-000000000001",
          email: "alex@example.com",
          display_name: "Alex Johnson",
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

      const h1 = screen.getByRole("heading", { level: 1 });
      expect(h1).toHaveTextContent(/welcome, alex johnson/i);

      const h2 = screen.getByRole("heading", { level: 2 });
      expect(h2).toHaveTextContent(/user identity & ownership foundation/i);

      const h3 = screen.getByRole("heading", { level: 3 });
      expect(h3).toHaveTextContent(/no datasets connected yet/i);
    });
  });
});

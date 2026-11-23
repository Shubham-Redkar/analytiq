/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom/vitest" />

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import LoginPage from "../app/login/page";
import RegisterPage from "../app/register/page";
import * as authContext from "../context/auth-context";
import { ApiError } from "../lib/api";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => ({
    get: (key: string) => (key === "redirect" ? "/dashboard" : null),
  }),
}));

describe("Authentication Pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("LoginPage", () => {
    it("renders login form with required fields", () => {
      render(<LoginPage />);

      expect(
        screen.getByRole("heading", { name: /sign in to analytiq/i })
      ).toBeInTheDocument();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /sign in/i })
      ).toBeInTheDocument();
    });

    it("displays error message when login fails", async () => {
      const mockLogin = vi.fn().mockRejectedValue(new Error("Invalid email or password."));
      vi.spyOn(authContext, "useAuth").mockReturnValue({
        user: null,
        loading: false,
        login: mockLogin,
        register: vi.fn(),
        logout: vi.fn(),
        refresh: vi.fn(),
      });

      render(<LoginPage />);

      await userEvent.type(screen.getByLabelText(/email address/i), "user@example.com");
      await userEvent.type(screen.getByLabelText(/password/i), "wrongpassword");
      await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent("Invalid email or password.");
      });
    });

    it("displays lockout message when account is throttled (HTTP 423)", async () => {
      const mockLogin = vi.fn().mockRejectedValue(
        new ApiError("Account temporarily locked due to too many failed login attempts.", 423)
      );
      vi.spyOn(authContext, "useAuth").mockReturnValue({
        user: null,
        loading: false,
        login: mockLogin,
        register: vi.fn(),
        logout: vi.fn(),
        refresh: vi.fn(),
      });

      render(<LoginPage />);

      await userEvent.type(screen.getByLabelText(/email address/i), "locked@example.com");
      await userEvent.type(screen.getByLabelText(/password/i), "wrongpassword");
      await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent(/temporarily locked/i);
      });
    });

    it("displays security message on CSRF failure (HTTP 403)", async () => {
      const mockLogin = vi.fn().mockRejectedValue(
        new ApiError("CSRF validation failed", 403)
      );
      vi.spyOn(authContext, "useAuth").mockReturnValue({
        user: null,
        loading: false,
        login: mockLogin,
        register: vi.fn(),
        logout: vi.fn(),
        refresh: vi.fn(),
      });

      render(<LoginPage />);

      await userEvent.type(screen.getByLabelText(/email address/i), "csrf@example.com");
      await userEvent.type(screen.getByLabelText(/password/i), "somepassword");
      await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent(/security validation failed/i);
      });
    });

    it("displays server error message on 500 status", async () => {
      const mockLogin = vi.fn().mockRejectedValue(
        new ApiError("Internal server error", 500)
      );
      vi.spyOn(authContext, "useAuth").mockReturnValue({
        user: null,
        loading: false,
        login: mockLogin,
        register: vi.fn(),
        logout: vi.fn(),
        refresh: vi.fn(),
      });

      render(<LoginPage />);

      await userEvent.type(screen.getByLabelText(/email address/i), "user@example.com");
      await userEvent.type(screen.getByLabelText(/password/i), "password123");
      await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent(/server error occurred/i);
      });
    });

    it("displays network error message on connection failure", async () => {
      const mockLogin = vi.fn().mockRejectedValue(
        new ApiError("Unable to connect to the server.", 0, "network")
      );
      vi.spyOn(authContext, "useAuth").mockReturnValue({
        user: null,
        loading: false,
        login: mockLogin,
        register: vi.fn(),
        logout: vi.fn(),
        refresh: vi.fn(),
      });

      render(<LoginPage />);

      await userEvent.type(screen.getByLabelText(/email address/i), "user@example.com");
      await userEvent.type(screen.getByLabelText(/password/i), "password123");
      await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent(/unable to connect to the server/i);
      });
    });

    it("navigates to dashboard on successful login", async () => {
      const mockLogin = vi.fn().mockResolvedValue({
        id: "123",
        email: "user@example.com",
        display_name: "Test User",
        is_active: true,
        created_at: "",
      });
      vi.spyOn(authContext, "useAuth").mockReturnValue({
        user: null,
        loading: false,
        login: mockLogin,
        register: vi.fn(),
        logout: vi.fn(),
        refresh: vi.fn(),
      });

      render(<LoginPage />);

      await userEvent.type(screen.getByLabelText(/email address/i), "user@example.com");
      await userEvent.type(screen.getByLabelText(/password/i), "validpassword");
      await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith("/dashboard");
      });
    });
  });

  describe("RegisterPage", () => {
    it("renders register form with fields", () => {
      render(<RegisterPage />);

      expect(
        screen.getByRole("heading", { name: /create an analytiq account/i })
      ).toBeInTheDocument();
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /create account/i })
      ).toBeInTheDocument();
    });

    it("validates password length under 8 characters", async () => {
      render(<RegisterPage />);

      await userEvent.type(screen.getByLabelText(/full name/i), "Alex");
      await userEvent.type(screen.getByLabelText(/email address/i), "alex@example.com");
      await userEvent.type(screen.getByLabelText(/^password/i), "short");
      await userEvent.type(screen.getByLabelText(/confirm password/i), "short");
      await userEvent.click(screen.getByRole("button", { name: /create account/i }));

      expect(
        await screen.findByText(/password must be at least 8 characters/i)
      ).toBeInTheDocument();
    });

    it("validates mismatched passwords", async () => {
      render(<RegisterPage />);

      await userEvent.type(screen.getByLabelText(/full name/i), "Alex");
      await userEvent.type(screen.getByLabelText(/email address/i), "alex@example.com");
      await userEvent.type(screen.getByLabelText(/^password/i), "Password123!");
      await userEvent.type(screen.getByLabelText(/confirm password/i), "PasswordMismatch!");
      await userEvent.click(screen.getByRole("button", { name: /create account/i }));

      expect(
        await screen.findByText(/passwords do not match/i)
      ).toBeInTheDocument();
    });
  });
});

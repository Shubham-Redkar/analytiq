import type { ApiErrorResponse, User } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    try {
      const errorData = (await response.json()) as ApiErrorResponse;
      if (errorData?.detail) {
        errorMessage = errorData.detail;
      }
    } catch {
      // Non-JSON error body
    }
    throw new ApiError(errorMessage, response.status);
  }

  return response.json() as Promise<T>;
}

export const api = {
  async register(data: { email: string; password: string; display_name: string }): Promise<User> {
    return request<User>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async login(credentials: { email: string; password: string }): Promise<User> {
    return request<User>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  },

  async logout(): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>("/api/v1/auth/logout", {
      method: "POST",
    });
  },

  async getMe(): Promise<User> {
    return request<User>("/api/v1/auth/me", {
      method: "GET",
    });
  },

  async getOwnership(): Promise<User> {
    return request<User>("/api/v1/users/me", {
      method: "GET",
    });
  },
};

export { ApiError };

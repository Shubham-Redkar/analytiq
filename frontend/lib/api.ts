import type {
  ApiErrorResponse,
  Dataset,
  DatasetListResponse,
  DatasetPreviewResponse,
  DatasetProfileResponse,
  DatasetQualityResponse,
  User,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export type ApiErrorCategory =
  "credentials" | "throttled" | "security" | "server" | "network" | "unknown";

export class ApiError extends Error {
  status: number;
  category: ApiErrorCategory;

  constructor(message: string, status: number, category?: ApiErrorCategory) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.category = category || ApiError.categorizeStatus(status);
  }

  static categorizeStatus(status: number): ApiErrorCategory {
    if (status === 401) return "credentials";
    if (status === 423) return "throttled";
    if (status === 403) return "security";
    if (status >= 500) return "server";
    if (status === 0) return "network";
    return "unknown";
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(
      "Unable to connect to the server. Please check your network connection.",
      0,
      "network"
    );
  }

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

  // A JSON endpoint returning 204 or empty text is an unexpected contract violation
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    throw new ApiError(
      `Expected JSON response from ${endpoint} but received status ${response.status} with empty content.`,
      response.status,
      "server"
    );
  }

  const text = await response.text();
  if (!text || text.trim() === "") {
    throw new ApiError(
      `Expected JSON response from ${endpoint} but received empty body.`,
      response.status,
      "server"
    );
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(
      `Failed to parse server response from ${endpoint} as JSON.`,
      response.status,
      "server"
    );
  }
}

/**
 * Perform a request to an endpoint that explicitly returns no content (e.g. HTTP 204).
 * Returns Promise<void> without unsafe generic casts.
 */
async function requestVoid(endpoint: string, options: RequestInit = {}): Promise<void> {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(
      "Unable to connect to the server. Please check your network connection.",
      0,
      "network"
    );
  }

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

  async uploadDataset(file: File, name?: string): Promise<Dataset> {
    const formData = new FormData();
    formData.append("file", file);
    if (name && name.trim()) {
      formData.append("name", name.trim());
    }
    return request<Dataset>("/api/v1/datasets", {
      method: "POST",
      body: formData,
    });
  },

  async listDatasets(page = 1, pageSize = 20): Promise<DatasetListResponse> {
    return request<DatasetListResponse>(`/api/v1/datasets?page=${page}&page_size=${pageSize}`, {
      method: "GET",
    });
  },

  async getDataset(id: string): Promise<Dataset> {
    return request<Dataset>(`/api/v1/datasets/${id}`, {
      method: "GET",
    });
  },

  async getDatasetPreview(id: string, offset = 0, limit = 25): Promise<DatasetPreviewResponse> {
    return request<DatasetPreviewResponse>(
      `/api/v1/datasets/${id}/preview?offset=${offset}&limit=${limit}`,
      {
        method: "GET",
      }
    );
  },

  async getDatasetProfile(id: string): Promise<DatasetProfileResponse> {
    return request<DatasetProfileResponse>(`/api/v1/datasets/${id}/profile`, {
      method: "GET",
    });
  },

  async getDatasetQuality(id: string): Promise<DatasetQualityResponse> {
    return request<DatasetQualityResponse>(`/api/v1/datasets/${id}/quality`, {
      method: "GET",
    });
  },

  async deleteDataset(
    id: string
  ): Promise<{ status: string; message: string; dataset_id: string }> {
    return request<{ status: string; message: string; dataset_id: string }>(
      `/api/v1/datasets/${id}`,
      {
        method: "DELETE",
      }
    );
  },

  // Analysis Sessions & Workflow APIs (M6)
  async listAnalysisSessions(
    datasetId?: string,
    page = 1,
    pageSize = 20
  ): Promise<import("./analysis-types").AnalysisSessionListResponse> {
    const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (datasetId) qs.set("dataset_id", datasetId);
    return request(`/api/v1/sessions?${qs.toString()}`, { method: "GET" });
  },

  async createAnalysisSession(
    datasetId: string,
    title?: string
  ): Promise<import("./analysis-types").AnalysisSessionResponse> {
    return request("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify({ dataset_id: datasetId, title }),
    });
  },

  async getAnalysisSession(
    sessionId: string
  ): Promise<import("./analysis-types").AnalysisSessionResponse> {
    return request(`/api/v1/sessions/${sessionId}`, { method: "GET" });
  },

  async updateAnalysisSession(
    sessionId: string,
    title: string
  ): Promise<import("./analysis-types").AnalysisSessionResponse> {
    return request(`/api/v1/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  },

  async deleteAnalysisSession(sessionId: string): Promise<void> {
    return requestVoid(`/api/v1/sessions/${sessionId}`, { method: "DELETE" });
  },

  async executeAnalysis(
    datasetId: string,
    question: string,
    sessionId?: string
  ): Promise<import("./analysis-types").WorkflowAnalysisResponse> {
    return request(`/api/v1/datasets/${datasetId}/analysis`, {
      method: "POST",
      body: JSON.stringify({ question, session_id: sessionId }),
    });
  },

  async cancelAnalysis(
    datasetId: string,
    requestId: string
  ): Promise<{ request_id: string; status: string; message: string }> {
    return request(`/api/v1/datasets/${datasetId}/analysis/${requestId}/cancel`, {
      method: "POST",
    });
  },

  // --- M7 Reports Endpoints ---
  async listReports(
    page = 1,
    pageSize = 20,
    datasetId?: string
  ): Promise<import("./report-types").ReportListResponse> {
    const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (datasetId) qs.set("dataset_id", datasetId);
    return request(`/api/v1/reports?${qs.toString()}`, { method: "GET" });
  },

  async createReport(
    payload: import("./report-types").CreateReportPayload
  ): Promise<import("./report-types").ReportDetail> {
    return request("/api/v1/reports", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getReport(reportId: string): Promise<import("./report-types").ReportDetail> {
    return request(`/api/v1/reports/${reportId}`, { method: "GET" });
  },

  async updateReport(
    reportId: string,
    payload: import("./report-types").UpdateReportPayload
  ): Promise<import("./report-types").ReportDetail> {
    return request(`/api/v1/reports/${reportId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async duplicateReport(reportId: string): Promise<import("./report-types").ReportDetail> {
    return request(`/api/v1/reports/${reportId}/duplicate`, {
      method: "POST",
    });
  },

  async deleteReport(reportId: string): Promise<void> {
    return requestVoid(`/api/v1/reports/${reportId}`, {
      method: "DELETE",
    });
  },

  getReportPdfUrl(reportId: string): string {
    return `${API_BASE}/api/v1/reports/${reportId}/export/pdf`;
  },

  getReportCsvUrl(reportId: string): string {
    return `${API_BASE}/api/v1/reports/${reportId}/export/csv`;
  },
};

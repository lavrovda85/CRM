/**
 * Centralized API client for the SPEC CRM backend.
 *
 * Все запросы проксируются через Next.js rewrite `/api/v1/*`.
 * Модуль предоставляет типизированные функции для каждой
 * группы эндпоинтов бэкенда.
 */

import type {
  ClientResponse,
  ChatMessageResponse,
  ChatAttachmentResponse,
  ChatRoomResponse,
  DashboardStats,
  DealResponse,
  DealStageResponse,
  DocumentResponse,
  EquipmentResponse,
  PaginatedResponse,
  ReferenceResponse,
  TaskDetail,
  TaskResponse,
  TenderAnalytics,
  TenderResponse,
  TenderDetailResponse,
  TenderChecklistItemResponse,
  TemplateResponse,
  TimeEntryResponse,
  TimeSummary,
  WarehouseAnalytics,
  WarehouseItemsImportResponse,
  WarehouseItemResponse,
  WarehouseMovementResponse,
  InboxNotificationItem,
  CompanyLoginOption,
} from "@/types";

/**
 * Public API base. In the browser always use same-origin `/api/v1` (Next `app/api/v1` → backend).
 * Ignores any absolute `NEXT_PUBLIC_API_URL` baked at build time so UI on :9000 cannot call :80 by mistake.
 * Non-browser (SSR) uses env for the rare code path that runs without `window`.
 */
function getApiBase(): string {
  if (typeof window !== "undefined") {
    return "/api/v1";
  }
  return (process.env.NEXT_PUBLIC_API_URL?.trim() || "/api/v1") as string;
}

/** Persists selected tenant for `X-Company-Id` on API calls (must match backend company context). */
export const ACTIVE_COMPANY_ID_STORAGE_KEY = "hvac_active_company_id";

function activeCompanyHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const id = localStorage.getItem(ACTIVE_COMPANY_ID_STORAGE_KEY)?.trim();
  return id ? { "X-Company-Id": id } : {};
}

/**
 * ngrok free tier (and similar tunnels) may serve an HTML interstitial unless this header is sent.
 * Without it, `/api/v1/*` can return HTML while `fetch` still "succeeds", breaking JSON parsing.
 */
function tunnelInterstitialBypassHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const h = window.location.hostname.toLowerCase();
  if (
    h.includes("ngrok") ||
    h.endsWith(".trycloudflare.com")
  ) {
    // Any value works; 69420 is commonly cited for ngrok free tier interstitials.
    return { "ngrok-skip-browser-warning": "69420" };
  }
  return {};
}

/** Prevents infinite spinners when Next.js → backend proxy or upstream hangs. */
const API_REQUEST_TIMEOUT_MS = 45_000;

function apiTimeoutSignal(existing?: AbortSignal | null): AbortSignal | undefined {
  if (typeof AbortSignal === "undefined") return undefined;
  const ctor = AbortSignal as unknown as {
    timeout?: (ms: number) => AbortSignal;
    any?: (signals: AbortSignal[]) => AbortSignal;
  };
  const t = ctor.timeout?.(API_REQUEST_TIMEOUT_MS);
  if (!t) return undefined;
  if (existing && ctor.any) {
    return ctor.any([t, existing]);
  }
  return t;
}

/** Parse FastAPI / backend JSON error bodies into one user-facing string. */
function extractApiErrorMessage(body: unknown): string {
  if (!body || typeof body !== "object") return "Request failed";
  const b = body as Record<string, unknown>;
  const err = b.error;
  if (err && typeof err === "object" && "message" in err) {
    const m = (err as { message?: unknown }).message;
    if (typeof m === "string" && m.trim()) return m;
  }
  const detail = b.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      try {
        return JSON.stringify(item);
      } catch {
        return String(item);
      }
    });
    return parts.filter(Boolean).join("; ") || "Request failed";
  }
  return "Request failed";
}

/**
 * Custom error thrown on non-2xx HTTP responses.
 *
 * Кастомная ошибка API, содержащая HTTP-статус, сообщение и код ошибки бэкенда.
 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isValidation(): boolean {
    return this.status === 422;
  }
}

/**
 * Centralized HTTP client with token management and typed responses.
 *
 * Класс-клиент для выполнения HTTP-запросов к бэкенду.
 * Автоматически прикрепляет Bearer-токен, парсит JSON-ответы
 * и выбрасывает `ApiError` при ошибках.
 * On 401, attempts one Keycloak token refresh via `/auth/refresh` before
 * invoking the unauthorized handler (avoids wiping the UI when the access
 * token simply expired).
 */
/** Paths where 401 must not call `onUnauthorized` (avoids logout→clear→401→logout loops). */
const PATHS_SKIP_401_LOGOUT = new Set(["/ai-assistant/clear"]);

class ApiClient {
  private token: string | null = null;
  private refreshToken: string | null = null;
  private refreshPromise: Promise<boolean> | null = null;
  private onUnauthorized: (() => void) | null = null;
  private onTokensRefreshed: ((access: string, refresh: string) => void) | null =
    null;

  /** Current bearer token (for conditional calls that must not fire when logged out). */
  getToken(): string | null {
    return this.token;
  }

  setToken(token: string): void {
    this.token = token;
  }

  clearToken(): void {
    this.token = null;
  }

  setRefreshToken(token: string | null): void {
    this.refreshToken = token;
  }

  setUnauthorizedHandler(handler: () => void): void {
    this.onUnauthorized = handler;
  }

  /**
   * Persist refreshed tokens (e.g. localStorage + zustand) without importing the auth store here.
   */
  setTokensRefreshedHandler(
    handler: ((access: string, refresh: string) => void) | null,
  ): void {
    this.onTokensRefreshed = handler;
  }

  private shouldAttemptRefresh(path: string): boolean {
    if (!this.refreshToken) return false;
    if (path === "/auth/refresh" || path.startsWith("/auth/refresh?")) {
      return false;
    }
    if (path === "/auth/login" || path.startsWith("/auth/login?")) {
      return false;
    }
    return true;
  }

  private shouldInvokeUnauthorizedOn401(path: string): boolean {
    if (!this.onUnauthorized) return false;
    const base = path.split("?")[0];
    return !PATHS_SKIP_401_LOGOUT.has(base);
  }

  /**
   * Rotate the access token using the stored refresh token (no 401 required).
   * Used for proactive refresh before JWT expiry.
   */
  async refreshAccessToken(): Promise<boolean> {
    return this.tryRefreshToken();
  }

  private async tryRefreshToken(): Promise<boolean> {
    if (!this.refreshToken) return false;
    if (this.refreshPromise) return this.refreshPromise;

    const rt = this.refreshToken;
    this.refreshPromise = (async () => {
      try {
        const res = await fetch(`${getApiBase()}/auth/refresh`, {
          method: "POST",
          headers: {
            ...tunnelInterstitialBypassHeaders(),
            "Content-Type": "application/json",
            ...activeCompanyHeaders(),
          },
          body: JSON.stringify({ refresh_token: rt }),
          signal: apiTimeoutSignal(),
        });
        if (!res.ok) return false;
        const data = (await res.json()) as {
          tokens?: {
            access_token: string;
            refresh_token?: string;
            token_type?: string;
            expires_in?: number;
          };
        };
        const t = data.tokens;
        if (!t?.access_token) return false;
        const newRefresh = t.refresh_token || rt;
        this.setToken(t.access_token);
        this.setRefreshToken(newRefresh);
        this.onTokensRefreshed?.(t.access_token, newRefresh);
        return true;
      } catch {
        return false;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  async request<T>(path: string, options?: RequestInit): Promise<T> {
    const exec = async (): Promise<Response> => {
      const hasBody = options?.body !== undefined && options?.body !== null;
      const isFormData =
        typeof FormData !== "undefined" && options?.body instanceof FormData;
      const headers: Record<string, string> = {
        ...tunnelInterstitialBypassHeaders(),
        ...(hasBody && !isFormData ? { "Content-Type": "application/json" } : {}),
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...activeCompanyHeaders(),
      };

      const mergedHeaders = options?.headers
        ? { ...headers, ...(options.headers as Record<string, string>) }
        : headers;

      return fetch(`${getApiBase()}${path}`, {
        ...options,
        headers: mergedHeaders,
        signal: apiTimeoutSignal(options?.signal ?? null),
      });
    };

    let res: Response;
    try {
      res = await exec();
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        throw new ApiError(
          408,
          "Request timed out — check API / BACKEND_INTERNAL_URL",
          "REQUEST_TIMEOUT",
        );
      }
      throw new ApiError(503, "Network error", "NETWORK_ERROR");
    }
    if (res.status === 401 && this.shouldAttemptRefresh(path)) {
      const refreshed = await this.tryRefreshToken();
      if (refreshed) {
        try {
          res = await exec();
        } catch (e) {
          if (e instanceof DOMException && e.name === "AbortError") {
            throw new ApiError(
              408,
              "Request timed out — check API / BACKEND_INTERNAL_URL",
              "REQUEST_TIMEOUT",
            );
          }
          throw new ApiError(503, "Network error", "NETWORK_ERROR");
        }
      }
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const message = extractApiErrorMessage(body);
      const code =
        body && typeof body === "object" && "error" in body
          ? (body as { error?: { code?: string } }).error?.code
          : undefined;

      if (res.status === 401 && this.shouldInvokeUnauthorizedOn401(path)) {
        this.onUnauthorized!();
      }

      throw new ApiError(res.status, message, code);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  }

  /** POST multipart (FormData); do not set Content-Type — browser sets boundary. */
  async postFormData<T>(path: string, formData: FormData): Promise<T> {
    return this.request<T>(path, { method: "POST", body: formData });
  }

  async requestBlob(
    path: string,
    options?: RequestInit,
  ): Promise<{ blob: Blob; filename: string }> {
    const exec = async (): Promise<Response> => {
      const hasBody = options?.body !== undefined && options?.body !== null;
      const isFormData =
        typeof FormData !== "undefined" && options?.body instanceof FormData;
      const headers: Record<string, string> = {
        ...tunnelInterstitialBypassHeaders(),
        ...(hasBody && !isFormData ? { "Content-Type": "application/json" } : {}),
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...activeCompanyHeaders(),
      };

      const mergedHeaders = options?.headers
        ? { ...headers, ...(options.headers as Record<string, string>) }
        : headers;

      return fetch(`${getApiBase()}${path}`, {
        ...options,
        headers: mergedHeaders,
        signal: apiTimeoutSignal(options?.signal ?? null),
      });
    };

    let res: Response;
    try {
      res = await exec();
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        throw new ApiError(
          408,
          "Request timed out — check API / BACKEND_INTERNAL_URL",
          "REQUEST_TIMEOUT",
        );
      }
      throw new ApiError(503, "Network error", "NETWORK_ERROR");
    }
    if (res.status === 401 && this.shouldAttemptRefresh(path)) {
      const refreshed = await this.tryRefreshToken();
      if (refreshed) {
        try {
          res = await exec();
        } catch (e) {
          if (e instanceof DOMException && e.name === "AbortError") {
            throw new ApiError(
              408,
              "Request timed out — check API / BACKEND_INTERNAL_URL",
              "REQUEST_TIMEOUT",
            );
          }
          throw new ApiError(503, "Network error", "NETWORK_ERROR");
        }
      }
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const message = extractApiErrorMessage(body);
      const code =
        body && typeof body === "object" && "error" in body
          ? (body as { error?: { code?: string } }).error?.code
          : undefined;

      if (res.status === 401 && this.shouldInvokeUnauthorizedOn401(path)) {
        this.onUnauthorized!();
      }

      throw new ApiError(res.status, message, code);
    }

    const blob = await res.blob();
    const contentDisp = res.headers.get("Content-Disposition") ?? "";
    const match = contentDisp.match(/filename="?([^"]+)"?/i);
    const filename = match?.[1] ?? "download.bin";
    return { blob, filename };
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, { method: "POST", body: JSON.stringify(body) });
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, { method: "PUT", body: JSON.stringify(body) });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }

  async uploadFile<T = unknown>(
    path: string,
    file: File,
    metadata: Record<string, string> = {},
  ): Promise<T> {
    const formData = new FormData();
    formData.append("file", file);
    Object.entries(metadata).forEach(([key, value]) =>
      formData.append(key, value),
    );
    return this.request<T>(path, { method: "POST", body: formData, headers: {} });
  }
}

export const api = new ApiClient();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return api.request<T>(path, init);
}

function qs(params: Record<string, unknown>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== "",
  );
  if (!entries.length) return "";
  return "?" + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

/* ------------------------------------------------------------------ */
/*  Companies (public login options)                                  */
/* ------------------------------------------------------------------ */

export async function fetchCompanyLoginOptions(): Promise<CompanyLoginOption[]> {
  return request<CompanyLoginOption[]>("/companies/login-options");
}

/* ------------------------------------------------------------------ */
/*  Analytics / Dashboard                                              */
/* ------------------------------------------------------------------ */

export async function fetchDashboard(): Promise<DashboardStats> {
  return request("/analytics/dashboard");
}

export async function fetchTenderAnalytics(): Promise<TenderAnalytics> {
  return request("/analytics/tenders");
}

export async function fetchWarehouseAnalytics(): Promise<WarehouseAnalytics> {
  return request("/analytics/warehouse");
}

/* ------------------------------------------------------------------ */
/*  In-app notifications (task inbox)                                 */
/* ------------------------------------------------------------------ */

export async function fetchInboxNotifications(
  params: { limit?: number; offset?: number; unread_only?: boolean } = {},
): Promise<PaginatedResponse<InboxNotificationItem>> {
  const q: Record<string, unknown> = {
    limit: params.limit ?? 40,
    offset: params.offset ?? 0,
  };
  if (params.unread_only) q.unread_only = true;
  return request(`/notifications${qs(q)}`);
}

export async function fetchUnreadNotificationCount(): Promise<{ unread_count: number }> {
  return request("/notifications/unread-count");
}

export async function markInboxNotificationRead(id: string): Promise<InboxNotificationItem> {
  return request(`/notifications/${id}/read`, { method: "PATCH" });
}

export async function markAllInboxNotificationsRead(): Promise<{ unread_count: number }> {
  return request("/notifications/mark-all-read", { method: "POST" });
}

/* ------------------------------------------------------------------ */
/*  Tasks                                                              */
/* ------------------------------------------------------------------ */

export async function fetchTasks(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<TaskResponse>> {
  return request(`/tasks${qs(params)}`);
}

export async function fetchTask(id: string): Promise<TaskDetail> {
  return request(`/tasks/${id}`);
}

export async function transitionTask(
  id: string,
  to_status: string,
  reason?: string,
): Promise<TaskResponse> {
  return request(`/tasks/${id}/transition`, {
    method: "POST",
    body: JSON.stringify({ to_status, reason }),
  });
}

export async function createTask(
  data: Record<string, unknown>,
): Promise<TaskResponse> {
  return request("/tasks", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTask(
  id: string,
  data: Record<string, unknown>,
): Promise<TaskResponse> {
  return request(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteTask(id: string): Promise<void> {
  return request(`/tasks/${id}`, { method: "DELETE" });
}

export async function addComment(
  taskId: string,
  body: string,
  mentions: string[] = [],
  attachmentDocIds: string[] = [],
): Promise<unknown> {
  return request(`/tasks/${taskId}/comments`, {
    method: "POST",
    body: JSON.stringify({ body, mentions, attachment_doc_ids: attachmentDocIds }),
  });
}

export async function toggleChecklistItem(
  taskId: string,
  checklistId: string,
  itemId: string,
): Promise<TaskDetail> {
  return request(
    `/tasks/${taskId}/checklists/${checklistId}/items/${itemId}/toggle`,
    { method: "POST" },
  );
}

/* ------------------------------------------------------------------ */
/*  Clients                                                            */
/* ------------------------------------------------------------------ */

export async function fetchClients(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<ClientResponse>> {
  return request(`/clients${qs(params)}`);
}

export async function createClient(
  data: Record<string, unknown>,
): Promise<ClientResponse> {
  return request("/clients", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ------------------------------------------------------------------ */
/*  Deals                                                              */
/* ------------------------------------------------------------------ */

export async function fetchDeals(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<DealResponse>> {
  return request(`/deals${qs(params)}`);
}

export async function fetchDealStages(): Promise<DealStageResponse[]> {
  return request("/deals/stages");
}

export async function updateDeal(
  id: string,
  data: Record<string, unknown>,
): Promise<DealResponse> {
  return request(`/deals/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/* ------------------------------------------------------------------ */
/*  Tenders                                                            */
/* ------------------------------------------------------------------ */

export async function fetchTenders(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<TenderResponse>> {
  return request(`/tenders${qs(params)}`);
}

export async function fetchTender(id: string): Promise<TenderDetailResponse> {
  return request(`/tenders/${id}`);
}

export async function createTender(
  data: Record<string, unknown>,
): Promise<TenderResponse> {
  return request("/tenders", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTender(
  id: string,
  data: Record<string, unknown>,
): Promise<TenderResponse> {
  return request(`/tenders/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/** Move tender along the validated lifecycle pipeline (search → … → completed). */
export async function transitionTender(
  id: string,
  to_status: string,
  reason?: string | null,
): Promise<TenderResponse> {
  const body: Record<string, unknown> = { to_status };
  if (reason?.trim()) body.reason = reason.trim();
  return request(`/tenders/${id}/transition`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteTender(id: string): Promise<void> {
  return request(`/tenders/${id}`, { method: "DELETE" });
}

export async function retryTenderAnalysis(
  tenderId: string,
): Promise<{ queued: boolean; tender_id: string }> {
  return request(`/tenders/${tenderId}/analysis/retry`, { method: "POST" });
}

export async function calculateTenderSmeta(
  tenderId: string,
): Promise<{ queued: boolean; tender_id: string }> {
  return request(`/tenders/${tenderId}/smeta/calculate`, { method: "POST" });
}

export async function createTenderEstimatorTask(
  tenderId: string,
  body?: {
    assigned_to?: string | null;
    description?: string | null;
    attachment_document_ids?: string[];
  },
): Promise<TaskResponse> {
  return request(`/tenders/${tenderId}/estimator-task`, {
    method: "POST",
    body: JSON.stringify(body ?? {}),
  });
}

export async function patchTenderBillOfWorks(
  tenderId: string,
  data: {
    bill_of_works: Array<Record<string, string | undefined>>;
    bill_of_works_notes?: string | null;
  },
): Promise<TenderResponse> {
  return request(`/tenders/${tenderId}/bill-of-works`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function createTasksFromBill(
  tenderId: string,
  body?: { assigned_to?: string | null; row_indices?: number[] | null },
): Promise<TaskResponse[]> {
  return request(`/tenders/${tenderId}/tasks-from-bill`, {
    method: "POST",
    body: JSON.stringify(body ?? {}),
  });
}

export async function toggleTenderChecklistItem(
  tenderId: string,
  itemId: string,
): Promise<TenderChecklistItemResponse> {
  return request(`/tenders/${tenderId}/checklists/items/${itemId}/toggle`, {
    method: "POST",
  });
}

export async function updateTenderChecklistItem(
  tenderId: string,
  itemId: string,
  data: Record<string, unknown>,
): Promise<TenderChecklistItemResponse> {
  return request(`/tenders/${tenderId}/checklists/items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function addTenderComment(
  tenderId: string,
  body: string,
  mentions: string[] = [],
  attachmentDocIds: string[] = [],
): Promise<unknown> {
  return request(`/tenders/${tenderId}/comments`, {
    method: "POST",
    body: JSON.stringify({ body, mentions, attachment_doc_ids: attachmentDocIds }),
  });
}

/* ------------------------------------------------------------------ */
/*  Time Tracking                                                      */
/* ------------------------------------------------------------------ */

export async function fetchTimeEntries(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<TimeEntryResponse>> {
  return request(`/time/entries${qs(params)}`);
}

export async function fetchTimeSummary(
  params: Record<string, unknown> = {},
): Promise<TimeSummary> {
  return request(`/time/summary${qs(params)}`);
}

export async function startTimer(
  task_id: string,
  notes?: string,
): Promise<TimeEntryResponse> {
  return request("/time/timer/start", {
    method: "POST",
    body: JSON.stringify({ task_id, notes }),
  });
}

export async function stopTimer(notes?: string): Promise<TimeEntryResponse> {
  return request("/time/timer/stop", {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
}

export async function createTimeEntry(
  data: Record<string, unknown>,
): Promise<TimeEntryResponse> {
  return request("/time/entries", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ------------------------------------------------------------------ */
/*  Warehouse                                                          */
/* ------------------------------------------------------------------ */

export async function fetchWarehouseItems(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<WarehouseItemResponse>> {
  return request(`/warehouse/items${qs(params)}`);
}

export async function createWarehouseItem(
  data: Record<string, unknown>,
): Promise<WarehouseItemResponse> {
  return request("/warehouse/items", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function downloadWarehouseItemsExcel(): Promise<void> {
  if (typeof window === "undefined") return;
  const { blob, filename } = await api.requestBlob("/warehouse/items/export");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function importWarehouseItemsExcel(file: File): Promise<WarehouseItemsImportResponse> {
  return api.uploadFile("/warehouse/items/import", file, {});
}

export async function fetchWarehouseMovements(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<WarehouseMovementResponse>> {
  return request(`/warehouse/movements${qs(params)}`);
}

export async function createWarehouseMovement(
  data: Record<string, unknown>,
): Promise<WarehouseMovementResponse> {
  return request("/warehouse/movements", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ------------------------------------------------------------------ */
/*  Equipment                                                          */
/* ------------------------------------------------------------------ */

export async function fetchEquipment(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<EquipmentResponse>> {
  return request(`/equipment${qs(params)}`);
}

/* ------------------------------------------------------------------ */
/*  Templates                                                          */
/* ------------------------------------------------------------------ */

export async function fetchTemplates(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<TemplateResponse>> {
  return request(`/templates${qs(params)}`);
}

export async function fetchTemplate(id: string): Promise<TemplateResponse> {
  return request(`/templates/${id}`);
}

export async function createTemplate(
  data: Record<string, unknown>,
): Promise<TemplateResponse> {
  return request("/templates", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTemplate(
  id: string,
  data: Record<string, unknown>,
): Promise<TemplateResponse> {
  return request(`/templates/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteTemplate(id: string): Promise<void> {
  return request(`/templates/${id}`, { method: "DELETE" });
}

/* ------------------------------------------------------------------ */
/*  Chat                                                               */
/* ------------------------------------------------------------------ */

export async function fetchChatMessages(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<ChatMessageResponse>> {
  return request(`/chat/messages${qs(params)}`);
}

export async function sendChatMessage(
  data: { room?: string; body: string },
): Promise<ChatMessageResponse> {
  return request("/chat/messages", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function uploadChatMessageAttachment(
  messageId: string,
  file: File,
): Promise<ChatAttachmentResponse> {
  return api.uploadFile(`/chat/messages/${messageId}/attachments`, file, {});
}

export async function fetchChatRooms(): Promise<ChatRoomResponse[]> {
  return request("/chat/rooms");
}

export async function createChatRoom(data: { name: string; code?: string }): Promise<ChatRoomResponse> {
  return request("/chat/rooms", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ------------------------------------------------------------------ */
/*  References                                                         */
/* ------------------------------------------------------------------ */

export async function fetchReferences(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<ReferenceResponse>> {
  return request(`/references${qs(params)}`);
}

export async function fetchReference(code: string): Promise<ReferenceResponse> {
  return request(`/references/${code}`);
}

export async function createReferenceItem(
  code: string,
  data: Record<string, unknown>,
): Promise<unknown> {
  return request(`/references/${code}/items`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateReferenceItem(
  code: string,
  itemId: string,
  data: Record<string, unknown>,
): Promise<unknown> {
  return request(`/references/${code}/items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/* ------------------------------------------------------------------ */
/*  Users                                                              */
/* ------------------------------------------------------------------ */

export interface UserListItem {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  avatar_url?: string | null;
}

export interface UserDetail {
  id: string;
  keycloak_id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: string;
  position: string | null;
  avatar_url: string | null;
  is_active: boolean;
  telegram_chat_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminSchedulerSettings {
  id?: string;
  name?: string;
  order?: number;
  enabled: boolean;
  cron_minute: string;
  cron_hour: string;
  cron_day_of_month: string;
  cron_month_of_year: string;
  cron_day_of_week: string;
  title: string;
  description?: string | null;
  priority: "low" | "medium" | "high" | "critical";
  template_id?: string | null;
  assigned_to?: string | null;
  requested_by?: string | null;
  board_id?: string | null;
  client_id?: string | null;
  due_in_hours: number;
  observer_ids: string[];
  co_assignee_ids: string[];
  dedup_window_minutes: number;
}

export interface AdminSettingsEnvelope {
  scheduler: AdminSchedulerSettings;
  scheduler_rules: AdminSchedulerSettings[];
  env_preview: Record<string, string>;
}

export async function fetchCurrentUser(): Promise<UserDetail> {
  return request("/users/me");
}

export async function fetchAdminSettings(): Promise<AdminSettingsEnvelope> {
  return request("/admin/settings");
}

export async function updateAdminSchedulerSettings(
  data: Partial<AdminSchedulerSettings>,
): Promise<AdminSchedulerSettings> {
  return request("/admin/settings/scheduler", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function fetchAdminSchedulerRules(): Promise<AdminSchedulerSettings[]> {
  return request("/admin/settings/scheduler/rules");
}

export async function createAdminSchedulerRule(
  data: Partial<AdminSchedulerSettings>,
): Promise<AdminSchedulerSettings> {
  return request("/admin/settings/scheduler/rules", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminSchedulerRule(
  ruleId: string,
  data: Partial<AdminSchedulerSettings>,
): Promise<AdminSchedulerSettings> {
  return request(`/admin/settings/scheduler/rules/${ruleId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminSchedulerRule(ruleId: string): Promise<void> {
  return request(`/admin/settings/scheduler/rules/${ruleId}`, {
    method: "DELETE",
  });
}

export async function runAdminSchedulerRuleNow(
  ruleId: string,
): Promise<{ ok: boolean; created: number; rules_total: number; rule_id: string }> {
  return request(`/admin/settings/scheduler/rules/${ruleId}/run`, {
    method: "POST",
  });
}

export interface DeployStatus {
  deploy_ui_enabled: boolean;
  agent_reachable: boolean | null;
  agent_error: string | null;
  github_repo_configured: boolean;
}

export interface DeployJob {
  id: string;
  branch: string;
  status: string;
  previous_sha: string | null;
  new_sha: string | null;
  log_excerpt: string | null;
  error_message: string | null;
  created_at: string;
  finished_at: string | null;
}

export async function fetchDeployStatus(): Promise<DeployStatus> {
  return request("/admin/deploy/status");
}

export async function fetchDeployBranches(): Promise<string[]> {
  const r = await request<{ branches: string[] }>("/admin/deploy/branches");
  return r.branches || [];
}

export async function runDeploy(branch: string): Promise<DeployJob> {
  return request("/admin/deploy/run", {
    method: "POST",
    body: JSON.stringify({ branch }),
  });
}

export async function fetchDeployJobs(limit = 30): Promise<DeployJob[]> {
  return request(`/admin/deploy/jobs?limit=${limit}`);
}

export async function fetchDeployJob(jobId: string): Promise<DeployJob> {
  return request(`/admin/deploy/jobs/${jobId}`);
}

export async function fetchProjectLogs(tail = 400): Promise<string> {
  const r = await request<{ lines: string }>(`/admin/deploy/logs/project?tail=${tail}`);
  return r.lines || "";
}

/** Update own profile (phone, name). Requires auth; does not use admin-only PATCH /users/{id}. */
export async function updateCurrentUserProfile(data: {
  phone?: string | null;
  full_name?: string | null;
}): Promise<UserDetail> {
  return request("/users/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function fetchUsers(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<UserListItem>> {
  return request(`/users${qs(params)}`);
}

export async function fetchUser(id: string): Promise<UserDetail> {
  return request(`/users/${id}`);
}

export async function createUser(
  data: Record<string, unknown>,
): Promise<UserDetail> {
  return request("/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateUser(
  id: string,
  data: Record<string, unknown>,
): Promise<UserDetail> {
  return request(`/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deactivateUser(id: string): Promise<void> {
  return request(`/users/${id}`, { method: "DELETE" });
}

export async function uploadUserAvatar(id: string, file: File): Promise<UserDetail> {
  return api.uploadFile(`/users/${id}/avatar`, file, {});
}

/* ------------------------------------------------------------------ */
/*  Documents                                                          */
/* ------------------------------------------------------------------ */

export async function uploadDocument(
  file: File,
  taskId?: string,
  docType: string = "other",
  label?: string,
  tenderId?: string,
): Promise<DocumentResponse> {
  const metadata: Record<string, string> = { doc_type: docType };
  if (taskId) metadata.task_id = taskId;
  if (tenderId) metadata.tender_id = tenderId;
  if (label) metadata.label = label;
  return api.uploadFile("/documents/upload", file, metadata);
}

export async function getDocumentDownloadUrl(
  docId: string,
): Promise<{ url: string; filename: string }> {
  return request(`/documents/${docId}/download`);
}

export async function deleteDocument(docId: string): Promise<void> {
  return request(`/documents/${docId}`, { method: "DELETE" });
}

/* ------------------------------------------------------------------ */
/*  AI assistant (OpenAI + MCP tools)                                 */
/* ------------------------------------------------------------------ */

export interface AiAssistantStatus {
  enabled: boolean;
  model: string;
}

export interface AiAssistantMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

/** Per-file outcome from POST /ai-assistant/chat/upload (server merged into model). */
export interface AiUploadFileSummary {
  name: string;
  kind: string;
  included_in_context: boolean;
  text_chars?: number | null;
  note?: string | null;
}

/** Confirms which attachments reached the model (multipart upload only). */
export interface AiUploadContext {
  merged_into_model: boolean;
  total_document_text_chars?: number | null;
  images_for_vision: number;
  files: AiUploadFileSummary[];
  warnings: string[];
}

export interface AiAssistantChatResponse {
  reply: string;
  messages: AiAssistantMessageItem[];
  upload_context?: AiUploadContext | null;
}

export async function fetchAiAssistantStatus(): Promise<AiAssistantStatus> {
  return request("/ai-assistant/status");
}

export async function fetchAiAssistantMessages(): Promise<AiAssistantMessageItem[]> {
  return request("/ai-assistant/messages");
}

export async function postAiAssistantChat(body: {
  message: string;
  files?: File[];
}): Promise<AiAssistantChatResponse> {
  if (body.files && body.files.length > 0) {
    const fd = new FormData();
    fd.append("message", body.message);
    for (const f of body.files) {
      fd.append("files", f);
    }
    return api.postFormData("/ai-assistant/chat/upload", fd);
  }
  return request("/ai-assistant/chat", {
    method: "POST",
    body: JSON.stringify({ message: body.message }),
  });
}

/**
 * Best-effort wipe of server-side AI assistant history.
 * Uses `fetch` (not `ApiClient`) so 401 never triggers the global logout handler.
 *
 * @param accessTokenOverride - Token captured before `api.clearToken()` (e.g. on logout).
 */
export async function clearAiAssistantServerHistory(
  accessTokenOverride?: string | null,
): Promise<void> {
  const t = (accessTokenOverride ?? api.getToken())?.trim();
  if (!t) return;
  const base = getApiBase().replace(/\/$/, "");
  const url = `${base}/ai-assistant/clear`;
  try {
    await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${t}`,
        ...activeCompanyHeaders(),
      },
    });
  } catch {
    /* ignore network errors during teardown */
  }
}

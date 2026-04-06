/**
 * Centralized API client for the HVAC CRM backend.
 *
 * Все запросы проксируются через Next.js rewrite `/api/v1/*`.
 * Модуль предоставляет типизированные функции для каждой
 * группы эндпоинтов бэкенда.
 */

import type {
  ClientResponse,
  DashboardStats,
  DealResponse,
  DealStageResponse,
  EquipmentResponse,
  PaginatedResponse,
  ReferenceResponse,
  TaskDetail,
  TaskResponse,
  TenderAnalytics,
  TenderResponse,
  TemplateResponse,
  TimeEntryResponse,
  TimeSummary,
  WarehouseAnalytics,
  WarehouseItemResponse,
  WarehouseMovementResponse,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

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
 */
class ApiClient {
  private token: string | null = null;
  private onUnauthorized: (() => void) | null = null;

  setToken(token: string): void {
    this.token = token;
  }

  clearToken(): void {
    this.token = null;
  }

  setUnauthorizedHandler(handler: () => void): void {
    this.onUnauthorized = handler;
  }

  async request<T>(path: string, options?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
    };

    const mergedHeaders = options?.headers
      ? { ...headers, ...(options.headers as Record<string, string>) }
      : headers;

    const res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: mergedHeaders,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const message = body?.error?.message || body?.detail || "Request failed";
      const code = body?.error?.code;

      if (res.status === 401 && this.onUnauthorized) {
        this.onUnauthorized();
      }

      throw new ApiError(res.status, message, code);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
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

export async function updateTender(
  id: string,
  data: Record<string, unknown>,
): Promise<TenderResponse> {
  return request(`/tenders/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
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

export async function fetchWarehouseMovements(
  params: Record<string, unknown> = {},
): Promise<PaginatedResponse<WarehouseMovementResponse>> {
  return request(`/warehouse/movements${qs(params)}`);
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

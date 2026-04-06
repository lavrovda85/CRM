/**
 * Zustand store for authentication state management.
 *
 * Хранилище состояния аутентификации: текущий пользователь, токены,
 * методы login/logout и инициализация из localStorage.
 */

import { create } from "zustand";
import {
  ACTIVE_COMPANY_ID_STORAGE_KEY,
  api,
  clearAiAssistantServerHistory,
} from "@/lib/api";
import { clearAiAssistantSession } from "@/stores/aiAssistant";
import { useCompanyStore } from "@/stores/company";
import { ws } from "@/lib/ws";
import type { User, AuthTokens } from "@/types";

const TOKEN_KEY = "hvac_access_token";
const REFRESH_KEY = "hvac_refresh_token";

/** Prevents re-entrant `logout` when 401 handlers fire during teardown. */
let logoutInProgress = false;

/** JWT `exp` claim in milliseconds, or null if not parseable. */
function readJwtExpMs(accessToken: string): number | null {
  try {
    const parts = accessToken.split(".");
    if (parts.length < 2) return null;
    let base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = base64.length % 4;
    if (pad) base64 += "=".repeat(4 - pad);
    const json = JSON.parse(atob(base64)) as { exp?: number };
    if (typeof json.exp === "number") return json.exp * 1000;
    return null;
  } catch {
    return null;
  }
}

let proactiveRefreshTimer: ReturnType<typeof setTimeout> | null = null;

function clearProactiveRefreshTimer(): void {
  if (proactiveRefreshTimer !== null) {
    clearTimeout(proactiveRefreshTimer);
    proactiveRefreshTimer = null;
  }
}

/**
 * Schedule a single access-token refresh before JWT expiry so background
 * requests (polling) do not hit 401 and trigger logout.
 */
function scheduleProactiveTokenRefresh(): void {
  clearProactiveRefreshTimer();
  if (typeof window === "undefined") return;

  const refresh = localStorage.getItem(REFRESH_KEY)?.trim();
  const access = localStorage.getItem(TOKEN_KEY)?.trim();
  if (!refresh || !access) return;

  const expMs = readJwtExpMs(access);
  const skewMs = 90_000;
  const fallbackDelayMs = 4 * 60 * 1000;
  const minDelayMs = 15_000;
  const delay =
    expMs !== null
      ? Math.max(expMs - Date.now() - skewMs, minDelayMs)
      : Math.max(fallbackDelayMs, minDelayMs);

  proactiveRefreshTimer = setTimeout(() => {
    void (async () => {
      const ok = await api.refreshAccessToken().catch(() => false);
      if (!ok) {
        scheduleProactiveTokenRefresh();
      }
    })();
  }, delay);
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string, companyId?: string | null) => Promise<void>;
  loginWithTokens: (tokens: AuthTokens, user: User) => void;
  logout: () => void;
  initialize: () => Promise<void>;
  setUser: (user: User) => void;
}

/**
 * Global auth store powered by Zustand.
 *
 * Глобальное хранилище аутентификации. Управляет жизненным циклом
 * токенов, синхронизацией с API-клиентом и WebSocket-соединением.
 */
export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (email, password, companyId) => {
    const data = await api.post<{
      tokens: AuthTokens;
      user: User;
      active_company_id?: string;
    }>("/auth/login", {
      email: email.trim(),
      password,
      ...(companyId?.trim() ? { company_id: companyId.trim() } : {}),
    });

    if (typeof window !== "undefined" && data.active_company_id) {
      localStorage.setItem(ACTIVE_COMPANY_ID_STORAGE_KEY, data.active_company_id);
    }

    get().loginWithTokens(data.tokens, data.user);
  },

  loginWithTokens: (tokens, user) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, tokens.access_token);
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    }

    api.setToken(tokens.access_token);
    api.setRefreshToken(tokens.refresh_token?.trim() || null);
    api.setUnauthorizedHandler(() => get().logout());
    ws.setToken(tokens.access_token);
    ws.connect();

    set({
      user,
      token: tokens.access_token,
      isAuthenticated: true,
      isLoading: false,
    });
    scheduleProactiveTokenRefresh();
    void useCompanyStore.getState().loadFromApi();
  },

  logout: () => {
    if (logoutInProgress) return;
    logoutInProgress = true;
    const accessForClear = api.getToken()?.trim() ?? null;
    try {
      clearProactiveRefreshTimer();
      useCompanyStore.getState().reset();
      clearAiAssistantSession();
      if (typeof window !== "undefined") {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
      }

      api.clearToken();
      api.setRefreshToken(null);
      ws.disconnect();
      ws.clearToken();

      set({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
      });
      if (accessForClear) {
        void clearAiAssistantServerHistory(accessForClear);
      }
    } finally {
      logoutInProgress = false;
    }
  },

  initialize: async () => {
    if (typeof window === "undefined") {
      set({ isLoading: false });
      return;
    }

    /**
     * Backend `BACKEND_DEBUG=true`: `/auth/me` without Authorization returns the dev CRM user.
     * Must run after clearing a stale JWT, otherwise we never hit this path.
     */
    const tryTokenlessDevMe = async (): Promise<boolean> => {
      try {
        api.clearToken();
        api.setRefreshToken(null);
        const user = await api.get<User>("/auth/me");
        api.setUnauthorizedHandler(() => get().logout());
        set({ user, token: null, isAuthenticated: true, isLoading: false });
        ws.clearToken();
        ws.connect();
        void useCompanyStore.getState().loadFromApi();
        return true;
      } catch {
        return false;
      }
    };

    const token = localStorage.getItem(TOKEN_KEY)?.trim();
    if (!token) {
      const ok = await tryTokenlessDevMe();
      if (!ok) {
        api.setUnauthorizedHandler(() => get().logout());
        set({ isLoading: false, user: null, token: null, isAuthenticated: false });
      }
      return;
    }

    api.setToken(token);
    const storedRefresh = localStorage.getItem(REFRESH_KEY)?.trim() || null;
    api.setRefreshToken(storedRefresh);
    api.setUnauthorizedHandler(() => get().logout());

    try {
      const user = await api.get<User>("/auth/me");
      ws.setToken(token);
      ws.connect();
      set({ user, token, isAuthenticated: true, isLoading: false });
      scheduleProactiveTokenRefresh();
      void useCompanyStore.getState().loadFromApi();
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
      api.clearToken();
      api.setRefreshToken(null);
      ws.disconnect();
      ws.clearToken();
      clearProactiveRefreshTimer();
      const devOk = await tryTokenlessDevMe();
      if (!devOk) {
        api.setUnauthorizedHandler(() => get().logout());
        set({ isLoading: false, user: null, token: null, isAuthenticated: false });
      }
    }
  },

  setUser: (user) => set({ user }),
}));

api.setTokensRefreshedHandler((access, refresh) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  }
  useAuthStore.setState((state) =>
    state.isAuthenticated ? { token: access } : {},
  );
  ws.setToken(access);
  scheduleProactiveTokenRefresh();
});

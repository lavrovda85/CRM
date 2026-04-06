/**
 * Zustand store for authentication state management.
 *
 * Хранилище состояния аутентификации: текущий пользователь, токены,
 * методы login/logout и инициализация из localStorage.
 */

import { create } from "zustand";
import { api } from "@/lib/api";
import { ws } from "@/lib/ws";
import type { User, AuthTokens } from "@/types";

const TOKEN_KEY = "hvac_access_token";
const REFRESH_KEY = "hvac_refresh_token";

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
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

  login: async (email, password) => {
    const data = await api.post<{ tokens: AuthTokens; user: User }>(
      "/auth/login",
      { email, password },
    );

    get().loginWithTokens(data.tokens, data.user);
  },

  loginWithTokens: (tokens, user) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, tokens.access_token);
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    }

    api.setToken(tokens.access_token);
    ws.setToken(tokens.access_token);
    ws.connect();

    set({
      user,
      token: tokens.access_token,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
    }

    api.clearToken();
    ws.disconnect();

    set({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  initialize: async () => {
    if (typeof window === "undefined") {
      set({ isLoading: false });
      return;
    }

    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      set({ isLoading: false });
      return;
    }

    api.setToken(token);
    api.setUnauthorizedHandler(() => get().logout());

    try {
      const user = await api.get<User>("/auth/me");
      ws.setToken(token);
      ws.connect();
      set({ user, token, isAuthenticated: true, isLoading: false });
    } catch {
      get().logout();
    }
  },

  setUser: (user) => set({ user }),
}));

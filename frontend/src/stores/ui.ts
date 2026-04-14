/**
 * Zustand store for UI state management.
 *
 * Хранилище состояния интерфейса: сворачивание сайдбара, активная страница,
 * управление модальными окнами и мобильным меню.
 */

import type { ReactNode } from "react";
import { create } from "zustand";

interface ModalState {
  id: string;
  props?: Record<string, unknown>;
}

interface UiState {
  sidebarCollapsed: boolean;
  mobileSidebarOpen: boolean;
  mobileMenuOpen: boolean;
  activePage: string;
  activeModal: ModalState | null;
  searchOpen: boolean;
  /** Tasks list search text (header command palette + filters bar on `/tasks`). */
  tasksSearchDraft: string;
  /** Optional center area in `Header` (e.g. tasks toolbar). Cleared on route leave. */
  headerToolbar: ReactNode | null;

  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleMobileSidebar: () => void;
  setMobileSidebarOpen: (open: boolean) => void;
  setMobileMenuOpen: (open: boolean) => void;
  setActivePage: (page: string) => void;
  openModal: (id: string, props?: Record<string, unknown>) => void;
  closeModal: () => void;
  toggleSearch: () => void;
  setSearchOpen: (open: boolean) => void;
  setTasksSearchDraft: (q: string) => void;
  setHeaderToolbar: (node: ReactNode | null) => void;
}

const SIDEBAR_KEY = "hvac_sidebar_collapsed";

/**
 * Global UI store powered by Zustand.
 *
 * Глобальное хранилище UI-состояния. Управляет состоянием навигации,
 * модальных окон и поисковой панели. Состояние сайдбара сохраняется
 * в localStorage для персистентности между сессиями.
 */
export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed:
    typeof window !== "undefined"
      ? localStorage.getItem(SIDEBAR_KEY) === "true"
      : false,
  mobileSidebarOpen: false,
  mobileMenuOpen: false,
  activePage: "dashboard",
  activeModal: null,
  searchOpen: false,
  tasksSearchDraft: "",
  headerToolbar: null,

  toggleSidebar: () =>
    set((state) => {
      const next = !state.sidebarCollapsed;
      if (typeof window !== "undefined") {
        localStorage.setItem(SIDEBAR_KEY, String(next));
      }
      return { sidebarCollapsed: next };
    }),

  setSidebarCollapsed: (collapsed) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(SIDEBAR_KEY, String(collapsed));
    }
    set({ sidebarCollapsed: collapsed });
  },

  toggleMobileSidebar: () =>
    set((state) => ({ mobileSidebarOpen: !state.mobileSidebarOpen })),

  setMobileSidebarOpen: (open) => set({ mobileSidebarOpen: open }),

  setMobileMenuOpen: (open) => set({ mobileMenuOpen: open }),

  setActivePage: (page) => set({ activePage: page }),

  openModal: (id, props) => set({ activeModal: { id, props } }),

  closeModal: () => set({ activeModal: null }),

  toggleSearch: () => set((state) => ({ searchOpen: !state.searchOpen })),

  setSearchOpen: (open) => set({ searchOpen: open }),

  setTasksSearchDraft: (q) => set({ tasksSearchDraft: q }),

  setHeaderToolbar: (node) => set({ headerToolbar: node }),
}));

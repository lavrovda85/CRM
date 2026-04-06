/**
 * Active company (tenant) for API requests via X-Company-Id.
 *
 * Хранит список организаций пользователя и выбранную компанию в localStorage.
 */

import { create } from "zustand";

import { ACTIVE_COMPANY_ID_STORAGE_KEY, api } from "@/lib/api";
import type { CompanyMembershipItem } from "@/types";

interface CompanyState {
  memberships: CompanyMembershipItem[];
  activeCompanyId: string | null;
  loadFromApi: () => Promise<void>;
  setActiveCompanyId: (id: string | null) => void;
  reset: () => void;
}

export const useCompanyStore = create<CompanyState>((set) => ({
  memberships: [],
  activeCompanyId: null,

  loadFromApi: async () => {
    try {
      const list = await api.get<CompanyMembershipItem[]>("/companies/mine");
      let id: string | null =
        typeof window !== "undefined"
          ? localStorage.getItem(ACTIVE_COMPANY_ID_STORAGE_KEY)?.trim() || null
          : null;
      const valid = new Set(list.map((m) => m.company.id));
      if (id && !valid.has(id)) id = null;
      if (!id) {
        id =
          list.find((m) => m.is_default)?.company.id ??
          list[0]?.company.id ??
          null;
      }
      if (typeof window !== "undefined") {
        if (id) localStorage.setItem(ACTIVE_COMPANY_ID_STORAGE_KEY, id);
        else localStorage.removeItem(ACTIVE_COMPANY_ID_STORAGE_KEY);
      }
      set({ memberships: list, activeCompanyId: id });
    } catch {
      set({ memberships: [], activeCompanyId: null });
    }
  },

  setActiveCompanyId: (id) => {
    if (typeof window !== "undefined") {
      if (id) localStorage.setItem(ACTIVE_COMPANY_ID_STORAGE_KEY, id);
      else localStorage.removeItem(ACTIVE_COMPANY_ID_STORAGE_KEY);
    }
    set({ activeCompanyId: id });
  },

  reset: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(ACTIVE_COMPANY_ID_STORAGE_KEY);
    }
    set({ memberships: [], activeCompanyId: null });
  },
}));

/**
 * AI assistant UI state (in-memory). Authoritative history lives on the server per user.
 *
 * Сообщения подгружаются с бэкенда при открытии страницы и после каждого ответа;
 * при навигации по SPA состояние в Zustand сохраняется до перезагрузки вкладки.
 */

import { create } from "zustand";

export type AiAssistantMessage = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
};

interface AiAssistantState {
  messages: AiAssistantMessage[];
  inputDraft: string;

  setFromServer: (messages: AiAssistantMessage[]) => void;
  setInputDraft: (value: string) => void;
  clearLocal: () => void;
}

export const useAiAssistantStore = create<AiAssistantState>((set) => ({
  messages: [],
  inputDraft: "",

  setFromServer: (messages) =>
    set({
      messages: messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        created_at: m.created_at,
      })),
    }),

  setInputDraft: (inputDraft) => set({ inputDraft }),

  clearLocal: () => set({ messages: [], inputDraft: "" }),
}));

/**
 * Clear local Zustand state; server history is cleared via API on logout.
 */
export function clearAiAssistantSession(): void {
  useAiAssistantStore.getState().clearLocal();
}

/**
 * Tender pipeline labels and main-path order (must match backend `tender_pipeline`).
 */

import type { TenderStatus } from "@/types";

/** Ordered happy-path stages for stepper UI. */
export const TENDER_MAIN_PIPELINE: readonly TenderStatus[] = [
  "search",
  "participation",
  "won",
  "execution",
  "completed",
] as const;

export const TENDER_STATUS_LABELS: Record<TenderStatus, string> = {
  search: "Поиск",
  participation: "Участие",
  won: "Выигран",
  lost: "Проигран",
  execution: "Реализация",
  completed: "Завершён",
};

export function tenderStatusLabel(status: string): string {
  return TENDER_STATUS_LABELS[status as TenderStatus] ?? status;
}

"use client";

import { cn } from "@/lib/utils";
import { Lock, CheckSquare, Square } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ChecklistItem {
  id: string;
  label: string;
  checked: boolean;
}

export interface Checklist {
  id: string;
  title: string;
  items: ChecklistItem[];
  /** Если true — чеклист блокирует переход (gate). */
  gatesTransition?: boolean;
}

export interface ChecklistPanelProps {
  /** Массив чеклистов. */
  checklists: Checklist[];
  /** Callback переключения элемента чеклиста. */
  onToggleItem?: (checklistId: string, itemId: string, checked: boolean) => void;
  /** Только для чтения. */
  readonly?: boolean;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Панель чеклистов с прогрессом, переключением элементов и индикацией гейта.
 *
 * Args:
 *     checklists: Массив чеклистов с элементами.
 *     onToggleItem: Callback при переключении элемента.
 *     readonly: Если true, элементы нельзя переключать.
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент панели чеклистов.
 */
export function ChecklistPanel({
  checklists,
  onToggleItem,
  readonly = false,
  className,
}: ChecklistPanelProps) {
  return (
    <div className={cn("space-y-4", className)}>
      {checklists.map((cl) => {
        const total = cl.items.length;
        const done = cl.items.filter((i) => i.checked).length;
        const percent = total > 0 ? Math.round((done / total) * 100) : 0;

        return (
          <div key={cl.id} className="rounded-xl border border-surface-200 bg-white p-4">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
              {cl.gatesTransition && (
                <Lock className="h-4 w-4 text-amber-500 shrink-0" aria-label="Блокирует переход" />
              )}
              <h4 className="text-sm font-semibold text-surface-800">{cl.title}</h4>
              <span className="ml-auto text-xs text-surface-400">
                {done}/{total}
              </span>
            </div>

            {/* Progress bar */}
            <div className="mb-3 h-1.5 w-full rounded-full bg-surface-100">
              <div
                className={cn(
                  "h-1.5 rounded-full transition-all",
                  percent === 100 ? "bg-emerald-500" : "bg-primary-500",
                )}
                style={{ width: `${percent}%` }}
              />
            </div>

            {/* Items */}
            <ul className="space-y-1.5">
              {cl.items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    disabled={readonly}
                    onClick={() => onToggleItem?.(cl.id, item.id, !item.checked)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors",
                      !readonly && "hover:bg-surface-50",
                      readonly && "cursor-default",
                    )}
                  >
                    {item.checked ? (
                      <CheckSquare className="h-4 w-4 shrink-0 text-primary-500" />
                    ) : (
                      <Square className="h-4 w-4 shrink-0 text-surface-300" />
                    )}
                    <span
                      className={cn(
                        "text-sm",
                        item.checked
                          ? "text-surface-400 line-through"
                          : "text-surface-700",
                      )}
                    >
                      {item.label}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

export default ChecklistPanel;

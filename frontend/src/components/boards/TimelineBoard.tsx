"use client";

import { useMemo } from "react";
import Link from "next/link";
import type { TaskResponse } from "@/types";
import { formatEnumLabel } from "@/lib/utils";

export type TimelineGroupBy = "assignee" | "type" | "priority" | "status";
export type TimelineDateField = "due_date" | "sla_deadline" | "created_at";

export interface TimelineBoardProps {
  tasks: TaskResponse[];
  groupBy: TimelineGroupBy;
  dateField: TimelineDateField;
  rangeDays: number;
  priorityColor: Record<string, string>;
  priorityLabel: Record<string, string>;
  statusLabel: Record<string, string>;
  onTaskClick?: (taskId: string) => void;
}

function localDayKey(d: Date): string {
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  return `${y}-${String(m).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function toDateOrNull(v: string | null | undefined): Date | null {
  if (!v) return null;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  return d;
}

function fmtDay(d: Date): string {
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
}

function fmtTime(d: Date): string {
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

export function TimelineBoard({
  tasks,
  groupBy,
  dateField,
  rangeDays,
  priorityColor,
  priorityLabel,
  statusLabel,
  onTaskClick,
}: TimelineBoardProps) {
  const { dayKeys, rowGroups, tasksByRowByDay } = useMemo(() => {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);

    const dayKeysLocal: string[] = [];
    const dayDates: Date[] = [];
    for (let i = 0; i < rangeDays; i += 1) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      dayDates.push(d);
      dayKeysLocal.push(localDayKey(d));
    }

    function rowLabel(t: TaskResponse): string {
      if (groupBy === "assignee") return t.assignee?.full_name ?? "Без исполнителя";
      if (groupBy === "type") return t.template?.category ?? t.template?.name ?? "Без типа";
      if (groupBy === "priority") return priorityLabel[t.priority] ?? t.priority;
      if (groupBy === "status") return statusLabel[t.status] ?? t.status;
      return "—";
    }

    const rowOrderPriority: Record<string, number> = {
      critical: 0,
      high: 1,
      medium: 2,
      low: 3,
    };

    const rowGroupsMap = new Map<string, string>();
    for (const t of tasks) {
      const label = rowLabel(t);
      rowGroupsMap.set(label, label);
    }

    const rowGroupsLocal = Array.from(rowGroupsMap.values());
    // Stable-ish ordering for priority mode.
    if (groupBy === "priority") {
      rowGroupsLocal.sort((a, b) => {
        const aRaw = Object.entries(priorityLabel).find(([, v]) => v === a)?.[0] ?? a;
        const bRaw = Object.entries(priorityLabel).find(([, v]) => v === b)?.[0] ?? b;
        return (rowOrderPriority[aRaw] ?? 999) - (rowOrderPriority[bRaw] ?? 999);
      });
    }

    const tasksByRowByDayLocal: Record<string, Record<string, TaskResponse[]>> = {};
    for (const rg of rowGroupsLocal) {
      tasksByRowByDayLocal[rg] = {};
      for (const dk of dayKeysLocal) tasksByRowByDayLocal[rg][dk] = [];
    }

    for (const t of tasks) {
      const dt = toDateOrNull((t as any)[dateField] as string | null);
      if (!dt) continue;
      const dk = localDayKey(dt);
      const row = rowLabel(t);
      if (!tasksByRowByDayLocal[row]) continue;
      if (!tasksByRowByDayLocal[row][dk]) continue;
      tasksByRowByDayLocal[row][dk].push(t);
    }

    // Sort tasks inside each cell.
    for (const row of rowGroupsLocal) {
      for (const dk of dayKeysLocal) {
        tasksByRowByDayLocal[row][dk].sort((a, b) => {
          const pRank = (p: string) => (p === "critical" ? 4 : p === "high" ? 3 : p === "medium" ? 2 : 1);
          return pRank(b.priority) - pRank(a.priority);
        });
      }
    }

    return {
      dayKeys: dayKeysLocal,
      rowGroups: rowGroupsLocal,
      tasksByRowByDay: tasksByRowByDayLocal,
      dayDates,
    };
  }, [tasks, groupBy, dateField, rangeDays, priorityLabel, priorityColor, statusLabel]);

  return (
    <div className="card overflow-hidden">
      <div className="overflow-auto">
        <div
          className="min-w-[900px]"
          style={{
            display: "grid",
            gridTemplateColumns: `minmax(220px, 260px) repeat(${rangeDays}, minmax(120px, 1fr))`,
          }}
        >
          {/* Header corner */}
          <div className="sticky left-0 z-10 bg-white border-b border-surface-100 px-4 py-3">
            <div className="text-sm font-semibold text-surface-700">Группа</div>
          </div>

          {dayKeys.map((dk, idx) => {
            const d = new Date(dayKeys[idx] + "T00:00:00");
            return (
              <div
                key={dk}
                className="bg-white border-b border-surface-100 px-3 py-3 text-center"
              >
                <div className="text-sm font-semibold text-surface-700">{fmtDay(d)}</div>
              </div>
            );
          })}

          {rowGroups.map((row) => (
            <div key={`rowWrap-${row}`} style={{ display: "contents" }}>
              <div
                key={`row-${row}`}
                className="sticky left-0 z-10 bg-white border-b border-surface-50 px-4 py-2"
              >
                <div className="text-sm font-medium text-surface-800 truncate">{row}</div>
              </div>
              {dayKeys.map((dk) => {
                const cellTasks = tasksByRowByDay[row]?.[dk] ?? [];
                return (
                  <div
                    key={`cell-${row}-${dk}`}
                    className="relative border-b border-surface-50 px-2 py-2"
                    style={{ minHeight: 64 }}
                  >
                    {cellTasks.slice(0, 6).map((t) => {
                      const dt = toDateOrNull((t as any)[dateField] as string | null);
                      const time = dt ? fmtTime(dt) : null;
                      const pColor = priorityColor[t.priority] ?? "#94a3b8";
                      return (
                        <Link
                          key={t.id}
                          href={`/tasks/${t.id}`}
                          className="mb-1 block rounded-lg border border-surface-200 bg-white/60 px-2 py-1 hover:bg-white"
                          style={{ boxShadow: `0 0 0 2px ${pColor}20 inset` }}
                          onClick={() => onTaskClick?.(t.id)}
                          title={t.title}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <div className="text-[11px] font-medium text-surface-900 truncate">
                                {t.title}
                              </div>
                              {time && (
                                <div className="mt-0.5 text-[10px] text-surface-500">{time}</div>
                              )}
                            </div>
                            <span
                              className="shrink-0 rounded-full px-1 text-[10px] font-medium"
                              style={{ backgroundColor: `${pColor}20`, color: pColor }}
                            >
                              {formatEnumLabel(t.priority, priorityLabel)}
                            </span>
                          </div>
                          <div className="mt-1 text-[10px] text-surface-500 line-clamp-1">
                            {formatEnumLabel(t.status, statusLabel)}
                          </div>
                        </Link>
                      );
                    })}
                    {cellTasks.length > 6 && (
                      <div className="mt-1 text-[11px] text-surface-400">
                        +{cellTasks.length - 6}
                      </div>
                    )}

                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


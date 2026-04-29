"use client";

import { useMemo } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Users, LayoutGrid } from "lucide-react";
import type { TaskResponse } from "@/types";
import type { UserListItem } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  getTaskDayInterval,
  isTerminalTaskStatus,
  localDayKey,
  type TaskDayInterval,
  type TimelineDateField,
} from "@/lib/timelineTaskIntervals";

export type MonthCalendarCellMode = "tasks" | "assignees";

export interface TasksMonthCalendarProps {
  tasks: TaskResponse[];
  assignees: UserListItem[];
  monthYm: string;
  dateField: TimelineDateField;
  hourStart: number;
  hourEndExclusive: number;
  cellMode: MonthCalendarCellMode;
  onCellModeChange: (mode: MonthCalendarCellMode) => void;
  selectedDay: string;
  /** Month navigation and default day selection (e.g. prev/next month). */
  onSelectDay: (dayKey: string) => void;
  /** If set, grid day cells use this instead of `onSelectDay` (e.g. jump to daily timeline). */
  onDayCellClick?: (dayKey: string) => void;
  priorityColor: Record<string, string>;
}

function avatarUrl(seed: string): string {
  const base = process.env.NEXT_PUBLIC_AVATAR_SERVICE_BASE_URL ?? "https://api.dicebear.com/9.x/thumbs/svg";
  return `${base}?seed=${encodeURIComponent(seed)}`;
}

const TASK_DUE_SOON_MINUTES = Math.max(
  1,
  Number.parseInt(process.env.NEXT_PUBLIC_TASK_DUE_SOON_MINUTES ?? "180", 10) || 180,
);

function dueUrgency(dueIso: string | null | undefined, status: string): "overdue" | "soon" | "none" {
  if (!dueIso || isTerminalTaskStatus(status)) return "none";
  const due = new Date(dueIso).getTime();
  if (!Number.isFinite(due)) return "none";
  const deltaMin = (due - Date.now()) / 60000;
  if (deltaMin < 0) return "overdue";
  if (deltaMin <= TASK_DUE_SOON_MINUTES) return "soon";
  return "none";
}

function parseYm(ym: string): { y: number; m: number } | null {
  const p = ym.split("-").map((x) => Number(x));
  if (p.length !== 2 || p.some((n) => Number.isNaN(n))) return null;
  return { y: p[0], m: p[1] };
}

function monthGridDays(anchorDayKey: string): { days: string[]; label: string } {
  const parts = anchorDayKey.split("-").map((x) => Number(x));
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) {
    const d = new Date();
    return monthGridDays(localDayKey(d));
  }
  const [y, mo] = parts;
  const monthStart = new Date(y, mo - 1, 1, 0, 0, 0, 0);
  const firstWeekday = (monthStart.getDay() + 6) % 7;
  const gridStart = new Date(monthStart);
  gridStart.setDate(1 - firstWeekday);
  const days: string[] = [];
  for (let i = 0; i < 42; i += 1) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    days.push(localDayKey(d));
  }
  return {
    days,
    label: monthStart.toLocaleDateString("ru-RU", { month: "long", year: "numeric" }),
  };
}

function prevMonthYm(ym: string): string {
  const p = parseYm(ym);
  if (!p) return ym;
  const d = new Date(p.y, p.m - 2, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function nextMonthYm(ym: string): string {
  const p = parseYm(ym);
  if (!p) return ym;
  const d = new Date(p.y, p.m, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function tasksOnDay(
  tasks: TaskResponse[],
  dayKey: string,
  dateField: TimelineDateField,
  hourStart: number,
  hourEndExclusive: number,
): TaskResponse[] {
  return tasks.filter(
    (t) => getTaskDayInterval(t, dayKey, dateField, hourStart, hourEndExclusive) !== null,
  );
}

function startHourForSort(t: TaskResponse, dayKey: string, dateField: TimelineDateField, hourStart: number, hourEndExclusive: number): number {
  const iv: TaskDayInterval | null = getTaskDayInterval(t, dayKey, dateField, hourStart, hourEndExclusive);
  return iv ? iv.start.getTime() : 0;
}

/**
 * Month grid for tasks: each day shows stacked assignee avatars or compact task tiles (see sketch).
 */
export function TasksMonthCalendar({
  tasks,
  assignees,
  monthYm,
  dateField,
  hourStart,
  hourEndExclusive,
  cellMode,
  onCellModeChange,
  selectedDay,
  onSelectDay,
  onDayCellClick,
  priorityColor,
}: TasksMonthCalendarProps) {
  const anchorDay = useMemo(() => {
    const p = parseYm(monthYm);
    if (!p) return `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}-01`;
    return `${p.y}-${String(p.m).padStart(2, "0")}-01`;
  }, [monthYm]);

  const { days, label } = useMemo(() => monthGridDays(anchorDay), [anchorDay]);

  const assigneeAvatarById = useMemo(() => {
    const m: Record<string, string> = {};
    for (const u of assignees) {
      if (u.avatar_url) m[String(u.id)] = String(u.avatar_url);
    }
    return m;
  }, [assignees]);

  return (
    <div className="card w-full overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-100 bg-surface-50/50 px-3 py-2 sm:px-4">
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="btn-ghost h-9 w-9 shrink-0 rounded-lg p-0"
            title="Предыдущий месяц"
            onClick={() => onSelectDay(`${prevMonthYm(monthYm)}-01`)}
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <h2 className="min-w-0 px-1 text-sm font-semibold capitalize text-surface-900 sm:text-base">{label}</h2>
          <button
            type="button"
            className="btn-ghost h-9 w-9 shrink-0 rounded-lg p-0"
            title="Следующий месяц"
            onClick={() => onSelectDay(`${nextMonthYm(monthYm)}-01`)}
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>
        <div className="flex rounded-lg border border-surface-200 bg-white p-0.5">
          <button
            type="button"
            title="Квадратики задач"
            onClick={() => onCellModeChange("tasks")}
            className={cn(
              "flex h-8 items-center gap-1 rounded-md px-2 text-xs font-medium",
              cellMode === "tasks" ? "bg-primary-600 text-white" : "text-surface-600 hover:text-surface-900",
            )}
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            Задачи
          </button>
          <button
            type="button"
            title="Круги исполнителей"
            onClick={() => onCellModeChange("assignees")}
            className={cn(
              "flex h-8 items-center gap-1 rounded-md px-2 text-xs font-medium",
              cellMode === "assignees" ? "bg-primary-600 text-white" : "text-surface-600 hover:text-surface-900",
            )}
          >
            <Users className="h-3.5 w-3.5" />
            Люди
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-px border-b border-surface-100 bg-surface-100 text-center text-[10px] font-semibold uppercase tracking-wide text-surface-500">
        {["пн", "вт", "ср", "чт", "пт", "сб", "вс"].map((w) => (
          <div key={w} className="bg-white py-1.5">
            {w}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-px bg-surface-200">
        {days.map((dk) => {
          const inMonth = dk.slice(0, 7) === monthYm;
          const isSelected = dk === selectedDay;
          const dayTasks = tasksOnDay(tasks, dk, dateField, hourStart, hourEndExclusive).sort(
            (a, b) =>
              startHourForSort(b, dk, dateField, hourStart, hourEndExclusive) -
              startHourForSort(a, dk, dateField, hourStart, hourEndExclusive),
          );
          const maxDots = cellMode === "assignees" ? 8 : 6;
          const overflowTasks = Math.max(0, dayTasks.length - maxDots);
          const overdueCount = dayTasks.filter((t) => dueUrgency(t.due_date, t.status) === "overdue").length;
          const soonCount = dayTasks.filter((t) => dueUrgency(t.due_date, t.status) === "soon").length;

          return (
            <button
              key={dk}
              type="button"
              onClick={() => (onDayCellClick ?? onSelectDay)(dk)}
              title={dk}
              className={cn(
                "flex min-h-[92px] flex-col items-stretch gap-1 bg-white p-1.5 text-left transition-colors sm:min-h-[104px] sm:p-2",
                !inMonth && "bg-surface-50/80 text-surface-400",
                isSelected && "ring-2 ring-inset ring-primary-500",
                overdueCount > 0 && "bg-red-50/40",
                overdueCount === 0 && soonCount > 0 && "bg-amber-50/30",
                inMonth && !isSelected && "hover:bg-primary-50/40",
              )}
            >
              <div className="flex items-start justify-between gap-1">
                <span
                  className={cn(
                    "inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold sm:h-7 sm:w-7 sm:text-xs",
                    isSelected ? "bg-primary-600 text-white" : inMonth ? "text-surface-800" : "text-surface-400",
                  )}
                >
                  {Number(dk.slice(-2))}
                </span>
                {(overdueCount > 0 || soonCount > 0) && (
                  <span
                    className={cn(
                      "rounded-full px-1.5 py-0.5 text-[9px] font-semibold",
                      overdueCount > 0 ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700",
                    )}
                    title={overdueCount > 0 ? `Просрочено: ${overdueCount}` : `Срок скоро: ${soonCount}`}
                  >
                    {overdueCount > 0 ? `!${overdueCount}` : `~${soonCount}`}
                  </span>
                )}
              </div>

              {cellMode === "assignees" ? (
                <div className="flex flex-1 flex-wrap content-start justify-start gap-0.5">
                  {(() => {
                    const seen = new Set<string>();
                    const ordered: TaskResponse[] = [];
                    for (const t of dayTasks) {
                      const id = t.assigned_to ? String(t.assigned_to) : "";
                      if (!id || seen.has(id)) continue;
                      seen.add(id);
                      ordered.push(t);
                    }
                    const show = ordered.slice(0, maxDots);
                    const restAssignees = Math.max(0, ordered.length - show.length);
                    return (
                      <>
                        {show.map((t) => {
                          const id = t.assigned_to ? String(t.assigned_to) : "";
                          const labelName = t.assignee?.full_name ?? "?";
                          const av = id ? assigneeAvatarById[id] : "";
                          const done = isTerminalTaskStatus(t.status);
                          return (
                            <div
                              key={`${dk}-${t.id}`}
                              className={cn(
                                "h-5 w-5 shrink-0 overflow-hidden rounded-full border border-surface-200 bg-surface-100 sm:h-6 sm:w-6",
                                done && "opacity-60 ring-1 ring-surface-300",
                              )}
                              title={`${labelName}${done ? " (завершена)" : ""}`}
                            >
                              {id ? (
                                <img
                                  src={av || avatarUrl(id)}
                                  alt=""
                                  className="h-full w-full object-cover"
                                  loading="lazy"
                                />
                              ) : (
                                <div className="flex h-full w-full items-center justify-center text-[8px] font-bold text-surface-500">
                                  ?
                                </div>
                              )}
                            </div>
                          );
                        })}
                        {restAssignees > 0 && (
                          <span className="text-[9px] font-semibold text-surface-500">+{restAssignees}</span>
                        )}
                      </>
                    );
                  })()}
                </div>
              ) : (
                <div className="flex flex-1 flex-wrap content-start gap-0.5">
                  {dayTasks.slice(0, maxDots).map((t) => {
                    const pc = priorityColor[t.priority] ?? "#94a3b8";
                    const done = isTerminalTaskStatus(t.status);
                    const urgency = dueUrgency(t.due_date, t.status);
                    const letter = (t.title.trim().charAt(0) || "·").toUpperCase();
                    return (
                      <Link
                        key={t.id}
                        href={`/tasks/${t.id}`}
                        onClick={(e) => e.stopPropagation()}
                        title={t.title}
                        className={cn(
                          "flex h-5 w-5 shrink-0 items-center justify-center rounded-sm border text-[9px] font-bold sm:h-6 sm:w-6 sm:text-[10px]",
                          done
                            ? "border-surface-300 bg-surface-100/90 text-surface-500 line-through decoration-surface-400 decoration-2"
                            : urgency === "overdue"
                              ? "border-red-300 bg-red-50 text-red-800 shadow-sm"
                              : urgency === "soon"
                                ? "border-amber-300 bg-amber-50 text-amber-800 shadow-sm"
                                : "border-black/10 bg-white text-surface-900 shadow-sm",
                        )}
                        style={
                          done
                            ? undefined
                            : urgency === "none"
                              ? {
                                borderColor: `${pc}99`,
                                boxShadow: `0 0 0 1px ${pc}40 inset`,
                              }
                              : undefined
                        }
                      >
                        {letter}
                      </Link>
                    );
                  })}
                  {overflowTasks > 0 && (
                    <span className="self-center text-[9px] font-semibold text-surface-500">+{overflowTasks}</span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

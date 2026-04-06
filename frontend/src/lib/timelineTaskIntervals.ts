/**
 * Helpers for task time intervals on the calendar timeline (local day, visible hours).
 */

import type { TaskResponse } from "@/types";

const MS_MIN = 60_000;
const DEFAULT_DURATION_MIN = 60;

export function localDayKey(d: Date): string {
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  return `${y}-${String(m).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function toDateOrNull(v: string | null | undefined): Date | null {
  if (!v) return null;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  return d;
}

export type TaskDayInterval = { start: Date; end: Date };

/**
 * Compute [start, end) for a task on selectedDate, clamped to visible hour range.
 */
/** Which date field drives placement on the day timeline / month grid. */
export type TimelineDateField = "due_date" | "sla_deadline" | "created_at";

export function getTaskDayInterval(
  task: TaskResponse,
  selectedDate: string,
  dateField: TimelineDateField,
  hourStart: number,
  hourEndExclusive: number,
): TaskDayInterval | null {
  const parts = selectedDate.split("-").map((x) => Number(x));
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return null;
  const [y, mo, d] = parts;

  const onDay = (dt: Date | null) => dt !== null && localDayKey(dt) === selectedDate;

  const due = toDateOrNull(task.due_date);
  const started = toDateOrNull(task.started_at);
  const anchor =
    dateField === "due_date"
      ? toDateOrNull(task.due_date)
      : dateField === "sla_deadline"
        ? toDateOrNull(task.sla_deadline)
        : toDateOrNull(task.created_at);

  const visStart = new Date(y, mo - 1, d, hourStart, 0, 0, 0);
  const visEnd = new Date(y, mo - 1, d, hourEndExclusive, 0, 0, 0);

  let s: Date;
  let e: Date;

  if (started && onDay(started) && due && onDay(due)) {
    s = started;
    e = due;
    if (e.getTime() <= s.getTime()) {
      e = new Date(s.getTime() + DEFAULT_DURATION_MIN * MS_MIN);
    }
  } else if (due && onDay(due)) {
    e = due;
    s = new Date(e.getTime() - DEFAULT_DURATION_MIN * MS_MIN);
  } else if (started && onDay(started)) {
    s = started;
    e = new Date(s.getTime() + DEFAULT_DURATION_MIN * MS_MIN);
  } else if (anchor && onDay(anchor)) {
    e = anchor;
    s = new Date(e.getTime() - DEFAULT_DURATION_MIN * MS_MIN);
  } else {
    return null;
  }

  let ns = s.getTime() < visStart.getTime() ? visStart : s;
  let ne = e.getTime() > visEnd.getTime() ? visEnd : e;
  if (ne.getTime() <= ns.getTime()) {
    ne = new Date(ns.getTime() + 15 * MS_MIN);
  }
  return { start: ns, end: ne };
}

export function intervalDurationMs(iv: TaskDayInterval): number {
  return Math.max(15 * MS_MIN, iv.end.getTime() - iv.start.getTime());
}

/** True when the task is finished (UI: strikethrough, muted). */
export function isTerminalTaskStatus(status: string): boolean {
  return status === "done" || status === "completed" || status === "closed";
}

export function columnKeyOfTask(
  t: TaskResponse,
  groupBy: "assignee" | "type" | "priority" | "status",
): string {
  if (groupBy === "assignee") return t.assigned_to ? String(t.assigned_to) : "none";
  if (groupBy === "type") return t.template_id ? String(t.template_id) : "none";
  if (groupBy === "priority") return t.priority;
  if (groupBy === "status") return t.status;
  return "none";
}

export type IntervalForResolve = { taskId: string; startMs: number; endMs: number; durationMs: number };

/**
 * Place the moved task exactly at [startMs, endMs]. Every other task keeps its duration; if it overlaps
 * any already placed interval (including the moved task), it is shifted forward to start at the latest
 * overlapping end — never pulling the moved task away from the drop position (no “swap” with an earlier bar).
 */
export function resolveColumnOverlaps(
  others: IntervalForResolve[],
  moved: { taskId: string; startMs: number; endMs: number },
): Map<string, { startMs: number; endMs: number }> {
  const placed = new Map<string, { startMs: number; endMs: number }>();
  placed.set(moved.taskId, { startMs: moved.startMs, endMs: moved.endMs });

  const rest = others.filter((o) => o.taskId !== moved.taskId);
  rest.sort((a, b) => a.startMs - b.startMs || a.taskId.localeCompare(b.taskId));

  for (const o of rest) {
    const d = o.durationMs;
    let s = o.startMs;
    let safety = 0;
    while (safety < 64) {
      safety += 1;
      const e = s + d;
      let maxPush = s;
      for (const q of placed.values()) {
        if (s < q.endMs && e > q.startMs) {
          maxPush = Math.max(maxPush, q.endMs);
        }
      }
      if (maxPush === s) {
        placed.set(o.taskId, { startMs: s, endMs: e });
        break;
      }
      s = maxPush;
    }
    if (!placed.has(o.taskId)) {
      placed.set(o.taskId, { startMs: s, endMs: s + d });
    }
  }

  return placed;
}

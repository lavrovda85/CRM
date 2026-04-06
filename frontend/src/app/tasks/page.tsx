"use client";

import { Suspense, useEffect, useLayoutEffect, useState, useCallback, useMemo } from "react";
import {
  LayoutGrid,
  List,
  Filter,
  Plus,
  Calendar,
  CalendarDays,
  Check,
  User,
  ChevronDown,
  X,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { flushSync } from "react-dom";
import { useSearchParams, useRouter } from "next/navigation";
import { ApiError, fetchTasks, deleteTask, transitionTask, updateTask, fetchUsers, type UserListItem } from "@/lib/api";
import { cn, formatEnumLabel } from "@/lib/utils";
import type { TaskResponse } from "@/types";
import {
  getTaskDayInterval,
  intervalDurationMs,
  isTerminalTaskStatus,
  type TimelineDateField,
} from "@/lib/timelineTaskIntervals";
import { useUiStore } from "@/stores/ui";
import { CreateTaskModal } from "@/components/tasks/CreateTaskModal";
import { KanbanBoard, type KanbanColumn, type KanbanCard } from "@/components/boards/KanbanBoard";
import { TimelineHoursBoard } from "@/components/boards/TimelineHoursBoard";
import {
  TasksMonthCalendar,
  type MonthCalendarCellMode,
} from "@/components/boards/TasksMonthCalendar";

const KANBAN_COLUMNS: KanbanColumn[] = [
  { id: "new", title: "Новая", color: "#94a3b8" },
  { id: "dispatched", title: "Назначена", color: "#38bdf8" },
  { id: "in_progress", title: "В работе", color: "#3b82f6" },
  { id: "testing", title: "Тестирование", color: "#fbbf24" },
  { id: "photo_report", title: "Фотоотчёт", color: "#8b5cf6" },
  { id: "act_signing", title: "Подписание акта", color: "#f97316" },
  { id: "done", title: "Завершена", color: "#22c55e" },
  { id: "closed", title: "Закрыта", color: "#9ca3af" },
];

const KANBAN_IDS = new Set(KANBAN_COLUMNS.map((c) => c.id));

const priorityColor: Record<string, string> = {
  low: "#22c55e",
  medium: "#eab308",
  high: "#f97316",
  critical: "#ef4444",
};

const priorityBadgeClass: Record<string, string> = {
  low: "bg-green-50 text-green-700",
  medium: "bg-yellow-50 text-yellow-700",
  high: "bg-orange-50 text-orange-700",
  critical: "bg-red-50 text-red-700",
};

const statusLabel: Record<string, string> = {
  new: "Новая",
  dispatched: "Назначена",
  in_progress: "В работе",
  testing: "Тестирование",
  photo_report: "Фотоотчёт",
  act_signing: "Подписание акта",
  done: "Завершена",
  completed: "Завершена",
  closed: "Закрыта",
};

const priorityLabel: Record<string, string> = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
  critical: "Критический",
};
const TASKS_VIEW_SESSION_KEY        = "tasks_last_view";
const TASKS_CAL_DATE_SESSION_KEY    = "tasks_last_calendar_date";
const TASKS_FILTERS_SESSION_KEY     = "tasks_last_filters";
const TASKS_FILTERS_OPEN_SESSION_KEY = "tasks_filters_open";
const TASKS_STAFF_IDS_SESSION_KEY   = "tasks_timeline_staff_ids";

function sessionGet<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = sessionStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function sessionSet(key: string, value: unknown): void {
  if (typeof window === "undefined") return;
  try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* quota */ }
}
const TIMELINE_HOUR_START = Math.max(
  0,
  Math.min(23, Number.parseInt(process.env.NEXT_PUBLIC_TASK_TIMELINE_HOUR_START ?? "8", 10) || 8),
);
const TIMELINE_HOUR_END = Math.max(
  TIMELINE_HOUR_START + 1,
  Math.min(24, Number.parseInt(process.env.NEXT_PUBLIC_TASK_TIMELINE_HOUR_END ?? "20", 10) || 20),
);

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

interface TasksHeaderToolbarProps {
  view: "kanban" | "list" | "timeline" | "month";
  onViewChange: (next: "kanban" | "list" | "timeline" | "month") => void;
  filtersOpen: boolean;
  onToggleFilters: () => void;
  onCreateClick: () => void;
}

/** Compact tasks actions for the sticky app header (all views: kanban, list, timeline). */
function TasksHeaderToolbar({
  view,
  onViewChange,
  filtersOpen,
  onToggleFilters,
  onCreateClick,
}: TasksHeaderToolbarProps) {
  return (
    <div className="flex shrink-0 items-center gap-1 sm:gap-2">
      <button
        type="button"
        onClick={onCreateClick}
        className="btn-primary hidden h-9 gap-1.5 whitespace-nowrap px-3 py-0 text-sm lg:inline-flex"
        title="Создать задачу"
      >
        <Plus className="h-4 w-4 shrink-0" />
        Создать задачу
      </button>
      <button
        type="button"
        onClick={onToggleFilters}
        className={cn(
          "btn-ghost h-9 gap-1 px-2 py-0 text-sm sm:gap-1.5 sm:px-3",
          filtersOpen && "bg-surface-100",
        )}
        aria-expanded={filtersOpen}
      >
        <Filter className="h-4 w-4 shrink-0" />
        <span className="hidden sm:inline">Фильтры</span>
        <ChevronDown
          className={cn(
            "hidden h-3.5 w-3.5 shrink-0 transition-transform sm:block",
            filtersOpen && "rotate-180",
          )}
        />
      </button>
      <div className="flex shrink-0 rounded-lg border border-surface-200 bg-white p-0.5">
        <button
          type="button"
          onClick={() => onViewChange("kanban")}
          title="Канбан"
          className={cn(
            "rounded-md px-2 py-1.5 transition-colors sm:px-2.5",
            view === "kanban" ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900",
          )}
        >
          <LayoutGrid className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onViewChange("list")}
          title="Список"
          className={cn(
            "rounded-md px-2 py-1.5 transition-colors sm:px-2.5",
            view === "list" ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900",
          )}
        >
          <List className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onViewChange("timeline")}
          title="График по часам"
          className={cn(
            "rounded-md px-2 py-1.5 transition-colors sm:px-2.5",
            view === "timeline" ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900",
          )}
        >
          <Calendar className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onViewChange("month")}
          title="Месяц"
          className={cn(
            "rounded-md px-2 py-1.5 transition-colors sm:px-2.5",
            view === "month" ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900",
          )}
        >
          <CalendarDays className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function taskToCard(task: TaskResponse): KanbanCard {
  const badges: { label: string; color: string }[] = [
    { label: priorityLabel[task.priority] ?? task.priority, color: priorityColor[task.priority] ?? "#94a3b8" },
  ];
  if (task.due_date) {
    badges.push({
      label: new Date(task.due_date).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }),
      color: "#6b7280",
    });
  }
  const co = task.co_assignees ?? [];
  const coHint = co.length > 0 ? ` +${co.length}` : "";
  const subtitle = task.assignee?.full_name
    ? `${task.assignee.full_name}${coHint}`
    : co.length > 0
      ? `${co.length} соисполн.`
      : undefined;

  const observerNames = (task.observers ?? []).map((o) => o.full_name).filter(Boolean);
  return {
    id: task.id,
    title: task.title,
    subtitle,
    badges,
    observerNames,
    completed: isTerminalTaskStatus(task.status),
  };
}

export default function TasksPage() {
  return (
    <Suspense>
      <TasksPageInner />
    </Suspense>
  );
}

function TasksPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [view, setView] = useState<"kanban" | "list" | "timeline" | "month">(() => {
    const qv = searchParams.get("view");
    if (qv === "list" || qv === "timeline" || qv === "month") return qv;
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem(TASKS_VIEW_SESSION_KEY);
      if (saved === "kanban" || saved === "list" || saved === "timeline" || saved === "month") return saved;
    }
    return "kanban";
  });
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [assignees, setAssignees] = useState<UserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState<boolean>(() => {
    // Open panel automatically if URL carries filter params
    if (searchParams.get("status") || searchParams.get("overdue")) return true;
    return sessionGet(TASKS_FILTERS_OPEN_SESSION_KEY, false);
  });
  const [filters, setFilters] = useState<Record<string, string>>(() => {
    // URL query params take precedence over session on first load
    const urlStatus  = searchParams.get("status");
    const urlOverdue = searchParams.get("overdue");
    if (urlStatus || urlOverdue) {
      const f: Record<string, string> = {};
      if (urlStatus)  f.status  = urlStatus;
      if (urlOverdue) f.overdue = urlOverdue;
      return f;
    }
    return sessionGet(TASKS_FILTERS_SESSION_KEY, {});
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [createPrefill, setCreatePrefill] = useState<{ assignedTo?: string; startedAt?: string; dueDate?: string } | undefined>();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const timelineDateField: TimelineDateField = "due_date";
  const [timelineSelectedDate, setTimelineSelectedDate] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem(TASKS_CAL_DATE_SESSION_KEY);
      if (saved && /^\d{4}-\d{2}-\d{2}$/.test(saved)) return saved;
    }
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  });
  const timelineHourStart = TIMELINE_HOUR_START;
  const timelineHourEndExclusive = TIMELINE_HOUR_END;

  const [timelineStaffIds, setTimelineStaffIds] = useState<string[] | null>(() =>
    sessionGet<string[] | null>(TASKS_STAFF_IDS_SESSION_KEY, null),
  );

  const setHeaderToolbar = useUiStore((s) => s.setHeaderToolbar);

  // Persist filters, panel open state, and staff filter to session storage on change
  useEffect(() => { sessionSet(TASKS_FILTERS_SESSION_KEY, filters); }, [filters]);
  useEffect(() => { sessionSet(TASKS_FILTERS_OPEN_SESSION_KEY, filtersOpen); }, [filtersOpen]);
  useEffect(() => { sessionSet(TASKS_STAFF_IDS_SESSION_KEY, timelineStaffIds); }, [timelineStaffIds]);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await fetchTasks({ ...filters, limit: 200 });
      setTasks(res.items);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Failed to load tasks";
      setLoadError(msg);
      /* Do not clear tasks on failure — avoids empty board after a transient API error. */
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const refetchTasksSilent = useCallback(async () => {
    try {
      const res = await fetchTasks({ ...filters, limit: 200 });
      setTasks(res.items);
      setLoadError(null);
    } catch {
      /* keep current state */
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const pageSize = 200;
        let offset = 0;
        const all: UserListItem[] = [];
        while (true) {
          const res = await fetchUsers({ is_active: true, limit: pageSize, offset });
          all.push(...res.items);
          offset += res.items.length;
          if (offset >= res.total || res.items.length < pageSize) break;
        }
        if (!cancelled) setAssignees(all);
      } catch {
        /* keep empty assignees list */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const qv = searchParams.get("view");
    const saved =
      typeof window !== "undefined" ? sessionStorage.getItem(TASKS_VIEW_SESSION_KEY) : null;
    const nextView =
      qv === "list" || qv === "timeline" || qv === "month"
        ? qv
        : saved === "kanban" || saved === "list" || saved === "timeline" || saved === "month"
          ? saved
          : "kanban";
    if (nextView !== view) {
      setView(nextView);
    }
  }, [searchParams, view]);

  const monthCellMode: MonthCalendarCellMode =
    searchParams.get("month_cell") === "assignees" ? "assignees" : "tasks";

  const setViewWithQuery = useCallback(
    (next: "kanban" | "list" | "timeline" | "month") => {
      if (typeof window !== "undefined") sessionStorage.setItem(TASKS_VIEW_SESSION_KEY, next);
      setView(next);
      const params = new URLSearchParams(searchParams.toString());
      if (next === "kanban") params.delete("view");
      else params.set("view", next);
      router.replace(`/tasks${params.toString() ? `?${params.toString()}` : ""}`, { scroll: false });
    },
    [searchParams, router],
  );

  useEffect(() => {
    const qpDate = searchParams.get("calendar_date");
    if (qpDate && qpDate !== timelineSelectedDate) {
      setTimelineSelectedDate(qpDate);
      if (typeof window !== "undefined") sessionStorage.setItem(TASKS_CAL_DATE_SESSION_KEY, qpDate);
    }
  }, [searchParams, timelineSelectedDate]);

  useEffect(() => {
    const raw = searchParams.get("timeline_staff");
    if (raw === null) {
      setTimelineStaffIds(null);
      return;
    }
    if (raw === "") {
      setTimelineStaffIds([]);
      return;
    }
    setTimelineStaffIds(raw.split(",").map((s) => s.trim()).filter(Boolean));
  }, [searchParams]);

  function replaceTasksQuery(mutate: (p: URLSearchParams) => void) {
    const params = new URLSearchParams(searchParams.toString());
    mutate(params);
    const q = params.toString();
    router.replace(`/tasks${q ? `?${q}` : ""}`, { scroll: false });
  }

  const setMonthCellMode = useCallback(
    (mode: MonthCalendarCellMode) => {
      const params = new URLSearchParams(searchParams.toString());
      if (mode === "tasks") params.delete("month_cell");
      else params.set("month_cell", "assignees");
      const q = params.toString();
      router.replace(`/tasks${q ? `?${q}` : ""}`, { scroll: false });
    },
    [searchParams, router],
  );

  const setCalendarDayKey = useCallback(
    (dayKey: string) => {
      if (typeof window !== "undefined") sessionStorage.setItem(TASKS_CAL_DATE_SESSION_KEY, dayKey);
      setTimelineSelectedDate(dayKey);
      const params = new URLSearchParams(searchParams.toString());
      params.set("calendar_date", dayKey);
      const q = params.toString();
      router.replace(`/tasks${q ? `?${q}` : ""}`, { scroll: false });
    },
    [searchParams, router],
  );

  /** From month grid: same date + switch to daily hour timeline in one navigation. */
  const goToTimelineForDay = useCallback(
    (dayKey: string) => {
      if (typeof window !== "undefined") {
        sessionStorage.setItem(TASKS_CAL_DATE_SESSION_KEY, dayKey);
        sessionStorage.setItem(TASKS_VIEW_SESSION_KEY, "timeline");
      }
      setTimelineSelectedDate(dayKey);
      setView("timeline");
      const params = new URLSearchParams(searchParams.toString());
      params.set("calendar_date", dayKey);
      params.set("view", "timeline");
      router.replace(`/tasks${params.toString() ? `?${params.toString()}` : ""}`, { scroll: false });
    },
    [searchParams, router],
  );

  const tasksForCalendar = useMemo(() => {
    if (timelineStaffIds === null) return tasks;
    const allowed = new Set(timelineStaffIds);
    return tasks.filter((t) => {
      const id = t.assigned_to ? String(t.assigned_to) : "";
      return !id || allowed.has(id);
    });
  }, [tasks, timelineStaffIds]);

  function setTimelineStaffFilter(next: string[] | null) {
    setTimelineStaffIds(next);
    replaceTasksQuery((p) => {
      if (next === null) p.delete("timeline_staff");
      else if (next.length === 0) p.set("timeline_staff", "");
      else p.set("timeline_staff", next.join(","));
    });
  }

  useEffect(() => {
    if (searchParams.get("new") === "1") {
      setCreateOpen(true);
      const params = new URLSearchParams(searchParams.toString());
      params.delete("new");
      router.replace(`/tasks${params.toString() ? `?${params.toString()}` : ""}`, { scroll: false });
    }
  }, [searchParams, router]);

  useLayoutEffect(() => {
    setHeaderToolbar(
      <TasksHeaderToolbar
        view={view}
        onViewChange={setViewWithQuery}
        filtersOpen={filtersOpen}
        onToggleFilters={() => setFiltersOpen((o) => !o)}
        onCreateClick={() => setCreateOpen(true)}
      />,
    );
    return () => setHeaderToolbar(null);
  }, [view, filtersOpen, setHeaderToolbar, setViewWithQuery]);

  const columns = [...KANBAN_COLUMNS];
  const unmapped = tasks.filter((t) => !KANBAN_IDS.has(t.status));
  if (unmapped.length > 0) {
    columns.push({ id: "_other", title: "Прочее", color: "#94a3b8" });
  }

  const cards: Record<string, KanbanCard[]> = {};
  for (const col of columns) {
    cards[col.id] = tasks
      .filter((t) => (col.id === "_other" ? !KANBAN_IDS.has(t.status) : t.status === col.id))
      .map(taskToCard);
  }

  async function handleCardMove(cardId: string, _fromCol: string, toCol: string) {
    if (toCol === "_other") return;

    const prev = [...tasks];
    setTasks((cur) => cur.map((t) => (t.id === cardId ? { ...t, status: toCol } : t)));

    try {
      await transitionTask(cardId, toCol);
    } catch {
      setTasks(prev);
    }
  }

  function handleCardClick(cardId: string) {
    router.push(`/tasks/${cardId}`);
  }

  function setFilter(key: string, value: string) {
    setFilters((prev) => {
      const next = { ...prev };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  }

  async function handleDelete(taskId: string) {
    if (!confirm("Удалить задачу? Это действие нельзя отменить.")) return;
    setDeletingId(taskId);
    setDeleteError(null);
    try {
      await deleteTask(taskId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка удаления";
      setDeleteError(msg);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleQuickComplete(taskId: string) {
    const target = tasks.find((t) => t.id === taskId);
    if (!target || isTerminalTaskStatus(target.status)) return;
    const prev = [...tasks];
    setTasks((cur) => cur.map((t) => (t.id === taskId ? { ...t, status: "done" } : t)));
    try {
      const updated = await transitionTask(taskId, "done", "Quick complete from board/list");
      setTasks((cur) => cur.map((t) => (t.id === taskId ? updated : t)));
    } catch {
      setTasks(prev);
    }
  }

  function handleCreated(task: TaskResponse) {
    setTasks((prev) => [task, ...prev]);
    refetchTasksSilent();
  }

  function handleTimelineMove(
    taskId: string,
    destination: { toRowKey: string; toDayKey: string; toHour: number },
  ) {
    const dayParts = destination.toDayKey.split("-").map((x) => Number(x));
    if (dayParts.length !== 3 || dayParts.some((n) => Number.isNaN(n))) return;
    const [y, m, d] = dayParts;

    const assigned_to = destination.toRowKey === "none" ? null : destination.toRowKey;

    let revert: TaskResponse[] = [];
    let patch: { id: string; body: Record<string, unknown> } | null = null;

    flushSync(() => {
      setTasks((prev) => {
        const dragged = prev.find((t) => t.id === taskId);
        if (!dragged) return prev;

        const ivOld = getTaskDayInterval(
          dragged,
          destination.toDayKey,
          timelineDateField,
          timelineHourStart,
          timelineHourEndExclusive,
        );
        const durationMs = ivOld ? intervalDurationMs(ivOld) : 60 * 60_000;

        const newStart = new Date(y, m - 1, d, destination.toHour, 0, 0, 0);
        const visEnd = new Date(y, m - 1, d, timelineHourEndExclusive, 0, 0, 0);
        let newEnd = new Date(newStart.getTime() + durationMs);
        if (newEnd.getTime() > visEnd.getTime()) newEnd = visEnd;
        if (newEnd.getTime() <= newStart.getTime()) newEnd = new Date(newStart.getTime() + 15 * 60_000);

        const sameAssignee =
          (dragged.assigned_to ?? null) === assigned_to ||
          String(dragged.assigned_to ?? "") === String(assigned_to ?? "");
        const sameTime =
          ivOld &&
          Math.abs(ivOld.start.getTime() - newStart.getTime()) < 1000 &&
          Math.abs(ivOld.end.getTime() - newEnd.getTime()) < 1000;
        if (sameAssignee && sameTime) return prev;

        const body: Record<string, unknown> = {
          started_at: newStart.toISOString(),
          due_date: newEnd.toISOString(),
          assigned_to,
        };

        revert = prev;
        patch = { id: taskId, body };

        return prev.map((t) =>
          t.id === taskId
            ? {
                ...t,
                started_at: newStart.toISOString(),
                due_date: newEnd.toISOString(),
                assigned_to,
              }
            : t,
        );
      });
    });

    if (!patch) return;

    const capturedPatch = patch as { id: string; body: Record<string, unknown> };
    void (async () => {
      try {
        const updated = await updateTask(capturedPatch.id, capturedPatch.body);
        setTasks((cur) => cur.map((t) => (t.id === updated.id ? updated : t)));
        setLoadError(null);
      } catch (e) {
        setLoadError(
          e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка обновления",
        );
        setTasks(revert);
        await refetchTasksSilent();
      }
    })();
  }

  function handleSlotClick(slot: { rowKey: string; dayKey: string; hour: number }) {
    const pad = (n: number) => String(n).padStart(2, "0");
    const startedAt = `${slot.dayKey}T${pad(slot.hour)}:00`;
    const dueHour = Math.min(slot.hour + 1, 23);
    const dueDate = `${slot.dayKey}T${pad(dueHour)}:00`;
    const assignedTo = slot.rowKey !== "none" ? slot.rowKey : undefined;
    setCreatePrefill({ assignedTo, startedAt, dueDate });
    setCreateOpen(true);
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[100rem] space-y-4 overflow-x-hidden p-3 sm:p-4 lg:p-6">
      {loadError && (
        <div
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
          role="alert"
        >
          <span>Не удалось загрузить задачи: {loadError}</span>
          <button type="button" onClick={() => load()} className="btn-primary btn-sm shrink-0">
            Повторить
          </button>
        </div>
      )}
      {deleteError && (
        <div
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
          role="alert"
        >
          <span>Не удалось удалить задачу: {deleteError}</span>
          <button
            type="button"
            onClick={() => setDeleteError(null)}
            className="btn-ghost btn-sm shrink-0"
          >
            Закрыть
          </button>
        </div>
      )}

      {/* Filters Bar */}
      {filtersOpen && (
        <div className="card flex flex-wrap items-center gap-3 p-3">
          <select
            className="input max-w-[160px]"
            value={filters.status ?? ""}
            onChange={(e) => setFilter("status", e.target.value)}
          >
            <option value="">Все статусы</option>
            {KANBAN_COLUMNS.map((c) => (
              <option key={c.id} value={c.id}>{c.title}</option>
            ))}
          </select>
          <select
            className="input max-w-[160px]"
            value={filters.priority ?? ""}
            onChange={(e) => setFilter("priority", e.target.value)}
          >
            <option value="">Все приоритеты</option>
            <option value="low">Низкий</option>
            <option value="medium">Средний</option>
            <option value="high">Высокий</option>
            <option value="critical">Критический</option>
          </select>
          {Object.keys(filters).length > 0 && (
            <button onClick={() => setFilters({})} className="btn-ghost btn-sm text-red-600 gap-1">
              <X className="h-3.5 w-3.5" /> Сбросить
            </button>
          )}
          {(view === "timeline" || view === "month") && assignees.length > 0 && (
            <div className="flex w-full flex-col gap-2 border-t border-surface-100 pt-3">
              <div className="text-xs font-semibold text-surface-600">
                {view === "month" ? "Календарь: кого показывать" : "Календарь: исполнители в колонках"}
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="rounded border-surface-300"
                  checked={timelineStaffIds === null}
                  onChange={(e) => {
                    if (e.target.checked) setTimelineStaffFilter(null);
                    else setTimelineStaffFilter([]);
                  }}
                />
                <span>Все сотрудники</span>
              </label>
              <div className="flex max-h-40 flex-col gap-1.5 overflow-y-auto pl-0.5">
                {assignees.map((u) => {
                  const id = String(u.id);
                  const checked = timelineStaffIds === null ? true : timelineStaffIds.includes(id);
                  return (
                    <label key={id} className="flex cursor-pointer items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        className="rounded border-surface-300"
                        checked={checked}
                        onChange={(e) => {
                          if (timelineStaffIds === null) {
                            if (!e.target.checked) {
                              setTimelineStaffFilter(
                                assignees.map((x) => String(x.id)).filter((x) => x !== id),
                              );
                            }
                            return;
                          }
                          const set = new Set(timelineStaffIds);
                          if (e.target.checked) set.add(id);
                          else set.delete(id);
                          const next = [...set];
                          if (next.length >= assignees.length) setTimelineStaffFilter(null);
                          else setTimelineStaffFilter(next);
                        }}
                      />
                      <span className="truncate">{u.full_name}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Kanban View with Drag & Drop */}
      {view === "kanban" && (
        <KanbanBoard
          columns={columns}
          cards={cards}
          onCardMove={handleCardMove}
          onCardClick={handleCardClick}
          renderCard={(card) => {
            const names = card.observerNames ?? [];
            const visible = names.slice(0, 3);
            const rest = Math.max(0, names.length - visible.length);
            return (
              <div
                role="button"
                tabIndex={0}
                onClick={() => handleCardClick(card.id)}
                onKeyDown={(e) => e.key === "Enter" && handleCardClick(card.id)}
                className="rounded-lg border border-surface-200 bg-white p-3 shadow-sm hover:shadow-md hover:border-primary-200 transition-all cursor-pointer group"
              >
                <p
                  className={cn(
                    "text-sm font-medium line-clamp-2 group-hover:text-primary-700",
                    card.completed
                      ? "text-surface-500 line-through decoration-surface-400/85 decoration-2"
                      : "text-surface-800",
                  )}
                >
                  {card.title}
                </p>
                {!card.completed && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      void handleQuickComplete(card.id);
                    }}
                    className="mt-2 inline-flex h-7 items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 text-[11px] font-medium text-emerald-700 hover:bg-emerald-100"
                    title="Завершить задачу"
                  >
                    <Check className="h-3.5 w-3.5" />
                    Завершить
                  </button>
                )}

                {card.subtitle && (
                  <p className="mt-1 text-xs text-surface-500 line-clamp-1">{card.subtitle}</p>
                )}

                {card.badges && card.badges.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {card.badges.map((b) => (
                      <span
                        key={b.label}
                        className="inline-block rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                        style={{ backgroundColor: `${b.color}20`, color: b.color }}
                      >
                        {b.label}
                      </span>
                    ))}
                  </div>
                )}

                {names.length > 0 && (
                  <div className="mt-2">
                    <div className="text-[10px] font-semibold text-surface-500">Наблюдатели</div>
                    <ul className="mt-1 space-y-0.5">
                      {visible.map((n) => (
                        <li key={n} className="text-[10px] text-surface-600 line-clamp-1">
                          {n}
                        </li>
                      ))}
                      {rest > 0 && (
                        <li className="text-[10px] text-surface-500">+{rest}</li>
                      )}
                    </ul>
                  </div>
                )}
              </div>
            );
          }}
        />
      )}

      {/* List View */}
      {view === "list" && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-100 text-left text-surface-500">
                  <th className="px-4 py-3 font-medium">Название</th>
                  <th className="px-4 py-3 font-medium">Статус</th>
                  <th className="px-4 py-3 font-medium">Приоритет</th>
                  <th className="hidden px-4 py-3 font-medium md:table-cell">Исполнитель</th>
                  <th className="hidden px-4 py-3 font-medium lg:table-cell">Срок</th>
                  <th className="px-4 py-3 font-medium w-24"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-50">
                {tasks.map((task) => (
                  <tr key={task.id} className="hover:bg-surface-50 transition-colors">
                    <td className="px-4 py-3">
                      <Link
                        href={`/tasks/${task.id}`}
                        className={cn(
                          "font-medium hover:text-primary-600",
                          isTerminalTaskStatus(task.status)
                            ? "text-surface-500 line-through decoration-surface-400/85 decoration-2"
                            : "text-surface-900",
                        )}
                      >
                        {task.title}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${
                        task.status === "done" || task.status === "completed"
                          ? "bg-green-50 text-green-700"
                          : task.status === "in_progress"
                          ? "bg-blue-50 text-blue-700"
                          : task.status === "testing"
                          ? "bg-amber-50 text-amber-700"
                          : "bg-surface-100 text-surface-600"
                      }`}>
                        {formatEnumLabel(task.status, statusLabel)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${priorityBadgeClass[task.priority] ?? ""}`}>
                        {formatEnumLabel(task.priority, priorityLabel)}
                      </span>
                    </td>
                    <td className="hidden px-4 py-3 md:table-cell">
                      {task.assignee || (task.co_assignees ?? []).length > 0 ? (
                        <div className="flex items-center gap-1.5">
                          <User className="h-3.5 w-3.5 text-surface-400" />
                          <span className="text-surface-600">
                            {task.assignee?.full_name ?? "—"}
                            {(task.co_assignees ?? []).length > 0
                              ? ` (+${(task.co_assignees ?? []).length})`
                              : ""}
                          </span>
                        </div>
                      ) : (
                        <span className="text-surface-300">—</span>
                      )}
                    </td>
                    <td className="hidden px-4 py-3 lg:table-cell">
                      {task.due_date ? (
                        <span className="text-surface-500">
                          {new Date(task.due_date).toLocaleDateString("ru-RU")}
                        </span>
                      ) : (
                        <span className="text-surface-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          void handleQuickComplete(task.id);
                        }}
                        disabled={isTerminalTaskStatus(task.status)}
                        className={cn(
                          "mr-1 rounded p-1 transition-colors",
                          isTerminalTaskStatus(task.status)
                            ? "cursor-not-allowed text-surface-200"
                            : "text-surface-300 hover:text-emerald-600 hover:bg-emerald-50",
                        )}
                        title="Завершить задачу"
                      >
                        <Check className="h-4 w-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          handleDelete(task.id);
                        }}
                        disabled={deletingId === task.id}
                        className="rounded p-1 text-surface-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                        title="Удалить задачу"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                {tasks.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-surface-400">
                      Задачи не найдены
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Timeline View */}
      {view === "timeline" && (
        <div className="space-y-3">
          <TimelineHoursBoard
            tasks={tasks}
            assignees={assignees}
            visibleAssigneeIds={timelineStaffIds === null ? undefined : timelineStaffIds}
            groupBy="assignee"
            dateField={timelineDateField}
            selectedDate={timelineSelectedDate}
            hourStart={timelineHourStart}
            hourEndExclusive={timelineHourEndExclusive}
            priorityColor={priorityColor}
            priorityLabel={priorityLabel}
            statusLabel={statusLabel}
            onTaskMove={handleTimelineMove}
            onQuickComplete={handleQuickComplete}
            onSlotClick={handleSlotClick}
          />
        </div>
      )}

      {view === "month" && (
        <TasksMonthCalendar
          tasks={tasksForCalendar}
          assignees={assignees}
          monthYm={timelineSelectedDate.slice(0, 7)}
          dateField={timelineDateField}
          hourStart={timelineHourStart}
          hourEndExclusive={timelineHourEndExclusive}
          cellMode={monthCellMode}
          onCellModeChange={setMonthCellMode}
          selectedDay={timelineSelectedDate}
          onSelectDay={setCalendarDayKey}
          onDayCellClick={goToTimelineForDay}
          priorityColor={priorityColor}
        />
      )}

      {/* FAB for mobile */}
      <button
        onClick={() => setCreateOpen(true)}
        className="fixed bottom-20 right-4 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary-600 text-white shadow-lg hover:bg-primary-700 active:bg-primary-800 transition-colors lg:hidden"
      >
        <Plus className="h-6 w-6" />
      </button>

      {/* Create Task Modal */}
      <CreateTaskModal
        open={createOpen}
        onClose={() => { setCreateOpen(false); setCreatePrefill(undefined); }}
        onCreated={handleCreated}
        initialValues={createPrefill}
      />
    </div>
  );
}

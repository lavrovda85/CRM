"use client";

/**
 * Archived / closed tasks: search, pagination, calendar window (day/week/month), multi-status.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  endOfDay,
  endOfMonth,
  endOfWeek,
  startOfDay,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { ApiError, fetchTasks, type UserListItem } from "@/lib/api";
import { cn, formatEnumLabel } from "@/lib/utils";
import type { TaskResponse } from "@/types";

const HISTORY_STATUSES: { id: string; label: string }[] = [
  { id: "closed", label: "Закрыта" },
  { id: "completed", label: "Завершена" },
  { id: "done", label: "Выполнено" },
];

const statusLabel: Record<string, string> = {
  new: "Новая",
  dispatched: "Назначена",
  in_progress: "В работе",
  testing: "Согласование",
  photo_report: "Согласование",
  act_signing: "Подписание акта",
  done: "Выполнено",
  completed: "Завершена",
  closed: "Закрыта",
};

const priorityLabel: Record<string, string> = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
  critical: "Критический",
};

export type HistoryCalMode = "day" | "week" | "month";

function toIsoUtc(d: Date): string {
  return d.toISOString();
}

function parseYmd(s: string): Date {
  const [y, m, d] = s.split("-").map((x) => Number(x));
  return new Date(y, (m || 1) - 1, d || 1, 12, 0, 0, 0);
}

export interface TasksHistoryViewProps {
  assignees: UserListItem[];
}

export function TasksHistoryView({ assignees }: TasksHistoryViewProps) {
  const [calMode, setCalMode] = useState<HistoryCalMode>("month");
  const [anchorYmd, setAnchorYmd] = useState(() => {
    const n = new Date();
    return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}-${String(n.getDate()).padStart(2, "0")}`;
  });
  const [selectedStatuses, setSelectedStatuses] = useState<Set<string>>(
    () => new Set(["closed", "completed"]),
  );
  const [search, setSearch] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [priority, setPriority] = useState("");

  const [offset, setOffset] = useState(0);
  const limit = 25;
  const [items, setItems] = useState<TaskResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQ(search.trim()), 350);
    return () => window.clearTimeout(t);
  }, [search]);

  const { updatedAfter, updatedBefore } = useMemo(() => {
    const anchor = parseYmd(anchorYmd);
    if (calMode === "day") {
      const a = startOfDay(anchor);
      const b = endOfDay(anchor);
      return { updatedAfter: toIsoUtc(a), updatedBefore: toIsoUtc(b) };
    }
    if (calMode === "week") {
      const a = startOfWeek(anchor, { weekStartsOn: 1 });
      const b = endOfWeek(anchor, { weekStartsOn: 1 });
      return { updatedAfter: toIsoUtc(startOfDay(a)), updatedBefore: toIsoUtc(endOfDay(b)) };
    }
    const a = startOfMonth(anchor);
    const b = endOfMonth(anchor);
    return { updatedAfter: toIsoUtc(startOfDay(a)), updatedBefore: toIsoUtc(endOfDay(b)) };
  }, [anchorYmd, calMode]);

  const statusInCsv = useMemo(() => {
    const xs = [...selectedStatuses];
    return xs.length ? xs.join(",") : "";
  }, [selectedStatuses]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, unknown> = {
        limit,
        offset,
        order: "updated_desc",
        updated_after: updatedAfter,
        updated_before: updatedBefore,
      };
      if (statusInCsv) params.status_in = statusInCsv;
      if (debouncedQ) params.q = debouncedQ;
      if (assignedTo) params.assigned_to = assignedTo;
      if (priority) params.priority = priority;
      const res = await fetchTasks(params);
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка загрузки";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [
    offset,
    limit,
    updatedAfter,
    updatedBefore,
    statusInCsv,
    debouncedQ,
    assignedTo,
    priority,
  ]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setOffset(0);
  }, [calMode, anchorYmd, statusInCsv, debouncedQ, assignedTo, priority]);

  function toggleStatus(id: string) {
    setSelectedStatuses((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      if (next.size === 0) next.add(id);
      return next;
    });
  }

  const page = Math.floor(offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="card space-y-4 p-3 sm:p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
        <div className="flex flex-wrap gap-2">
          <span className="w-full text-xs font-semibold text-surface-600 sm:w-auto">Период</span>
          {(["day", "week", "month"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setCalMode(m)}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                calMode === m
                  ? "border-primary-500 bg-primary-50 text-primary-800"
                  : "border-surface-200 bg-white text-surface-600 hover:bg-surface-50",
              )}
            >
              {m === "day" ? "День" : m === "week" ? "Неделя" : "Месяц"}
            </button>
          ))}
        </div>
        <label className="flex flex-col gap-1 text-xs font-medium text-surface-600">
          Дата
          <input
            type="date"
            className="input max-w-[200px]"
            value={anchorYmd}
            onChange={(e) => setAnchorYmd(e.target.value)}
          />
        </label>
        <label className="relative flex min-w-[min(100%,240px)] flex-1 basis-[220px] flex-col gap-1">
          <span className="text-xs font-medium text-surface-600">Поиск</span>
          <Search className="pointer-events-none absolute bottom-2.5 left-2.5 h-4 w-4 text-surface-400" />
          <input
            type="search"
            className="input w-full pl-9"
            placeholder="Название, описание…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-surface-600">
          Исполнитель
          <select
            className="input max-w-[220px]"
            value={assignedTo}
            onChange={(e) => setAssignedTo(e.target.value)}
          >
            <option value="">Все</option>
            {assignees.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-surface-600">
          Приоритет
          <select
            className="input max-w-[160px]"
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
          >
            <option value="">Все</option>
            <option value="low">Низкий</option>
            <option value="medium">Средний</option>
            <option value="high">Высокий</option>
            <option value="critical">Критический</option>
          </select>
        </label>
      </div>

      <div>
        <div className="mb-2 text-xs font-semibold text-surface-600">Статусы (несколько)</div>
        <div className="flex flex-wrap gap-2">
          {HISTORY_STATUSES.map((s) => (
            <label
              key={s.id}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm",
                selectedStatuses.has(s.id)
                  ? "border-primary-400 bg-primary-50 text-primary-900"
                  : "border-surface-200 bg-white text-surface-600",
              )}
            >
              <input
                type="checkbox"
                className="rounded border-surface-300"
                checked={selectedStatuses.has(s.id)}
                onChange={() => toggleStatus(s.id)}
              />
              {s.label}
            </label>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-surface-100">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-surface-100 bg-surface-50 text-left text-surface-600">
              <th className="px-3 py-2 font-medium">Название</th>
              <th className="px-3 py-2 font-medium">Статус</th>
              <th className="px-3 py-2 font-medium">Приоритет</th>
              <th className="hidden px-3 py-2 font-medium md:table-cell">Исполнитель</th>
              <th className="hidden px-3 py-2 font-medium lg:table-cell">Обновлено</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-50">
            {loading && (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-surface-400">
                  Загрузка…
                </td>
              </tr>
            )}
            {!loading &&
              items.map((task) => (
                <tr key={task.id} className="hover:bg-surface-50/80">
                  <td className="px-3 py-2">
                    <Link href={`/tasks/${task.id}`} className="font-medium text-primary-700 hover:underline">
                      {task.title}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-surface-600">
                    {formatEnumLabel(task.status, statusLabel)}
                  </td>
                  <td className="px-3 py-2">{formatEnumLabel(task.priority, priorityLabel)}</td>
                  <td className="hidden px-3 py-2 md:table-cell">
                    {task.assignee?.full_name ?? "—"}
                  </td>
                  <td className="hidden px-3 py-2 text-surface-500 lg:table-cell">
                    {task.updated_at
                      ? new Date(task.updated_at).toLocaleString("ru-RU", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "—"}
                  </td>
                </tr>
              ))}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center text-surface-400">
                  Нет записей за выбранный период и фильтры
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {total > limit && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-surface-100 pt-3">
          <span className="text-xs text-surface-500">
            Всего: {total} · стр. {page} / {pageCount}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-ghost btn-sm inline-flex items-center gap-1"
              disabled={offset <= 0 || loading}
              onClick={() => setOffset((o) => Math.max(0, o - limit))}
            >
              <ChevronLeft className="h-4 w-4" /> Назад
            </button>
            <button
              type="button"
              className="btn-ghost btn-sm inline-flex items-center gap-1"
              disabled={offset + limit >= total || loading}
              onClick={() => setOffset((o) => o + limit)}
            >
              Вперёд <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

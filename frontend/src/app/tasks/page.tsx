"use client";

import { useEffect, useState, useCallback } from "react";
import {
  LayoutGrid,
  List,
  Filter,
  Plus,
  Calendar,
  User,
  ChevronDown,
  X,
} from "lucide-react";
import Link from "next/link";
import { fetchTasks } from "@/lib/api";
import type { TaskResponse } from "@/types";

const KANBAN_COLUMNS = [
  { key: "new", label: "New", color: "bg-surface-300" },
  { key: "dispatched", label: "Dispatched", color: "bg-sky-400" },
  { key: "in_progress", label: "In Progress", color: "bg-blue-500" },
  { key: "testing", label: "Testing", color: "bg-amber-400" },
  { key: "photo_report", label: "Photo Report", color: "bg-violet-500" },
  { key: "act_signing", label: "Act Signing", color: "bg-orange-400" },
  { key: "done", label: "Done", color: "bg-green-500" },
] as const;

const priorityColor: Record<string, string> = {
  low: "bg-green-50 text-green-700",
  medium: "bg-yellow-50 text-yellow-700",
  high: "bg-orange-50 text-orange-700",
  critical: "bg-red-50 text-red-700",
};

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function TasksPage() {
  const [view, setView] = useState<"kanban" | "list">("kanban");
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchTasks({ ...filters, limit: 200 });
      setTasks(res.items);
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const grouped = KANBAN_COLUMNS.map((col) => ({
    ...col,
    tasks: tasks.filter((t) => t.status === col.key),
  }));

  function setFilter(key: string, value: string) {
    setFilters((prev) => {
      const next = { ...prev };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Tasks</h1>
        </div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[100rem] space-y-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFiltersOpen((o) => !o)}
            className={`btn-ghost gap-1.5 ${filtersOpen ? "bg-surface-100" : ""}`}
          >
            <Filter className="h-4 w-4" /> Filters
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${filtersOpen ? "rotate-180" : ""}`} />
          </button>
          <div className="flex rounded-lg border border-surface-200 bg-white p-0.5">
            <button
              onClick={() => setView("kanban")}
              className={`rounded-md px-2.5 py-1.5 text-sm transition-colors ${
                view === "kanban" ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900"
              }`}
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setView("list")}
              className={`rounded-md px-2.5 py-1.5 text-sm transition-colors ${
                view === "list" ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900"
              }`}
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Filters Bar */}
      {filtersOpen && (
        <div className="card flex flex-wrap items-center gap-3 p-3">
          <select
            className="input max-w-[160px]"
            value={filters.status ?? ""}
            onChange={(e) => setFilter("status", e.target.value)}
          >
            <option value="">All statuses</option>
            {KANBAN_COLUMNS.map((c) => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </select>
          <select
            className="input max-w-[160px]"
            value={filters.priority ?? ""}
            onChange={(e) => setFilter("priority", e.target.value)}
          >
            <option value="">All priorities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
          {Object.keys(filters).length > 0 && (
            <button onClick={() => setFilters({})} className="btn-ghost btn-sm text-red-600 gap-1">
              <X className="h-3.5 w-3.5" /> Clear
            </button>
          )}
        </div>
      )}

      {/* Kanban View */}
      {view === "kanban" && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {grouped.map((col) => (
            <div key={col.key} className="flex w-64 shrink-0 flex-col lg:w-auto lg:flex-1">
              <div className="mb-3 flex items-center gap-2">
                <div className={`h-2.5 w-2.5 rounded-full ${col.color}`} />
                <h3 className="text-sm font-semibold text-surface-700">{col.label}</h3>
                <span className="badge bg-surface-100 text-surface-500">{col.tasks.length}</span>
              </div>
              <div className="flex-1 space-y-3 rounded-xl bg-surface-50 p-2 min-h-[200px]">
                {col.tasks.map((task) => (
                  <Link
                    key={task.id}
                    href={`/tasks/${task.id}`}
                    className="card block p-3 hover:border-primary-200 transition-colors"
                  >
                    <p className="text-sm font-medium leading-snug">{task.title}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <span className={`badge text-[10px] ${priorityColor[task.priority] ?? ""}`}>
                        {task.priority}
                      </span>
                      {task.due_date && (
                        <span className="flex items-center gap-0.5 text-[10px] text-surface-400">
                          <Calendar className="h-3 w-3" />
                          {new Date(task.due_date).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}
                        </span>
                      )}
                    </div>
                    {task.assignee && (
                      <div className="mt-2 flex items-center gap-1.5">
                        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary-100 text-[10px] font-medium text-primary-700">
                          {task.assignee.full_name.charAt(0)}
                        </div>
                        <span className="text-xs text-surface-500 truncate">{task.assignee.full_name}</span>
                      </div>
                    )}
                  </Link>
                ))}
                {col.tasks.length === 0 && (
                  <p className="py-8 text-center text-xs text-surface-300">No tasks</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* List View */}
      {view === "list" && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-100 text-left text-surface-500">
                  <th className="px-4 py-3 font-medium">Title</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Priority</th>
                  <th className="hidden px-4 py-3 font-medium md:table-cell">Assignee</th>
                  <th className="hidden px-4 py-3 font-medium lg:table-cell">Due Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-50">
                {tasks.map((task) => (
                  <tr key={task.id} className="hover:bg-surface-50 transition-colors">
                    <td className="px-4 py-3">
                      <Link href={`/tasks/${task.id}`} className="font-medium text-surface-900 hover:text-primary-600">
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
                        {task.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${priorityColor[task.priority] ?? ""}`}>{task.priority}</span>
                    </td>
                    <td className="hidden px-4 py-3 md:table-cell">
                      {task.assignee ? (
                        <div className="flex items-center gap-1.5">
                          <User className="h-3.5 w-3.5 text-surface-400" />
                          <span className="text-surface-600">{task.assignee.full_name}</span>
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
                  </tr>
                ))}
                {tasks.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-surface-400">
                      No tasks found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* FAB for mobile */}
      <Link
        href="/tasks?new=1"
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary-600 text-white shadow-lg hover:bg-primary-700 active:bg-primary-800 transition-colors lg:hidden"
      >
        <Plus className="h-6 w-6" />
      </Link>
    </div>
  );
}

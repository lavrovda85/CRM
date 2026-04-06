"use client";

import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  CheckCircle2,
  Briefcase,
  DollarSign,
  Plus,
  UserPlus,
  Timer,
  AlertTriangle,
  Clock,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";
import { fetchDashboard, fetchTasks } from "@/lib/api";
import { formatEnumLabel } from "@/lib/utils";
import type { DashboardStats, TaskResponse } from "@/types";

function StatCard({
  icon: Icon,
  label,
  value,
  accent,
  href,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  accent: string;
  href?: string;
}) {
  const inner = (
    <div className="flex items-center gap-3">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${accent}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <p className="text-sm text-surface-500 truncate">{label}</p>
        <p className="text-2xl font-bold tracking-tight">{value}</p>
      </div>
      {href && <ArrowRight className="ml-auto h-4 w-4 shrink-0 text-surface-300" />}
    </div>
  );
  if (href) {
    return (
      <Link href={href} className="card block p-5 transition-shadow hover:shadow-md">
        {inner}
      </Link>
    );
  }
  return <div className="card p-5">{inner}</div>;
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentTasks, setRecentTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [dashData, tasksData] = await Promise.all([
          fetchDashboard(),
          fetchTasks({ limit: 5 }),
        ]);
        setStats(dashData);
        setRecentTasks(tasksData.items);
        setApiError(null);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Не удалось загрузить данные";
        setApiError(msg);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const completedToday = stats?.completed_today ?? 0;
  const activeTasks = stats?.active_tasks ?? 0;

  const statusColor: Record<string, string> = {
    new: "bg-surface-100 text-surface-600",
    dispatched: "bg-sky-50 text-sky-700",
    in_progress: "bg-blue-50 text-blue-700",
    testing: "bg-amber-50 text-amber-700",
    photo_report: "bg-violet-50 text-violet-700",
    act_signing: "bg-orange-50 text-orange-700",
    done: "bg-green-50 text-green-700",
    completed: "bg-green-50 text-green-700",
  };

  const priorityColor: Record<string, string> = {
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
  };

  const priorityLabel: Record<string, string> = {
    low: "Низкий",
    medium: "Средний",
    high: "Высокий",
    critical: "Критический",
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl space-y-6 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Панель управления</h1>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 lg:p-6">
      <h1 className="text-2xl font-bold">Панель управления</h1>

      {apiError && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
          <span className="font-medium">Ошибка API:</span> {apiError}
        </div>
      )}

      {/* Stats Row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon={LayoutDashboard}
          label="Активные задачи"
          value={activeTasks}
          accent="bg-blue-100 text-blue-600"
          href="/tasks?view=kanban"
        />
        <StatCard
          icon={CheckCircle2}
          label="Завершено сегодня"
          value={completedToday}
          accent="bg-green-100 text-green-600"
          href="/tasks?view=kanban&status=done"
        />
        <StatCard
          icon={Briefcase}
          label="Активные тендеры"
          value={stats?.active_tenders ?? 0}
          accent="bg-amber-100 text-amber-600"
        />
        <StatCard
          icon={DollarSign}
          label="Выручка"
          value={`₽${Number(stats?.deals_amount ?? 0).toLocaleString("ru-RU")}`}
          accent="bg-primary-100 text-primary-600"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent Tasks */}
        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between border-b border-surface-100 p-4">
            <h2 className="font-semibold">Последние задачи</h2>
            <Link href="/tasks" className="text-sm text-primary-600 hover:underline flex items-center gap-1">
              Все задачи <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="divide-y divide-surface-50">
            {recentTasks.length === 0 && (
              <p className="p-6 text-center text-sm text-surface-400">Задач пока нет</p>
            )}
            {recentTasks.map((task) => (
              <Link
                key={task.id}
                href={`/tasks/${task.id}`}
                className="flex items-center gap-3 p-4 hover:bg-surface-50 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{task.title}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <span className={`badge ${statusColor[task.status] ?? "bg-surface-100 text-surface-600"}`}>
                      {formatEnumLabel(task.status, statusLabel)}
                    </span>
                    <span className={`badge ${priorityColor[task.priority] ?? ""}`}>
                      {formatEnumLabel(task.priority, priorityLabel)}
                    </span>
                  </div>
                </div>
                {task.due_date && (
                  <span className="flex shrink-0 items-center gap-1 text-xs text-surface-400">
                    <Clock className="h-3.5 w-3.5" />
                    {new Date(task.due_date).toLocaleDateString("ru-RU")}
                  </span>
                )}
              </Link>
            ))}
          </div>
        </div>

        {/* Quick Actions + Alerts */}
        <div className="space-y-6">
          <div className="card p-4">
            <h2 className="mb-3 font-semibold">Быстрые действия</h2>
            <div className="space-y-2">
              <Link href="/tasks?new=1" className="btn-primary w-full justify-start gap-2">
                <Plus className="h-4 w-4" /> Новая задача
              </Link>
              <Link href="/clients?new=1" className="btn-secondary w-full justify-start gap-2">
                <UserPlus className="h-4 w-4" /> Новый клиент
              </Link>
              <Link href="/time" className="btn-secondary w-full justify-start gap-2">
                <Timer className="h-4 w-4" /> Запустить таймер
              </Link>
            </div>
          </div>

          <div className="card p-4">
            <h2 className="mb-3 font-semibold flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Уведомления
            </h2>
            <div className="space-y-2 text-sm">
              {(stats?.overdue_tasks ?? 0) > 0 && (
                <Link
                  href="/tasks?view=kanban&overdue=1"
                  className="flex items-center justify-between rounded-lg bg-red-50 p-3 text-red-700 hover:bg-red-100 transition-colors"
                >
                  <span>Просроченные задачи</span>
                  <span className="flex items-center gap-1.5 font-bold">
                    {stats!.overdue_tasks}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </Link>
              )}
              {(stats?.low_stock_items ?? 0) > 0 && (
                <div className="flex items-center justify-between rounded-lg bg-amber-50 p-3 text-amber-700">
                  <span>Мало на складе</span>
                  <span className="font-bold">{stats!.low_stock_items}</span>
                </div>
              )}
              {(stats?.overdue_tasks ?? 0) === 0 && (stats?.low_stock_items ?? 0) === 0 && (
                <p className="text-surface-400">Нет уведомлений</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

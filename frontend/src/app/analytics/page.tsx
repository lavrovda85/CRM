"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  TrendingUp,
  Award,
  Package,
  Calendar,
  Users,
  Target,
  DollarSign,
} from "lucide-react";
import { fetchDashboard, fetchTenderAnalytics, fetchWarehouseAnalytics } from "@/lib/api";
import type { DashboardStats, TenderAnalytics, WarehouseAnalytics } from "@/types";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

type Period = "week" | "month" | "quarter" | "year";

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<Period>("month");
  const [dashboard, setDashboard] = useState<DashboardStats | null>(null);
  const [tenderStats, setTenderStats] = useState<TenderAnalytics | null>(null);
  const [warehouseStats, setWarehouseStats] = useState<WarehouseAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [d, t, w] = await Promise.all([
          fetchDashboard(),
          fetchTenderAnalytics(),
          fetchWarehouseAnalytics(),
        ]);
        setDashboard(d);
        setTenderStats(t);
        setWarehouseStats(w);
      } catch {
        /* empty state */
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [period]);

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl space-y-6 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Аналитика</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-64" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 lg:p-6">
      {/* Header + Period Selector */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Аналитика</h1>
        <div className="flex items-center gap-1 rounded-lg border border-surface-200 bg-white p-1">
          {(["week", "month", "quarter", "year"] as Period[]).map((p) => {
            const periodLabels: Record<Period, string> = {
              week: "Неделя",
              month: "Месяц",
              quarter: "Квартал",
              year: "Год",
            };
            return (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  period === p ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900"
                }`}
              >
                {periodLabels[p]}
              </button>
            );
          })}
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-100 text-primary-600">
              <DollarSign className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-surface-500">Выручка</p>
              <p className="text-xl font-bold">₽{Number(dashboard?.deals_amount ?? 0).toLocaleString("ru-RU")}</p>
            </div>
          </div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-green-600">
              <Target className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-surface-500">Процент побед (тендеры)</p>
              <p className="text-xl font-bold">{tenderStats?.win_rate ?? 0}%</p>
            </div>
          </div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
              <Package className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-surface-500">Стоимость склада</p>
              <p className="text-xl font-bold">₽{Number(warehouseStats?.total_value ?? 0).toLocaleString("ru-RU")}</p>
            </div>
          </div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-surface-500">Всего задач</p>
              <p className="text-xl font-bold">{dashboard?.total_tasks ?? 0}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Revenue Chart Placeholder */}
      <div className="card p-6">
        <h2 className="mb-4 font-semibold flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-primary-500" /> Выручка за период
        </h2>
        <div className="flex h-48 items-center justify-center rounded-lg border-2 border-dashed border-surface-200 text-surface-400">
          <div className="text-center">
            <BarChart3 className="mx-auto h-10 w-10 mb-2" />
            <p className="text-sm">Здесь будет отображён график выручки</p>
            <p className="text-xs mt-1">Интеграция с библиотекой графиков в разработке</p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Tender Analytics */}
        <div className="card">
          <div className="border-b border-surface-100 p-4">
            <h2 className="font-semibold flex items-center gap-2">
              <Award className="h-4 w-4 text-primary-500" /> Сводка по тендерам
            </h2>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-surface-50 p-3 text-center">
                <p className="text-2xl font-bold">{tenderStats?.total_tenders ?? 0}</p>
                <p className="text-xs text-surface-500">Всего</p>
              </div>
              <div className="rounded-lg bg-green-50 p-3 text-center">
                <p className="text-2xl font-bold text-green-700">{tenderStats?.win_rate ?? 0}%</p>
                <p className="text-xs text-green-600">Процент побед</p>
              </div>
            </div>
            {tenderStats && Object.keys(tenderStats.tenders_by_status).length > 0 && (
              <div className="mt-4 space-y-2">
                {Object.entries(tenderStats.tenders_by_status).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between text-sm">
                    <span className="badge bg-surface-100 text-surface-600 capitalize">{status}</span>
                    <span className="font-medium">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Warehouse Turnover */}
        <div className="card">
          <div className="border-b border-surface-100 p-4">
            <h2 className="font-semibold flex items-center gap-2">
              <Package className="h-4 w-4 text-primary-500" /> Оборот склада
            </h2>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-surface-50 p-3 text-center">
                <p className="text-2xl font-bold">{warehouseStats?.total_items ?? 0}</p>
                <p className="text-xs text-surface-500">Позиции</p>
              </div>
              <div className={`rounded-lg p-3 text-center ${
                (warehouseStats?.low_stock_items.length ?? 0) > 0 ? "bg-red-50" : "bg-green-50"
              }`}>
                <p className={`text-2xl font-bold ${
                  (warehouseStats?.low_stock_items.length ?? 0) > 0 ? "text-red-700" : "text-green-700"
                }`}>
                  {warehouseStats?.low_stock_items.length ?? 0}
                </p>
                <p className="text-xs text-surface-500">Мало на складе</p>
              </div>
            </div>
            {warehouseStats && Object.keys(warehouseStats.movements_summary).length > 0 && (
              <div className="mt-4 space-y-2">
                {Object.entries(warehouseStats.movements_summary).map(([type, data]) => (
                  <div key={type} className="flex items-center justify-between text-sm">
                    <span className="badge bg-surface-100 text-surface-600 capitalize">{type.replace(/_/g, " ")}</span>
                    <span className="text-surface-600">{data.count} опер. / {data.total_quantity} ед.</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Employee Performance Placeholder */}
      <div className="card">
        <div className="border-b border-surface-100 p-4">
          <h2 className="font-semibold flex items-center gap-2">
            <Users className="h-4 w-4 text-primary-500" /> Эффективность сотрудников
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-100 text-left text-surface-500">
                <th className="px-4 py-3 font-medium">Сотрудник</th>
                <th className="px-4 py-3 font-medium text-right">Завершено задач</th>
                <th className="px-4 py-3 font-medium text-right">В работе</th>
                <th className="hidden px-4 py-3 font-medium text-right md:table-cell">Ср. часы</th>
                <th className="hidden px-4 py-3 font-medium text-right md:table-cell">Залогировано</th>
                <th className="hidden px-4 py-3 font-medium text-right lg:table-cell">Вовремя</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-surface-400">
                  Данные по эффективности сотрудников будут загружены
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

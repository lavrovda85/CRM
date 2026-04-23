"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Wrench,
  Filter,
  BarChart3,
  ChevronDown,
  X,
  MapPin,
  User,
  Calendar,
  DollarSign,
} from "lucide-react";
import { fetchEquipment } from "@/lib/api";
import type { EquipmentResponse, EquipmentStatus } from "@/types";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

const statusConfig: Record<EquipmentStatus, { label: string; classes: string }> = {
  active: { label: "Активно", classes: "bg-green-50 text-green-700" },
  maintenance: { label: "На обслуживании", classes: "bg-amber-50 text-amber-700" },
  written_off: { label: "Списано", classes: "bg-surface-100 text-surface-500" },
  lost: { label: "Утеряно", classes: "bg-red-50 text-red-700" },
};

const categoryLabels: Record<string, string> = {
  power_tool: "Электроинструмент",
  measuring: "Измерительное",
  hand_tool: "Ручной инструмент",
  safety: "Безопасность",
  vehicle: "Транспорт",
  crew: "Бригада / подряд (почасовая)",
};

export default function EquipmentPage() {
  const [equipment, setEquipment] = useState<EquipmentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchEquipment({ limit: 100 });
      setEquipment(res.items);
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = equipment.filter((e) => {
    if (statusFilter && e.status !== statusFilter) return false;
    if (categoryFilter && e.category !== categoryFilter) return false;
    return true;
  });

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Оборудование</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Оборудование</h1>
        <button
          onClick={() => setFiltersOpen((o) => !o)}
          className={`btn-ghost gap-1.5 ${filtersOpen ? "bg-surface-100" : ""}`}
        >
          <Filter className="h-4 w-4" /> Фильтры
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${filtersOpen ? "rotate-180" : ""}`} />
        </button>
      </div>

      {/* Filters */}
      {filtersOpen && (
        <div className="card flex flex-wrap items-center gap-3 p-3">
          <select
            className="input max-w-[160px]"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">Все статусы</option>
            {Object.entries(statusConfig).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
          <select
            className="input max-w-[160px]"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="">Все категории</option>
            {Object.entries(categoryLabels).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          {(statusFilter || categoryFilter) && (
            <button
              onClick={() => { setStatusFilter(""); setCategoryFilter(""); }}
              className="btn-ghost btn-sm text-red-600 gap-1"
            >
              <X className="h-3.5 w-3.5" /> Сбросить
            </button>
          )}
        </div>
      )}

      {/* Depreciation Chart Placeholder */}
      <div className="card p-6 text-center">
        <div className="flex items-center justify-center gap-2 text-surface-400">
          <BarChart3 className="h-8 w-8" />
          <span className="text-sm">Здесь будет отображён график амортизации</span>
        </div>
      </div>

      {/* Equipment Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((eq) => {
          const st = statusConfig[eq.status] ?? { label: eq.status, classes: "bg-surface-100 text-surface-600" };
          const depreciationPct = eq.purchase_price > 0
            ? Math.round((Number(eq.current_value) / Number(eq.purchase_price)) * 100)
            : 0;

          return (
            <div key={eq.id} className="card p-4 hover:border-primary-200 transition-colors">
              <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold truncate">{eq.name}</h3>
                  <p className="mt-0.5 text-xs text-surface-400 font-mono">{eq.serial_number}</p>
                </div>
                <span className={`badge shrink-0 ${st.classes}`}>{st.label}</span>
              </div>

              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-surface-500">Категория</span>
                  <span className="badge bg-surface-100 text-surface-600">
                    {categoryLabels[eq.category] ?? eq.category}
                  </span>
                </div>

                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-1 text-surface-500">
                    <DollarSign className="h-3.5 w-3.5" /> Текущая стоимость
                  </span>
                  <span className="font-medium">₽{Number(eq.current_value).toLocaleString("ru-RU")}</span>
                </div>

                {eq.hourly_rate != null && Number(eq.hourly_rate) > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-surface-500">Ставка часа</span>
                    <span className="font-medium">₽{Number(eq.hourly_rate).toLocaleString("ru-RU")}</span>
                  </div>
                )}

                {/* Depreciation Bar */}
                <div>
                  <div className="flex items-center justify-between text-xs text-surface-400">
                    <span>Остаточная стоимость</span>
                    <span>{depreciationPct}%</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-100">
                    <div
                      className={`h-full rounded-full transition-all ${
                        depreciationPct > 50 ? "bg-green-500" : depreciationPct > 20 ? "bg-amber-500" : "bg-red-500"
                      }`}
                      style={{ width: `${depreciationPct}%` }}
                    />
                  </div>
                </div>

                {eq.assigned_to && (
                  <div className="flex items-center gap-1 text-xs text-surface-500">
                    <User className="h-3.5 w-3.5" /> Назначено
                  </div>
                )}
                {eq.location && (
                  <div className="flex items-center gap-1 text-xs text-surface-500">
                    <MapPin className="h-3.5 w-3.5" /> {eq.location}
                  </div>
                )}
                <div className="flex items-center gap-1 text-xs text-surface-400">
                  <Calendar className="h-3.5 w-3.5" />
                  Приобретено: {new Date(eq.purchase_date).toLocaleDateString("ru-RU")}
                </div>
              </div>
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="col-span-full py-12 text-center text-surface-400">
            Оборудование не найдено
          </div>
        )}
      </div>
    </div>
  );
}

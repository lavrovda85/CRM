"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  Clock3,
  Edit3,
  Wrench,
  Filter,
  BarChart3,
  ChevronDown,
  X,
  MapPin,
  User,
  Calendar,
  DollarSign,
  Plus,
  Save,
} from "lucide-react";
import { ApiError, createEquipment, fetchActiveCompany, fetchEquipment, fetchTasks, updateEquipment } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";
import { isTerminalTaskStatus } from "@/lib/timelineTaskIntervals";
import type { EquipmentResponse, EquipmentStatus, TaskResponse } from "@/types";

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
  const [fieldTasks, setFieldTasks] = useState<TaskResponse[]>([]);
  const [fieldBoardId, setFieldBoardId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formSerial, setFormSerial] = useState("");
  const [formCategory, setFormCategory] = useState("crew");
  const [formPurchasePrice, setFormPurchasePrice] = useState("0");
  const [formCurrentValue, setFormCurrentValue] = useState("0");
  const [formServiceLifeMonths, setFormServiceLifeMonths] = useState("60");
  const [formStatus, setFormStatus] = useState<EquipmentStatus>("active");
  const [formHourlyRate, setFormHourlyRate] = useState("");
  const [formPurchaseDate, setFormPurchaseDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [formLocation, setFormLocation] = useState("");
  const [formNotes, setFormNotes] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [res, company] = await Promise.all([
        fetchEquipment({ limit: 300 }),
        fetchActiveCompany(),
      ]);
      setEquipment(res.items);
      const boardId = company.field_work_board_id?.trim() || null;
      setFieldBoardId(boardId);
      if (boardId) {
        const tr = await fetchTasks({ board_id: boardId, limit: 500, status_not_in: "closed,completed" });
        setFieldTasks(tr.items);
      } else {
        setFieldTasks([]);
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Не удалось загрузить данные");
      setFieldTasks([]);
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

  const workerStatsByEquipmentId = useMemo(() => {
    const out: Record<string, { busyNow: boolean; monthHours: number; monthPayout: number }> = {};
    const now = Date.now();
    const monthStart = new Date();
    monthStart.setDate(1);
    monthStart.setHours(0, 0, 0, 0);
    const nextMonthStart = new Date(monthStart);
    nextMonthStart.setMonth(nextMonthStart.getMonth() + 1);
    for (const t of fieldTasks) {
      const workerIdRaw = t.custom_fields?.["worker_equipment_id"];
      const workerId = typeof workerIdRaw === "string" ? workerIdRaw : "";
      if (!workerId) continue;
      if (!out[workerId]) out[workerId] = { busyNow: false, monthHours: 0, monthPayout: 0 };
      const startedMs = t.started_at ? new Date(t.started_at).getTime() : NaN;
      const dueMs = t.due_date ? new Date(t.due_date).getTime() : NaN;
      if (Number.isFinite(startedMs) && Number.isFinite(dueMs)) {
        if (!isTerminalTaskStatus(t.status) && startedMs <= now && dueMs >= now) {
          out[workerId].busyNow = true;
        }
        const overlapStart = Math.max(startedMs, monthStart.getTime());
        const overlapEnd = Math.min(dueMs, nextMonthStart.getTime());
        if (overlapEnd > overlapStart) {
          out[workerId].monthHours += (overlapEnd - overlapStart) / (1000 * 60 * 60);
        }
      }
    }
    for (const eq of equipment) {
      const s = out[eq.id];
      if (!s) continue;
      const rate = Number(eq.hourly_rate ?? 0);
      s.monthPayout = rate > 0 ? s.monthHours * rate : 0;
    }
    return out;
  }, [fieldTasks, equipment]);

  function openCreateModal() {
    setEditingId(null);
    setFormName("");
    setFormSerial("");
    setFormCategory("crew");
    setFormPurchasePrice("0");
    setFormCurrentValue("0");
    setFormServiceLifeMonths("60");
    setFormStatus("active");
    setFormHourlyRate("");
    setFormPurchaseDate(new Date().toISOString().slice(0, 10));
    setFormLocation("");
    setFormNotes("");
    setSaveError(null);
    setFormOpen(true);
  }

  function openEditModal(eq: EquipmentResponse) {
    setEditingId(eq.id);
    setFormName(eq.name ?? "");
    setFormSerial(eq.serial_number ?? "");
    setFormCategory(eq.category ?? "crew");
    setFormPurchasePrice(String(eq.purchase_price ?? 0));
    setFormCurrentValue(String(eq.current_value ?? 0));
    setFormServiceLifeMonths(String(eq.service_life_months ?? 60));
    setFormStatus(eq.status);
    setFormHourlyRate(eq.hourly_rate != null ? String(eq.hourly_rate) : "");
    setFormPurchaseDate(eq.purchase_date ? String(eq.purchase_date).slice(0, 10) : new Date().toISOString().slice(0, 10));
    setFormLocation(eq.location ?? "");
    setFormNotes(eq.notes ?? "");
    setSaveError(null);
    setFormOpen(true);
  }

  async function handleSaveEquipment() {
    if (!formName.trim()) {
      setSaveError("Введите название оборудования");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const payload = {
        name: formName.trim(),
        serial_number: formSerial.trim() || `EQ-${Date.now()}`,
        category: formCategory.trim() || "crew",
        purchase_price: Number(formPurchasePrice || 0),
        current_value: Number(formCurrentValue || 0),
        service_life_months: Number(formServiceLifeMonths || 60),
        status: formStatus,
        hourly_rate: formHourlyRate.trim() ? Number(formHourlyRate) : null,
        purchase_date: formPurchaseDate ? new Date(`${formPurchaseDate}T00:00:00`).toISOString() : new Date().toISOString(),
        location: formLocation.trim() || null,
        notes: formNotes.trim() || null,
      };
      if (editingId) {
        await updateEquipment(editingId, payload);
      } else {
        await createEquipment(payload);
      }
      setFormOpen(false);
      await load();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось сохранить";
      setSaveError(msg);
    } finally {
      setSaving(false);
    }
  }

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
        <div className="flex items-center gap-2">
          <button onClick={openCreateModal} className="btn-primary gap-1.5">
            <Plus className="h-4 w-4" /> Добавить оборудование
          </button>
          <button
            onClick={() => setFiltersOpen((o) => !o)}
            className={`btn-ghost gap-1.5 ${filtersOpen ? "bg-surface-100" : ""}`}
          >
            <Filter className="h-4 w-4" /> Фильтры
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${filtersOpen ? "rotate-180" : ""}`} />
          </button>
        </div>
      </div>

      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{loadError}</div>
      )}

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
                {Number(eq.hourly_rate ?? 0) > 0 && (
                  <>
                    <div className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-1 text-surface-500">
                        <Clock3 className="h-3.5 w-3.5" /> Занятость сейчас
                      </span>
                      <span
                        className={`badge ${
                          workerStatsByEquipmentId[eq.id]?.busyNow
                            ? "bg-amber-50 text-amber-700"
                            : "bg-green-50 text-green-700"
                        }`}
                      >
                        {workerStatsByEquipmentId[eq.id]?.busyNow ? "Занят" : "Свободен"}
                      </span>
                    </div>
                    <div className="rounded-lg border border-surface-200 bg-surface-50 px-2.5 py-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-surface-500">Часы за текущий месяц</span>
                        <span className="font-semibold text-surface-800">
                          {(workerStatsByEquipmentId[eq.id]?.monthHours ?? 0).toFixed(1)} ч
                        </span>
                      </div>
                      <div className="mt-1 flex items-center justify-between">
                        <span className="text-surface-500">Расчет ЗП (месяц)</span>
                        <span className="font-semibold text-surface-900">
                          ₽{Math.round(workerStatsByEquipmentId[eq.id]?.monthPayout ?? 0).toLocaleString("ru-RU")}
                        </span>
                      </div>
                    </div>
                  </>
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
                <div className="pt-1">
                  <button type="button" onClick={() => openEditModal(eq)} className="btn-ghost btn-sm gap-1">
                    <Edit3 className="h-3.5 w-3.5" /> Редактировать
                  </button>
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

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingId ? "Редактировать оборудование" : "Новое оборудование"}
        className="sm:max-w-xl"
        footer={(
          <>
            <button type="button" className="btn-ghost" onClick={() => setFormOpen(false)} disabled={saving}>
              Отмена
            </button>
            <button type="button" className="btn-primary gap-1.5" onClick={() => void handleSaveEquipment()} disabled={saving}>
              <Save className="h-4 w-4" />
              {saving ? "Сохранение..." : "Сохранить"}
            </button>
          </>
        )}
      >
        <div className="space-y-3">
          {saveError && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{saveError}</div>}
          {!fieldBoardId && (
            <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
              Доска выездных работ не назначена в настройках компании — индикаторы занятости/часов будут пустыми.
            </div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">Название</label>
            <input className="input" value={formName} onChange={(e) => setFormName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Серийный номер</label>
              <input className="input" value={formSerial} onChange={(e) => setFormSerial(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Категория</label>
              <input className="input" value={formCategory} onChange={(e) => setFormCategory(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Ставка часа</label>
              <input className="input" type="number" min="0" step="0.01" value={formHourlyRate} onChange={(e) => setFormHourlyRate(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Статус</label>
              <select className="input" value={formStatus} onChange={(e) => setFormStatus(e.target.value as EquipmentStatus)}>
                {Object.entries(statusConfig).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Цена закупки</label>
              <input className="input" type="number" min="0" step="0.01" value={formPurchasePrice} onChange={(e) => setFormPurchasePrice(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Текущая стоимость</label>
              <input className="input" type="number" min="0" step="0.01" value={formCurrentValue} onChange={(e) => setFormCurrentValue(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Срок службы (мес.)</label>
              <input className="input" type="number" min="1" value={formServiceLifeMonths} onChange={(e) => setFormServiceLifeMonths(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Дата покупки</label>
              <input className="input" type="date" value={formPurchaseDate} onChange={(e) => setFormPurchaseDate(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Локация</label>
              <input className="input" value={formLocation} onChange={(e) => setFormLocation(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">Примечание</label>
            <textarea className="input min-h-[84px]" value={formNotes} onChange={(e) => setFormNotes(e.target.value)} />
          </div>
        </div>
      </Modal>
    </div>
  );
}

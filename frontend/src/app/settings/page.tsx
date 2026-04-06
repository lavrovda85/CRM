"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Settings,
  Plus,
  Pencil,
  Check,
  X,
  BookOpen,
  ChevronRight,
} from "lucide-react";
import {
  fetchReferences,
  fetchReference,
  createReferenceItem,
  updateReferenceItem,
  fetchAdminSettings,
  updateAdminSchedulerSettings,
  fetchUsers,
} from "@/lib/api";
import type { ReferenceResponse, ReferenceItemResponse } from "@/types";
import { useAuthStore } from "@/stores/auth";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function SettingsPage() {
  const authUser = useAuthStore((s) => s.user);
  const isAdmin = authUser?.role === "admin";
  const [references, setReferences] = useState<ReferenceResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeRef, setActiveRef] = useState<ReferenceResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [newItem, setNewItem] = useState({ code: "", name: "" });
  const [showAdd, setShowAdd] = useState(false);
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminSaving, setAdminSaving] = useState(false);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [adminOk, setAdminOk] = useState<string | null>(null);
  const [envPreview, setEnvPreview] = useState<Record<string, string>>({});
  const [staff, setStaff] = useState<Array<{ id: string; full_name: string }>>([]);
  const [scheduler, setScheduler] = useState({
    enabled: false,
    cron_minute: "0",
    cron_hour: "9",
    cron_day_of_month: "*",
    cron_month_of_year: "*",
    cron_day_of_week: "1-5",
    title: "Daily control task",
    description: "",
    priority: "medium",
    template_id: "",
    assigned_to: "",
    requested_by: "",
    board_id: "",
    client_id: "",
    due_in_hours: 24,
    observer_ids: [] as string[],
    co_assignee_ids: [] as string[],
    dedup_window_minutes: 180,
  });

  const loadRefs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchReferences({ limit: 50 });
      setReferences(res.items);
      if (res.items.length > 0 && !activeRef) {
        await loadRefDetail(res.items[0].code);
      }
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, []);

  async function loadRefDetail(code: string) {
    setDetailLoading(true);
    try {
      const ref = await fetchReference(code);
      setActiveRef(ref);
    } catch {
      /* silent */
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => { loadRefs(); }, [loadRefs]);
  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    void (async () => {
      setAdminLoading(true);
      setAdminError(null);
      try {
        const [settings, users] = await Promise.all([
          fetchAdminSettings(),
          fetchUsers({ limit: 200, offset: 0, is_active: true }),
        ]);
        if (cancelled) return;
        setEnvPreview(settings.env_preview || {});
        setScheduler({
          enabled: !!settings.scheduler.enabled,
          cron_minute: settings.scheduler.cron_minute || "0",
          cron_hour: settings.scheduler.cron_hour || "9",
          cron_day_of_month: settings.scheduler.cron_day_of_month || "*",
          cron_month_of_year: settings.scheduler.cron_month_of_year || "*",
          cron_day_of_week: settings.scheduler.cron_day_of_week || "1-5",
          title: settings.scheduler.title || "Daily control task",
          description: settings.scheduler.description || "",
          priority: (settings.scheduler.priority || "medium") as "low" | "medium" | "high" | "critical",
          template_id: settings.scheduler.template_id || "",
          assigned_to: settings.scheduler.assigned_to || "",
          requested_by: settings.scheduler.requested_by || "",
          board_id: settings.scheduler.board_id || "",
          client_id: settings.scheduler.client_id || "",
          due_in_hours: Number(settings.scheduler.due_in_hours || 24),
          observer_ids: settings.scheduler.observer_ids || [],
          co_assignee_ids: settings.scheduler.co_assignee_ids || [],
          dedup_window_minutes: Number(settings.scheduler.dedup_window_minutes || 180),
        });
        setStaff(users.items.map((u) => ({ id: String(u.id), full_name: u.full_name })));
      } catch (e) {
        if (!cancelled) setAdminError(e instanceof Error ? e.message : "Не удалось загрузить админ-настройки");
      } finally {
        if (!cancelled) setAdminLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  async function saveScheduler() {
    setAdminSaving(true);
    setAdminError(null);
    setAdminOk(null);
    try {
      await updateAdminSchedulerSettings({
        enabled: scheduler.enabled,
        cron_minute: scheduler.cron_minute,
        cron_hour: scheduler.cron_hour,
        cron_day_of_month: scheduler.cron_day_of_month,
        cron_month_of_year: scheduler.cron_month_of_year,
        cron_day_of_week: scheduler.cron_day_of_week,
        title: scheduler.title,
        description: scheduler.description || null,
        priority: scheduler.priority as "low" | "medium" | "high" | "critical",
        template_id: scheduler.template_id || null,
        assigned_to: scheduler.assigned_to || null,
        requested_by: scheduler.requested_by || null,
        board_id: scheduler.board_id || null,
        client_id: scheduler.client_id || null,
        due_in_hours: Number(scheduler.due_in_hours),
        observer_ids: scheduler.observer_ids,
        co_assignee_ids: scheduler.co_assignee_ids,
        dedup_window_minutes: Number(scheduler.dedup_window_minutes),
      });
      setAdminOk("Сохранено");
    } catch (e) {
      setAdminError(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setAdminSaving(false);
    }
  }

  async function handleAddItem() {
    if (!activeRef || !newItem.code || !newItem.name) return;
    try {
      await createReferenceItem(activeRef.code, newItem);
      setNewItem({ code: "", name: "" });
      setShowAdd(false);
      await loadRefDetail(activeRef.code);
    } catch {
      /* silent */
    }
  }

  async function handleUpdateItem(itemId: string) {
    if (!activeRef || !editName.trim()) return;
    try {
      await updateReferenceItem(activeRef.code, itemId, { name: editName });
      setEditingItem(null);
      await loadRefDetail(activeRef.code);
    } catch {
      /* silent */
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Настройки</h1>
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-64" />
          <Skeleton className="h-64 lg:col-span-2" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 lg:p-6">
      <div className="flex items-center gap-2">
        <Settings className="h-6 w-6 text-surface-500" />
        <h1 className="text-2xl font-bold">Настройки</h1>
        {isAdmin && (
          <Link href="/settings/admin" className="btn-ghost btn-sm ml-auto">
            Открыть админку
          </Link>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Reference Tabs */}
        <div className="card">
          <div className="border-b border-surface-100 p-4">
            <h2 className="font-semibold flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-primary-500" /> Справочники
            </h2>
          </div>
          <div className="divide-y divide-surface-50">
            {references.map((ref) => (
              <button
                key={ref.id}
                onClick={() => loadRefDetail(ref.code)}
                className={`flex w-full items-center justify-between p-3 text-left transition-colors ${
                  activeRef?.code === ref.code
                    ? "bg-primary-50 text-primary-700"
                    : "hover:bg-surface-50"
                }`}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{ref.name}</p>
                  <p className="text-xs text-surface-400 font-mono">{ref.code}</p>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-surface-300" />
              </button>
            ))}
            {references.length === 0 && (
              <p className="p-6 text-center text-sm text-surface-400">Нет справочников</p>
            )}
          </div>
        </div>

        {/* Reference Items */}
        <div className="card lg:col-span-2">
          {activeRef ? (
            <>
              <div className="flex items-center justify-between border-b border-surface-100 p-4">
                <div>
                  <h2 className="font-semibold">{activeRef.name}</h2>
                  {activeRef.description && (
                    <p className="mt-0.5 text-sm text-surface-500">{activeRef.description}</p>
                  )}
                </div>
                <button onClick={() => setShowAdd(true)} className="btn-primary btn-sm gap-1">
                  <Plus className="h-3.5 w-3.5" /> Добавить
                </button>
              </div>

              {showAdd && (
                <div className="border-b border-surface-100 bg-surface-50 p-4">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Код"
                      className="input max-w-[120px]"
                      value={newItem.code}
                      onChange={(e) => setNewItem({ ...newItem, code: e.target.value })}
                    />
                    <input
                      type="text"
                      placeholder="Название"
                      className="input flex-1"
                      value={newItem.name}
                      onChange={(e) => setNewItem({ ...newItem, name: e.target.value })}
                    />
                    <button onClick={handleAddItem} className="btn-primary btn-sm" disabled={!newItem.code || !newItem.name}>
                      <Check className="h-4 w-4" />
                    </button>
                    <button onClick={() => { setShowAdd(false); setNewItem({ code: "", name: "" }); }} className="btn-ghost btn-sm">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}

              {detailLoading ? (
                <div className="p-4 space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-10" />
                  ))}
                </div>
              ) : (
                <div className="divide-y divide-surface-50">
                  {activeRef.items
                    .sort((a, b) => a.order - b.order)
                    .map((item) => (
                      <div key={item.id} className="flex items-center justify-between p-3">
                        {editingItem === item.id ? (
                          <div className="flex flex-1 items-center gap-2">
                            <input
                              type="text"
                              className="input flex-1"
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              autoFocus
                              onKeyDown={(e) => e.key === "Enter" && handleUpdateItem(item.id)}
                            />
                            <button onClick={() => handleUpdateItem(item.id)} className="btn-primary btn-sm">
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button onClick={() => setEditingItem(null)} className="btn-ghost btn-sm">
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        ) : (
                          <>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium">{item.name}</span>
                                <span className="text-xs text-surface-400 font-mono">{item.code}</span>
                                {!item.is_active && (
                                  <span className="badge bg-surface-100 text-surface-400 text-[10px]">неактивен</span>
                                )}
                              </div>
                            </div>
                            <button
                              onClick={() => { setEditingItem(item.id); setEditName(item.name); }}
                              className="btn-ghost btn-sm"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    ))}
                  {activeRef.items.length === 0 && (
                    <p className="p-8 text-center text-sm text-surface-400">
                      Нет элементов в этом справочнике
                    </p>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center py-16 text-surface-400">
              <p className="text-sm">Выберите справочник для управления его элементами</p>
            </div>
          )}
        </div>
      </div>

      {isAdmin && (
        <div className="card p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Админка: системные настройки</h2>
            <button onClick={() => void saveScheduler()} className="btn-primary btn-sm" disabled={adminSaving || adminLoading}>
              {adminSaving ? "Сохранение..." : "Сохранить"}
            </button>
          </div>
          {adminError && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{adminError}</div>}
          {adminOk && <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{adminOk}</div>}
          {adminLoading ? (
            <Skeleton className="h-32" />
          ) : (
            <>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={scheduler.enabled} onChange={(e) => setScheduler((s) => ({ ...s, enabled: e.target.checked }))} />
                  Включить шедуллер
                </label>
                <input className="input" placeholder="Minute" value={scheduler.cron_minute} onChange={(e) => setScheduler((s) => ({ ...s, cron_minute: e.target.value }))} />
                <input className="input" placeholder="Hour" value={scheduler.cron_hour} onChange={(e) => setScheduler((s) => ({ ...s, cron_hour: e.target.value }))} />
                <input className="input" placeholder="Day of week" value={scheduler.cron_day_of_week} onChange={(e) => setScheduler((s) => ({ ...s, cron_day_of_week: e.target.value }))} />
                <input className="input" placeholder="Day of month" value={scheduler.cron_day_of_month} onChange={(e) => setScheduler((s) => ({ ...s, cron_day_of_month: e.target.value }))} />
                <input className="input" placeholder="Month of year" value={scheduler.cron_month_of_year} onChange={(e) => setScheduler((s) => ({ ...s, cron_month_of_year: e.target.value }))} />
                <select className="input" value={scheduler.priority} onChange={(e) => setScheduler((s) => ({ ...s, priority: e.target.value as "low" | "medium" | "high" | "critical" }))}>
                  <option value="low">Низкий</option>
                  <option value="medium">Средний</option>
                  <option value="high">Высокий</option>
                  <option value="critical">Критический</option>
                </select>
                <input className="input" type="number" min={0} max={744} value={scheduler.due_in_hours} onChange={(e) => setScheduler((s) => ({ ...s, due_in_hours: Number(e.target.value || 0) }))} placeholder="Due in hours" />
              </div>
              <input className="input w-full" placeholder="Заголовок задачи" value={scheduler.title} onChange={(e) => setScheduler((s) => ({ ...s, title: e.target.value }))} />
              <textarea className="input min-h-[84px] w-full" placeholder="Описание задачи" value={scheduler.description} onChange={(e) => setScheduler((s) => ({ ...s, description: e.target.value }))} />
              <div className="grid gap-3 md:grid-cols-2">
                <select className="input" value={scheduler.assigned_to} onChange={(e) => setScheduler((s) => ({ ...s, assigned_to: e.target.value }))}>
                  <option value="">Исполнитель (optional)</option>
                  {staff.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                </select>
                <select className="input" value={scheduler.requested_by} onChange={(e) => setScheduler((s) => ({ ...s, requested_by: e.target.value }))}>
                  <option value="">Постановщик (optional)</option>
                  {staff.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                </select>
              </div>
              <div>
                <div className="mb-1 text-xs font-semibold text-surface-500">ENV preview</div>
                <div className="grid gap-1 md:grid-cols-2">
                  {Object.entries(envPreview).map(([k, v]) => (
                    <div key={k} className="rounded bg-surface-50 px-2 py-1 text-xs">
                      <span className="font-mono text-surface-500">{k}</span>: <span>{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

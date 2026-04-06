"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Filter,
  Plus,
  Calendar,
  DollarSign,
  Globe,
  X,
  ChevronDown,
  Trash2,
  Loader2,
  GripVertical,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  DragDropContext,
  Droppable,
  Draggable,
  type DropResult,
} from "@hello-pangea/dnd";
import { ApiError, createClient, createTender, deleteTender, fetchClients, fetchTenders, transitionTender } from "@/lib/api";
import { tenderStatusLabel } from "@/lib/tenderPipeline";
import type { ClientResponse, TenderResponse, TenderStatus } from "@/types";

const COLUMNS: { key: TenderStatus; label: string; color: string }[] = [
  { key: "search", label: "Поиск", color: "bg-surface-400" },
  { key: "participation", label: "Участие", color: "bg-blue-500" },
  { key: "won", label: "Выигран", color: "bg-green-500" },
  { key: "execution", label: "Реализация", color: "bg-amber-500" },
  { key: "completed", label: "Завершён", color: "bg-emerald-600" },
  { key: "lost", label: "Проигран", color: "bg-red-500" },
];

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function TendersPage() {
  const router = useRouter();
  const [tenders, setTenders] = useState<TenderResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<Record<string, string>>({});

  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [clients, setClients] = useState<ClientResponse[]>([]);
  const [clientsBusy, setClientsBusy] = useState(false);
  const [clientsLoaded, setClientsLoaded] = useState(false);

  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletingTenderId, setDeletingTenderId] = useState<string | null>(null);
  const [boardError, setBoardError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [form, setForm] = useState({
    title: "",
    tender_link: "",
    customer_id: "" as string,
    new_customer_name: "",
    customer_type: "individual" as "individual" | "organization",
    guarantee_amount: "0",
    max_price: "0",
    min_price: "0",
    trade_start_at: "",
    trade_end_at: "",
    source: "",
    status: "search" as TenderStatus,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await fetchTenders({ ...filters, limit: 200 });
      setTenders(res.items);
    } catch (e) {
      setTenders([]);
      setLoadError(
        e instanceof ApiError
          ? `${e.message}${e.status ? ` (HTTP ${e.status})` : ""}`
          : e instanceof Error
            ? e.message
            : "Не удалось загрузить тендеры",
      );
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!createOpen) return;
    if (clientsLoaded) return;

    setClientsBusy(true);
    fetchClients({ limit: 200 })
      .then((res) => setClients(res.items))
      .catch(() => {})
      .finally(() => {
        setClientsBusy(false);
        setClientsLoaded(true);
      });
  }, [createOpen, clientsLoaded]);

  async function handleTenderDragEnd(result: DropResult) {
    const { destination, source, draggableId } = result;
    if (!destination || destination.droppableId === source.droppableId) return;
    const toStatus = destination.droppableId as TenderStatus;
    const tid = draggableId;
    const snapshot = [...tenders];
    setBoardError(null);
    setTenders((items) =>
      items.map((t) => (t.id === tid ? { ...t, status: toStatus } : t)),
    );
    try {
      await transitionTender(tid, toStatus);
    } catch (e) {
      setTenders(snapshot);
      setBoardError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось сменить этап тендера",
      );
    }
  }

  async function handleDeleteTender(tenderId: string) {
    if (deletingTenderId) return;
    if (!confirm("Удалить тендер?")) return;
    setDeleteError(null);
    setDeletingTenderId(tenderId);
    try {
      await deleteTender(tenderId);
      await load();
    } catch (e) {
      setDeleteError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка удаления тендера",
      );
    } finally {
      setDeletingTenderId(null);
    }
  }

  function setFilter(key: string, value: string) {
    setFilters((prev) => {
      const next = { ...prev };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  }

  const grouped = COLUMNS.map((col) => ({
    ...col,
    tenders: tenders.filter((t) => t.status === col.key),
  }));

  const getTradePriority = (tender: TenderResponse) => {
    if (!tender.trade_start_at) return null;
    const start = new Date(tender.trade_start_at).getTime();
    const diffHours = (start - Date.now()) / (1000 * 60 * 60);
    if (diffHours <= 2) return { tone: "danger", label: "Срочно: < 2ч" };
    if (diffHours <= 24) return { tone: "warning", label: "Скоро: < 24ч" };
    return null;
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-[100rem] space-y-4 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Тендеры</h1>
        <div className="flex gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-64 w-56 shrink-0 lg:flex-1" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[100rem] space-y-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Тендеры</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFiltersOpen((o) => !o)}
            className={`btn-ghost gap-1.5 ${filtersOpen ? "bg-surface-100" : ""}`}
          >
            <Filter className="h-4 w-4" /> Фильтры
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${filtersOpen ? "rotate-180" : ""}`} />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setCreateError(null);
              setCreateOpen(true);
            }}
            className="btn-primary gap-1.5"
          >
            <Plus className="h-4 w-4" /> Новый тендер
          </button>
        </div>
      </div>

      {/* Filters */}
      {filtersOpen && (
        <div className="card flex flex-wrap items-center gap-3 p-3">
          <select
            className="input max-w-[160px]"
            value={filters.status ?? ""}
            onChange={(e) => setFilter("status", e.target.value)}
          >
            <option value="">Все статусы</option>
            {COLUMNS.map((c) => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </select>
          {Object.keys(filters).length > 0 && (
            <button onClick={() => setFilters({})} className="btn-ghost btn-sm text-red-600 gap-1">
              <X className="h-3.5 w-3.5" /> Сбросить
            </button>
          )}
        </div>
      )}

      {/* Kanban */}
      <p className="text-xs text-surface-500">
        Перетащите карточку в другую колонку, чтобы перевести тендер на следующий этап пайплайна (допустимые переходы проверяются на сервере).
      </p>
      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
          <strong className="font-medium">Не удалось загрузить список.</strong> {loadError}{" "}
          <button type="button" className="underline text-primary-700" onClick={() => void load()}>
            Повторить
          </button>
        </div>
      )}
      {deleteError && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{deleteError}</div>
      )}
      {boardError && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">
          {boardError}
        </div>
      )}
      <DragDropContext onDragEnd={(r) => void handleTenderDragEnd(r)}>
        <div className="flex gap-4 overflow-x-auto pb-4">
          {grouped.map((col) => (
            <div key={col.key} className="flex w-60 shrink-0 flex-col lg:w-auto lg:flex-1">
              <div className="mb-3 flex items-center gap-2">
                <div className={`h-2.5 w-2.5 rounded-full ${col.color}`} />
                <h3 className="text-sm font-semibold text-surface-700">{col.label}</h3>
                <span className="badge bg-surface-100 text-surface-500">{col.tenders.length}</span>
              </div>
              <Droppable droppableId={col.key}>
                {(provided) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className="flex-1 space-y-3 rounded-xl bg-surface-50 p-2 min-h-[200px]"
                  >
                    {col.tenders.map((tender, index) => (
                      <Draggable key={tender.id} draggableId={tender.id} index={index}>
                        {(dragProvided) => (
                          <div
                            ref={dragProvided.innerRef}
                            {...dragProvided.draggableProps}
                            className={`card p-3 hover:border-primary-200 transition-colors ${
                              getTradePriority(tender)?.tone === "danger"
                                ? "border-red-200 bg-red-50/40"
                                : getTradePriority(tender)?.tone === "warning"
                                  ? "border-amber-200 bg-amber-50/40"
                                  : ""
                            }`}
                          >
                            <div className="flex items-start gap-2">
                              <button
                                type="button"
                                className="mt-0.5 shrink-0 cursor-grab text-surface-300 hover:text-surface-500 active:cursor-grabbing"
                                {...dragProvided.dragHandleProps}
                                title="Перетащить"
                                aria-label="Перетащить карточку"
                              >
                                <GripVertical className="h-4 w-4" />
                              </button>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-start justify-between gap-2">
                                  <button
                                    type="button"
                                    className="text-left text-sm font-medium leading-snug text-surface-900 hover:text-primary-600"
                                    onClick={() => router.push(`/tenders/${tender.id}`)}
                                  >
                                    {tender.title}
                                  </button>
                                  <div className="flex shrink-0 items-center gap-1">
                                    {getTradePriority(tender) && (
                                      <span
                                        className={`badge ${
                                          getTradePriority(tender)!.tone === "danger"
                                            ? "bg-red-50 text-red-700"
                                            : "bg-amber-50 text-amber-700"
                                        }`}
                                      >
                                        {getTradePriority(tender)!.label}
                                      </span>
                                    )}
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        handleDeleteTender(tender.id).catch(() => {});
                                      }}
                                      className="rounded p-1.5 text-surface-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                                      title="Удалить"
                                      disabled={deletingTenderId === tender.id}
                                    >
                                      {deletingTenderId === tender.id ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                      ) : (
                                        <Trash2 className="h-4 w-4" />
                                      )}
                                    </button>
                                  </div>
                                </div>
                                <p className="mt-1 text-[10px] uppercase tracking-wide text-surface-400">
                                  {tenderStatusLabel(tender.status)}
                                </p>
                                <div className="mt-2 space-y-1.5">
                                  {tender.customer_name && (
                                    <div className="flex items-center gap-1 text-xs text-surface-600">
                                      <Globe className="h-3 w-3 text-surface-400" />
                                      {tender.customer_name}
                                    </div>
                                  )}
                                  {tender.budget != null && (
                                    <div className="flex items-center gap-1 text-xs text-surface-600">
                                      <DollarSign className="h-3 w-3 text-surface-400" />
                                      Бюджет: ₽{Number(tender.budget).toLocaleString("ru-RU")}
                                    </div>
                                  )}
                                  {tender.deadline && (
                                    <div className="flex items-center gap-1 text-xs text-surface-600">
                                      <Calendar className="h-3 w-3 text-surface-400" />
                                      {new Date(tender.deadline).toLocaleDateString("ru-RU")}
                                    </div>
                                  )}
                                  {tender.source && (
                                    <div className="flex items-center gap-1 text-xs text-surface-400">
                                      <Globe className="h-3 w-3" />
                                      {tender.source}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                    {col.tenders.length === 0 && (
                      <p className="py-8 text-center text-xs text-surface-300">Нет тендеров</p>
                    )}
                  </div>
                )}
              </Droppable>
            </div>
          ))}
        </div>
      </DragDropContext>

      {/* Create Tender Sheet */}
      {createOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center"
          onClick={() => setCreateOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-t-2xl bg-white p-6 shadow-2xl sm:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">Новый тендер</h2>
              <button onClick={() => setCreateOpen(false)} className="btn-ghost p-1.5">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3">
              {createError && (
                <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">
                  {createError}
                </div>
              )}

              <div>
                <label className="mb-1 block text-sm font-medium text-surface-700">
                  Название тендера *
                </label>
                <input
                  className="input w-full"
                  value={form.title}
                  onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-surface-700">
                  Ссылка на тендер *
                </label>
                <input
                  className="input w-full"
                  value={form.tender_link}
                  onChange={(e) => setForm((p) => ({ ...p, tender_link: e.target.value }))}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label className="text-sm font-medium text-surface-700">Заказчик *</label>
                </div>
                {clientsBusy ? (
                  <p className="text-xs text-surface-500">Загрузка клиентов...</p>
                ) : clients.length > 0 ? (
                  <select
                    className="input w-full"
                    value={form.customer_id}
                    onChange={(e) => setForm((p) => ({ ...p, customer_id: e.target.value }))}
                  >
                    <option value="">Выберите клиента</option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                    <option value="__new__">Создать нового</option>
                  </select>
                ) : (
                  <p className="text-xs text-surface-500">Список клиентов пуст. Создайте нового.</p>
                )}

                {clients.length === 0 || form.customer_id === "__new__" ? (
                  <div className="space-y-2">
                    <input
                      className="input w-full"
                      placeholder="Имя заказчика"
                      value={form.new_customer_name}
                      onChange={(e) => setForm((p) => ({ ...p, new_customer_name: e.target.value }))}
                    />
                    <select
                      className="input w-full"
                      value={form.customer_type}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, customer_type: e.target.value as any }))
                      }
                    >
                      <option value="individual">Физ. лицо</option>
                      <option value="organization">Организация</option>
                    </select>
                  </div>
                ) : null}
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-1">
                  <label className="mb-1 block text-xs font-medium text-surface-700">Гарантия *</label>
                  <input
                    className="input w-full"
                    type="number"
                    step="0.01"
                    value={form.guarantee_amount}
                    onChange={(e) => setForm((p) => ({ ...p, guarantee_amount: e.target.value }))}
                  />
                </div>
                <div className="col-span-1">
                  <label className="mb-1 block text-xs font-medium text-surface-700">Макс цена *</label>
                  <input
                    className="input w-full"
                    type="number"
                    step="0.01"
                    value={form.max_price}
                    onChange={(e) => setForm((p) => ({ ...p, max_price: e.target.value }))}
                  />
                </div>
                <div className="col-span-1">
                  <label className="mb-1 block text-xs font-medium text-surface-700">Мин цена *</label>
                  <input
                    className="input w-full"
                    type="number"
                    step="0.01"
                    value={form.min_price}
                    onChange={(e) => setForm((p) => ({ ...p, min_price: e.target.value }))}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div>
                  <label className="mb-1 block text-sm font-medium text-surface-700">
                    Дата начала торгов *
                  </label>
                  <input
                    className="input w-full"
                    type="datetime-local"
                    value={form.trade_start_at}
                    onChange={(e) => setForm((p) => ({ ...p, trade_start_at: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-surface-700">
                    Дата окончания торгов (необязательно)
                  </label>
                  <input
                    className="input w-full"
                    type="datetime-local"
                    value={form.trade_end_at}
                    onChange={(e) => setForm((p) => ({ ...p, trade_end_at: e.target.value }))}
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-surface-700">
                  Источник (необязательно)
                </label>
                <input
                  className="input w-full"
                  value={form.source}
                  onChange={(e) => setForm((p) => ({ ...p, source: e.target.value }))}
                />
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              <button onClick={() => setCreateOpen(false)} className="btn-secondary flex-1">
                Отмена
              </button>
              <button
                onClick={async () => {
                  if (createBusy) return;
                  setCreateError(null);
                  setCreateBusy(true);
                  try {
                    const parsedGuarantee = Number(form.guarantee_amount);
                    const parsedMax = Number(form.max_price);
                    const parsedMin = Number(form.min_price);
                    if (!form.title.trim()) throw new Error("Заполните название");
                    if (!form.tender_link.trim()) throw new Error("Заполните ссылку на тендер");
                    if (!form.trade_start_at) throw new Error("Заполните дату начала торгов");
                    if (!Number.isFinite(parsedGuarantee) || parsedGuarantee < 0) {
                      throw new Error("Некорректная гарантийная сумма");
                    }
                    if (!Number.isFinite(parsedMax) || parsedMax < 0) throw new Error("Некорректная max цена");
                    if (!Number.isFinite(parsedMin) || parsedMin < 0) throw new Error("Некорректная min цена");

                    let customerId: string | null = null;
                    if (form.customer_id && form.customer_id !== "__new__") {
                      customerId = form.customer_id;
                    } else if (form.customer_id === "__new__" || clients.length === 0) {
                      // Create new customer when explicit "new" selected
                      // or when we have no clients in the system yet.
                      if (!form.new_customer_name.trim()) {
                        throw new Error("Укажите имя заказчика (для создания нового)");
                      }
                      const created = await createClient({
                        name: form.new_customer_name.trim(),
                        client_type: form.customer_type,
                        phone: "",
                        email: "",
                      });
                      customerId = created.id;
                    } else {
                      // Clients exist, but user didn't select any.
                      throw new Error("Выберите заказчика из списка");
                    }

                    const toIso = (v: string) => {
                      // datetime-local -> ISO
                      const dt = new Date(v);
                      return dt.toISOString();
                    };

                    await createTender({
                      title: form.title.trim(),
                      tender_link: form.tender_link.trim(),
                      customer_id: customerId,
                      guarantee_amount: parsedGuarantee,
                      max_price: parsedMax,
                      min_price: parsedMin,
                      trade_start_at: toIso(form.trade_start_at),
                      trade_end_at: form.trade_end_at ? toIso(form.trade_end_at) : null,
                      source: form.source.trim() || null,
                      status: form.status,
                    });

                    setCreateOpen(false);
                    await load();
                  } catch (e) {
                    setCreateError(e instanceof Error ? e.message : "Не удалось создать тендер");
                  } finally {
                    setCreateBusy(false);
                  }
                }}
                disabled={createBusy}
                className="btn-primary flex-1"
              >
                {createBusy ? "Создание..." : "Создать тендер"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Search,
  Plus,
  Phone,
  Mail,
  Building2,
  User,
  X,
  Briefcase,
  Pencil,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { fetchClients, createClient, updateClient, deleteClient } from "@/lib/api";
import type { ClientResponse } from "@/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;

type ExtraDataRow = { key: string; value: string };

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

function extraDataToRows(extra: Record<string, unknown> | null | undefined): ExtraDataRow[] {
  if (!extra || typeof extra !== "object") return [];
  return Object.entries(extra).map(([key, value]) => ({
    key,
    value: typeof value === "string" ? value : JSON.stringify(value),
  }));
}

function rowsToExtraData(rows: ExtraDataRow[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const row of rows) {
    const key = row.key.trim();
    if (!key) continue;
    const raw = row.value.trim();
    if (!raw) continue;
    try {
      out[key] = JSON.parse(raw);
    } catch {
      out[key] = raw;
    }
  }
  return out;
}

function emptyForm() {
  return {
    name: "",
    client_type: "individual",
    phone: "",
    email: "",
    address: "",
    primary_contact_name: "",
    inn: "",
    kpp: "",
    ogrn: "",
    ogrnip: "",
    bik: "",
    bank_account: "",
    corr_account: "",
    bank_name: "",
    notes: "",
    extra_data_items: [] as ExtraDataRow[],
  };
}

function primaryContactLabel(c: ClientResponse): string {
  const p = c.contacts.find((x) => x.is_primary);
  return (p?.full_name ?? c.contacts[0]?.full_name ?? "").trim();
}

function clientToForm(c: ClientResponse) {
  return {
    name: c.name,
    client_type: c.client_type,
    phone: c.phone ?? "",
    email: c.email ?? "",
    address: c.address ?? "",
    primary_contact_name: primaryContactLabel(c),
    inn: c.inn ?? "",
    kpp: c.kpp ?? "",
    ogrn: c.ogrn ?? "",
    ogrnip: c.ogrnip ?? "",
    bik: c.bik ?? "",
    bank_account: c.bank_account ?? "",
    corr_account: c.corr_account ?? "",
    bank_name: c.bank_name ?? "",
    notes: c.notes ?? "",
    extra_data_items: extraDataToRows(c.extra_data),
  };
}

export default function ClientsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [clients, setClients] = useState<ClientResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState<number>(20);

  const [dialogMode, setDialogMode] = useState<"closed" | "create" | "edit">("closed");
  const [editingClientId, setEditingClientId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [deletingClientId, setDeletingClientId] = useState<string | null>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(t);
  }, [search]);

  useEffect(() => {
    setOffset(0);
  }, [debouncedSearch, pageSize]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchClients({
        search: debouncedSearch || undefined,
        limit: pageSize,
        offset,
      });
      setClients(res.items);
      setTotal(res.total);
    } catch {
      setClients([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, offset, pageSize]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (searchParams.get("create") !== "1") return;
    setDialogMode("create");
    setEditingClientId(null);
    setForm(emptyForm());
    router.replace("/clients", { scroll: false });
  }, [searchParams, router]);

  function openCreate() {
    setDialogMode("create");
    setEditingClientId(null);
    setForm(emptyForm());
  }

  function openEdit(c: ClientResponse) {
    setDialogMode("edit");
    setEditingClientId(c.id);
    setForm(clientToForm(c));
  }

  function closeDialog() {
    setDialogMode("closed");
    setEditingClientId(null);
    setForm(emptyForm());
  }

  function buildPayloadFromForm(): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      address: form.address.trim() || null,
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      notes: form.notes.trim() || null,
    };
    if (form.client_type === "organization") {
      payload.inn = form.inn.trim() || null;
      payload.kpp = form.kpp.trim() || null;
      payload.ogrn = form.ogrn.trim() || null;
      payload.ogrnip = form.ogrnip.trim() || null;
      payload.bik = form.bik.trim() || null;
      payload.bank_account = form.bank_account.trim() || null;
      payload.corr_account = form.corr_account.trim() || null;
      payload.bank_name = form.bank_name.trim() || null;
    }
    payload.extra_data = rowsToExtraData(form.extra_data_items);
    return payload;
  }

  async function handleCreate() {
    if (!form.name.trim() || submitting) return;
    setSubmitting(true);
    try {
      const payload = buildPayloadFromForm();
      payload.client_type = form.client_type;
      if (form.primary_contact_name.trim()) {
        payload.primary_contact_name = form.primary_contact_name.trim();
      }
      await createClient(payload);
      closeDialog();
      void load();
    } catch {
      /* silent */
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSaveEdit() {
    if (!editingClientId || !form.name.trim() || submitting) return;
    setSubmitting(true);
    try {
      await updateClient(editingClientId, buildPayloadFromForm());
      closeDialog();
      void load();
    } catch {
      /* silent */
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteClient(client: ClientResponse) {
    if (deletingClientId || submitting) return;
    const ok = window.confirm(`Удалить клиента «${client.name}»? Это действие нельзя отменить.`);
    if (!ok) return;
    setDeletingClientId(client.id);
    try {
      await deleteClient(client.id);
      const isLastOnPage = clients.length === 1;
      if (isLastOnPage && offset > 0) {
        setOffset((prev) => Math.max(0, prev - pageSize));
      } else {
        void load();
      }
    } catch {
      /* silent */
    } finally {
      setDeletingClientId(null);
    }
  }

  const page = Math.floor(offset / pageSize) + 1;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const canPrev = offset > 0;
  const canNext = offset + pageSize < total;

  const dialogOpen = dialogMode !== "closed";

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Клиенты</h1>
        <button type="button" onClick={openCreate} className="btn-primary gap-1.5">
          <Plus className="h-4 w-4" /> Добавить клиента
        </button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative min-w-[min(100%,280px)] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            placeholder="Поиск по имени, телефону или email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-surface-600">
          <span className="whitespace-nowrap">На странице</span>
          <select
            className="input w-24 py-1.5"
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
          >
            {PAGE_SIZE_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-100 text-left text-surface-500">
                  <th className="px-4 py-3 font-medium">Клиент</th>
                  <th className="hidden px-4 py-3 font-medium lg:table-cell">Контакт</th>
                  <th className="hidden px-4 py-3 font-medium xl:table-cell">Адрес</th>
                  <th className="hidden px-4 py-3 font-medium sm:table-cell">Тип</th>
                  <th className="hidden px-4 py-3 font-medium md:table-cell">Телефон</th>
                  <th className="hidden px-4 py-3 font-medium md:table-cell">Email</th>
                  <th className="hidden px-4 py-3 font-medium xl:table-cell">Реквизиты</th>
                  <th className="hidden px-4 py-3 font-medium 2xl:table-cell">Комментарий</th>
                  <th className="px-4 py-3 font-medium">Создан</th>
                  <th className="w-24 px-2 py-3 font-medium text-right"> </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-50">
                {clients.map((client) => (
                  <tr key={client.id} className="hover:bg-surface-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-medium text-primary-700">
                          {client.name.charAt(0).toUpperCase()}
                        </div>
                        <span className="font-medium">{client.name}</span>
                      </div>
                    </td>
                    <td className="hidden px-4 py-3 text-surface-600 lg:table-cell">
                      {primaryContactLabel(client) || <span className="text-surface-300">—</span>}
                    </td>
                    <td className="hidden max-w-[18rem] truncate px-4 py-3 text-surface-600 xl:table-cell">
                      {client.address || <span className="text-surface-300">—</span>}
                    </td>
                    <td className="hidden px-4 py-3 sm:table-cell">
                      <span className="badge bg-surface-100 text-surface-600 gap-1">
                        {client.client_type === "organization" ? (
                          <>
                            <Building2 className="h-3 w-3" /> Организация
                          </>
                        ) : (
                          <>
                            <User className="h-3 w-3" /> Физ. лицо
                          </>
                        )}
                      </span>
                    </td>
                    <td className="hidden px-4 py-3 text-surface-600 md:table-cell">
                      {client.phone ? (
                        <span className="flex items-center gap-1">
                          <Phone className="h-3.5 w-3.5 text-surface-400" /> {client.phone}
                        </span>
                      ) : (
                        <span className="text-surface-300">—</span>
                      )}
                    </td>
                    <td className="hidden px-4 py-3 text-surface-600 md:table-cell">
                      {client.email ? (
                        <span className="flex items-center gap-1">
                          <Mail className="h-3.5 w-3.5 text-surface-400" /> {client.email}
                        </span>
                      ) : (
                        <span className="text-surface-300">—</span>
                      )}
                    </td>
                    <td className="hidden px-4 py-3 text-surface-600 xl:table-cell">
                      {client.client_type === "organization" ? (
                        <span className="flex items-center gap-1">
                          <Briefcase className="h-3.5 w-3.5 text-surface-400" />
                          {client.inn || client.kpp || client.ogrn ? "Заполнены" : "—"}
                        </span>
                      ) : (
                        <span className="text-surface-300">—</span>
                      )}
                    </td>
                    <td className="hidden max-w-[16rem] truncate px-4 py-3 text-surface-600 2xl:table-cell">
                      {client.notes || <span className="text-surface-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-surface-500">
                      {new Date(client.created_at).toLocaleDateString("ru-RU")}
                    </td>
                    <td className="px-2 py-3 text-right">
                      <div className="inline-flex items-center">
                        <button
                          type="button"
                          onClick={() => openEdit(client)}
                          className="inline-flex rounded-lg p-2 text-surface-400 hover:bg-primary-50 hover:text-primary-700"
                          title="Редактировать"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDeleteClient(client)}
                          disabled={deletingClientId === client.id}
                          className={cn(
                            "inline-flex rounded-lg p-2 text-surface-400 hover:bg-red-50 hover:text-red-700",
                            deletingClientId === client.id && "cursor-not-allowed opacity-50",
                          )}
                          title="Удалить"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {clients.length === 0 && (
                  <tr>
                    <td colSpan={11} className="px-4 py-12 text-center text-surface-400">
                      {debouncedSearch ? "Клиенты не найдены" : "Клиентов пока нет"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {total > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-surface-100 px-4 py-3 text-sm text-surface-600">
              <span>
                Всего: {total} · стр. {page} / {pageCount}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={!canPrev || loading}
                  onClick={() => setOffset((o) => Math.max(0, o - pageSize))}
                  className={cn("btn-ghost btn-sm inline-flex items-center gap-1", !canPrev && "opacity-40")}
                >
                  <ChevronLeft className="h-4 w-4" /> Назад
                </button>
                <button
                  type="button"
                  disabled={!canNext || loading}
                  onClick={() => setOffset((o) => o + pageSize)}
                  className={cn("btn-ghost btn-sm inline-flex items-center gap-1", !canNext && "opacity-40")}
                >
                  Вперёд <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {dialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center"
          onClick={closeDialog}
        >
          <div
            className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-white p-6 shadow-2xl sm:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">
                {dialogMode === "edit" ? "Редактировать клиента" : "Новый клиент"}
              </h2>
              <button type="button" onClick={closeDialog} className="btn-ghost p-1.5">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-surface-700">Имя *</label>
                <input
                  type="text"
                  className="input"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Имя клиента"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-surface-700">Тип</label>
                <select
                  className="input"
                  value={form.client_type}
                  onChange={(e) => setForm({ ...form, client_type: e.target.value })}
                  disabled={dialogMode === "edit"}
                  title={dialogMode === "edit" ? "Тип нельзя сменить в этом окне" : undefined}
                >
                  <option value="individual">Физ. лицо</option>
                  <option value="organization">Организация</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-surface-700">Адрес</label>
                <textarea
                  className="input min-h-[72px] resize-y"
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                  placeholder="Город, улица, дом"
                  rows={2}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-surface-700">Контактное лицо</label>
                <input
                  type="text"
                  className="input"
                  value={form.primary_contact_name}
                  onChange={(e) => setForm({ ...form, primary_contact_name: e.target.value })}
                  placeholder="ФИО"
                  disabled={dialogMode === "edit"}
                  title={
                    dialogMode === "edit"
                      ? "Редактирование контактов — через карточку клиента (API контактов)"
                      : undefined
                  }
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-surface-700">Телефон</label>
                  <input
                    type="tel"
                    className="input"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    placeholder="+7..."
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-surface-700">Email</label>
                  <input
                    type="email"
                    className="input"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    placeholder="email@example.com"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-surface-700">Заметки</label>
                <textarea
                  className="input min-h-[64px] resize-y"
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  placeholder="Внутренние заметки менеджера"
                  rows={2}
                />
              </div>
              <div className="space-y-2 rounded-lg border border-surface-100 bg-surface-50/60 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-surface-600">
                    Дополнительные данные (JSON ключ-значение)
                  </p>
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    onClick={() =>
                      setForm((prev) => ({
                        ...prev,
                        extra_data_items: [...prev.extra_data_items, { key: "", value: "" }],
                      }))
                    }
                  >
                    <Plus className="h-4 w-4" /> Добавить поле
                  </button>
                </div>
                {form.extra_data_items.length === 0 ? (
                  <p className="text-xs text-surface-400">
                    Например: `telegram`, `whatsapp`, `instagram`, `vk`, `utm_source`, `паспорт`.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {form.extra_data_items.map((item, idx) => (
                      <div key={`${idx}-${item.key}`} className="grid grid-cols-1 gap-2 md:grid-cols-12">
                        <input
                          type="text"
                          className="input md:col-span-4"
                          placeholder="Ключ, напр. telegram"
                          value={item.key}
                          onChange={(e) =>
                            setForm((prev) => {
                              const next = [...prev.extra_data_items];
                              next[idx] = { ...next[idx], key: e.target.value };
                              return { ...prev, extra_data_items: next };
                            })
                          }
                        />
                        <input
                          type="text"
                          className="input md:col-span-7"
                          placeholder="Значение, напр. @client_handle"
                          value={item.value}
                          onChange={(e) =>
                            setForm((prev) => {
                              const next = [...prev.extra_data_items];
                              next[idx] = { ...next[idx], value: e.target.value };
                              return { ...prev, extra_data_items: next };
                            })
                          }
                        />
                        <button
                          type="button"
                          className="btn-ghost md:col-span-1"
                          title="Удалить поле"
                          onClick={() =>
                            setForm((prev) => ({
                              ...prev,
                              extra_data_items: prev.extra_data_items.filter((_, i) => i !== idx),
                            }))
                          }
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {form.client_type === "organization" && (
                <div className="space-y-3 rounded-lg border border-surface-100 bg-surface-50/80 p-3">
                  <p className="text-xs font-medium text-surface-600">Реквизиты организации</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-surface-700">ИНН</label>
                      <input
                        type="text"
                        className="input"
                        value={form.inn}
                        onChange={(e) => setForm({ ...form, inn: e.target.value })}
                        inputMode="numeric"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-surface-700">КПП</label>
                      <input
                        type="text"
                        className="input"
                        value={form.kpp}
                        onChange={(e) => setForm({ ...form, kpp: e.target.value })}
                        inputMode="numeric"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-surface-700">ОГРН</label>
                      <input
                        type="text"
                        className="input"
                        value={form.ogrn}
                        onChange={(e) => setForm({ ...form, ogrn: e.target.value })}
                        inputMode="numeric"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-surface-700">ОГРНИП</label>
                      <input
                        type="text"
                        className="input"
                        value={form.ogrnip}
                        onChange={(e) => setForm({ ...form, ogrnip: e.target.value })}
                        inputMode="numeric"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-surface-700">БИК</label>
                      <input
                        type="text"
                        className="input"
                        value={form.bik}
                        onChange={(e) => setForm({ ...form, bik: e.target.value })}
                        inputMode="numeric"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-surface-700">Расчётный счёт</label>
                      <input
                        type="text"
                        className="input"
                        value={form.bank_account}
                        onChange={(e) => setForm({ ...form, bank_account: e.target.value })}
                        inputMode="numeric"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-surface-700">Корр. счёт</label>
                    <input
                      type="text"
                      className="input"
                      value={form.corr_account}
                      onChange={(e) => setForm({ ...form, corr_account: e.target.value })}
                      inputMode="numeric"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-surface-700">Банк</label>
                    <input
                      type="text"
                      className="input"
                      value={form.bank_name}
                      onChange={(e) => setForm({ ...form, bank_name: e.target.value })}
                      placeholder="Наименование банка"
                    />
                  </div>
                </div>
              )}
            </div>
            <div className="mt-6 flex gap-3">
              <button type="button" onClick={closeDialog} className="btn-secondary flex-1">
                Отмена
              </button>
              {dialogMode === "create" ? (
                <button
                  type="button"
                  onClick={() => void handleCreate()}
                  disabled={submitting || !form.name.trim()}
                  className="btn-primary flex-1"
                >
                  {submitting ? "Создание…" : "Создать клиента"}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleSaveEdit()}
                  disabled={submitting || !form.name.trim()}
                  className="btn-primary flex-1"
                >
                  {submitting ? "Сохранение…" : "Сохранить"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

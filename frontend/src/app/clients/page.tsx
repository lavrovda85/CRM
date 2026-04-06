"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Search,
  Plus,
  Phone,
  Mail,
  Building2,
  User,
  X,
  Briefcase,
} from "lucide-react";
import { fetchClients, createClient } from "@/lib/api";
import type { ClientResponse } from "@/types";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function ClientsPage() {
  const [clients, setClients] = useState<ClientResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", client_type: "individual", phone: "", email: "" });
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchClients({ search: search || undefined, limit: 50 });
      setClients(res.items);
      setTotal(res.total);
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [load]);

  async function handleCreate() {
    if (!form.name.trim() || creating) return;
    setCreating(true);
    try {
      await createClient(form);
      setShowCreate(false);
      setForm({ name: "", client_type: "individual", phone: "", email: "" });
      load();
    } catch {
      /* silent */
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Клиенты</h1>
        <button onClick={() => setShowCreate(true)} className="btn-primary gap-1.5">
          <Plus className="h-4 w-4" /> Добавить клиента
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
        <input
          type="text"
          placeholder="Поиск клиентов по имени, телефону или email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input pl-10"
        />
      </div>

      {/* Table */}
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
                  <th className="px-4 py-3 font-medium">Имя</th>
                  <th className="hidden px-4 py-3 font-medium sm:table-cell">Тип</th>
                  <th className="hidden px-4 py-3 font-medium md:table-cell">Телефон</th>
                  <th className="hidden px-4 py-3 font-medium md:table-cell">Email</th>
                  <th className="hidden px-4 py-3 font-medium lg:table-cell">Контакты</th>
                  <th className="px-4 py-3 font-medium">Создан</th>
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
                    <td className="hidden px-4 py-3 sm:table-cell">
                      <span className="badge bg-surface-100 text-surface-600 gap-1">
                        {client.client_type === "organization" ? (
                          <><Building2 className="h-3 w-3" /> Организация</>
                        ) : (
                          <><User className="h-3 w-3" /> Физ. лицо</>
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
                    <td className="hidden px-4 py-3 lg:table-cell">
                      <span className="flex items-center gap-1 text-surface-500">
                        <Briefcase className="h-3.5 w-3.5 text-surface-400" />
                        {client.contacts.length}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-surface-500">
                      {new Date(client.created_at).toLocaleDateString("ru-RU")}
                    </td>
                  </tr>
                ))}
                {clients.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-surface-400">
                      {search ? "Клиенты не найдены" : "Клиентов пока нет"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {total > clients.length && (
            <div className="border-t border-surface-100 p-3 text-center text-sm text-surface-400">
              Показано {clients.length} из {total}
            </div>
          )}
        </div>
      )}

      {/* Create Client Sheet */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center" onClick={() => setShowCreate(false)}>
          <div
            className="w-full max-w-lg rounded-t-2xl bg-white p-6 shadow-2xl sm:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">Новый клиент</h2>
              <button onClick={() => setShowCreate(false)} className="btn-ghost p-1.5">
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
                >
                  <option value="individual">Физ. лицо</option>
                  <option value="organization">Организация</option>
                </select>
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
            </div>
            <div className="mt-6 flex gap-3">
              <button onClick={() => setShowCreate(false)} className="btn-secondary flex-1">Отмена</button>
              <button onClick={handleCreate} disabled={creating || !form.name.trim()} className="btn-primary flex-1">
                {creating ? "Создание..." : "Создать клиента"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

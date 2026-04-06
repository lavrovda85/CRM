"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus, Pencil, UserX, Search } from "lucide-react";
import { ApiError, fetchUsers, deactivateUser, type UserListItem } from "@/lib/api";
import Link from "next/link";
import { UserFormModal } from "@/components/users/UserFormModal";
import type { UserDetail } from "@/lib/api";

const roleLabel: Record<string, string> = {
  admin: "Администратор",
  manager: "Менеджер",
  engineer: "Инженер",
  warehouse_manager: "Кладовщик",
  accountant: "Бухгалтер",
};

const roleColor: Record<string, string> = {
  admin: "bg-red-50 text-red-700",
  manager: "bg-blue-50 text-blue-700",
  engineer: "bg-green-50 text-green-700",
  warehouse_manager: "bg-amber-50 text-amber-700",
  accountant: "bg-violet-50 text-violet-700",
};

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await fetchUsers({ search: search || undefined, limit: 100 });
      setUsers(res.items);
    } catch (e) {
      if (e instanceof ApiError && e.isUnauthorized) {
        setLoadError(
          "Сессия недействительна для этого адреса. Войдите снова: токены с localhost не действуют на URL туннеля.",
        );
      } else if (e instanceof ApiError) {
        setLoadError(e.message || "Не удалось загрузить пользователей");
      } else {
        setLoadError("Не удалось загрузить пользователей (сеть или туннель).");
      }
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { load(); }, [load]);

  function handleCreate() {
    setEditingUser(null);
    setFormOpen(true);
  }

  function handleEdit(u: UserListItem) {
    setEditingUser(u as unknown as UserDetail);
    setFormOpen(true);
  }

  async function handleDeactivate(u: UserListItem) {
    if (!confirm(`Деактивировать пользователя "${u.full_name}"?`)) return;
    try {
      await deactivateUser(u.id);
      load();
    } catch { /* silent */ }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Пользователи</h1>
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 lg:p-6">
      {loadError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          <p>{loadError}</p>
          <p className="mt-2">
            <Link href="/login" className="font-medium text-primary-700 underline">
              Перейти ко входу
            </Link>
          </p>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Пользователи</h1>
        <button onClick={handleCreate} className="btn-primary gap-1.5">
          <Plus className="h-4 w-4" /> Добавить
        </button>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-surface-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по имени или email..."
          className="input pl-9"
        />
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-100 text-left text-surface-500">
              <th className="px-4 py-3 font-medium">Имя</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Роль</th>
              <th className="px-4 py-3 font-medium">Статус</th>
              <th className="px-4 py-3 font-medium w-20"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-50">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-surface-50 transition-colors">
                <td className="px-4 py-3 font-medium">
                  <div className="flex items-center gap-2">
                    {u.avatar_url ? (
                      <img src={u.avatar_url} alt={u.full_name} className="h-7 w-7 rounded-full object-cover" />
                    ) : (
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-100 text-xs text-surface-500">
                        {u.full_name.slice(0, 1).toUpperCase()}
                      </div>
                    )}
                    <span>{u.full_name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-surface-500">{u.email}</td>
                <td className="px-4 py-3">
                  <span className={`badge ${roleColor[u.role] ?? "bg-surface-100 text-surface-600"}`}>
                    {roleLabel[u.role] ?? u.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {u.is_active ? (
                    <span className="badge bg-green-50 text-green-700">Активен</span>
                  ) : (
                    <span className="badge bg-surface-100 text-surface-400">Неактивен</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <button onClick={() => handleEdit(u)} className="rounded p-1 text-surface-400 hover:text-primary-600 hover:bg-primary-50" title="Редактировать">
                      <Pencil className="h-4 w-4" />
                    </button>
                    {u.is_active && (
                      <button onClick={() => handleDeactivate(u)} className="rounded p-1 text-surface-300 hover:text-red-500 hover:bg-red-50" title="Деактивировать">
                        <UserX className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-surface-400">Пользователи не найдены</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <UserFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={load}
        user={editingUser}
      />
    </div>
  );
}

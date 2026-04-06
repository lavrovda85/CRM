"use client";

import { useState } from "react";
import { Shield, Check, X as XIcon } from "lucide-react";

const ROLES = [
  { id: "admin", label: "Администратор" },
  { id: "manager", label: "Менеджер" },
  { id: "engineer", label: "Инженер" },
  { id: "warehouse_manager", label: "Кладовщик" },
  { id: "accountant", label: "Бухгалтер" },
];

const RESOURCES = [
  { id: "tasks", label: "Задачи" },
  { id: "users", label: "Пользователи" },
  { id: "clients", label: "Клиенты" },
  { id: "templates", label: "Шаблоны" },
  { id: "warehouse", label: "Склад" },
  { id: "equipment", label: "Оборудование" },
  { id: "analytics", label: "Аналитика" },
  { id: "deals", label: "Сделки" },
  { id: "tenders", label: "Тендеры" },
  { id: "settings", label: "Настройки" },
];

type Perm = "full" | "read" | "own" | "none";

const DEFAULT_MATRIX: Record<string, Record<string, Perm>> = {
  tasks:      { admin: "full", manager: "full", engineer: "own",  warehouse_manager: "read", accountant: "read" },
  users:      { admin: "full", manager: "read", engineer: "none", warehouse_manager: "none", accountant: "none" },
  clients:    { admin: "full", manager: "full", engineer: "read", warehouse_manager: "none", accountant: "read" },
  templates:  { admin: "full", manager: "full", engineer: "read", warehouse_manager: "none", accountant: "none" },
  warehouse:  { admin: "full", manager: "read", engineer: "read", warehouse_manager: "full", accountant: "read" },
  equipment:  { admin: "full", manager: "read", engineer: "read", warehouse_manager: "full", accountant: "read" },
  analytics:  { admin: "full", manager: "full", engineer: "own",  warehouse_manager: "own",  accountant: "full" },
  deals:      { admin: "full", manager: "full", engineer: "none", warehouse_manager: "none", accountant: "read" },
  tenders:    { admin: "full", manager: "full", engineer: "none", warehouse_manager: "none", accountant: "read" },
  settings:   { admin: "full", manager: "none", engineer: "none", warehouse_manager: "none", accountant: "none" },
};

const PERM_LABELS: Record<Perm, { label: string; color: string }> = {
  full: { label: "Полный", color: "bg-green-50 text-green-700" },
  read: { label: "Чтение", color: "bg-blue-50 text-blue-700" },
  own:  { label: "Свои", color: "bg-amber-50 text-amber-700" },
  none: { label: "Нет", color: "bg-surface-100 text-surface-400" },
};

export default function RolesPage() {
  const [matrix, setMatrix] = useState(DEFAULT_MATRIX);

  function cyclePerm(resource: string, role: string) {
    const order: Perm[] = ["full", "read", "own", "none"];
    const current = matrix[resource]?.[role] ?? "none";
    const next = order[(order.indexOf(current) + 1) % order.length];
    setMatrix((prev) => ({
      ...prev,
      [resource]: { ...prev[resource], [role]: next },
    }));
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 lg:p-6">
      <div className="flex items-center gap-3">
        <Shield className="h-6 w-6 text-primary-600" />
        <h1 className="text-2xl font-bold">Матрица прав доступа</h1>
      </div>

      <p className="text-sm text-surface-500">
        Нажмите на ячейку для переключения уровня доступа. Изменения применяются к новым сессиям.
      </p>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-100 bg-surface-50">
                <th className="px-4 py-3 text-left font-semibold text-surface-700">Ресурс</th>
                {ROLES.map((r) => (
                  <th key={r.id} className="px-3 py-3 text-center font-semibold text-surface-700 min-w-[110px]">
                    {r.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-50">
              {RESOURCES.map((res) => (
                <tr key={res.id} className="hover:bg-surface-50/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-surface-800">{res.label}</td>
                  {ROLES.map((role) => {
                    const perm = matrix[res.id]?.[role.id] ?? "none";
                    const cfg = PERM_LABELS[perm];
                    return (
                      <td key={role.id} className="px-3 py-3 text-center">
                        <button
                          onClick={() => cyclePerm(res.id, role.id)}
                          className={`badge cursor-pointer transition-all hover:opacity-80 ${cfg.color}`}
                        >
                          {cfg.label}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs text-surface-500">
        <span className="flex items-center gap-1"><span className="badge bg-green-50 text-green-700">Полный</span> CRUD</span>
        <span className="flex items-center gap-1"><span className="badge bg-blue-50 text-blue-700">Чтение</span> только просмотр</span>
        <span className="flex items-center gap-1"><span className="badge bg-amber-50 text-amber-700">Свои</span> только свои записи</span>
        <span className="flex items-center gap-1"><span className="badge bg-surface-100 text-surface-400">Нет</span> нет доступа</span>
      </div>
    </div>
  );
}

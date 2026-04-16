"use client";

/**
 * Work planning table: date/time, object, customer/contact, work type/cost,
 * equipment, status, two executor columns — aligned with field scheduling sketches.
 */

import Link from "next/link";
import { useMemo } from "react";
import type { ClientResponse } from "@/types";
import type { TaskResponse } from "@/types";
import { cn } from "@/lib/utils";

function cfStr(cf: Record<string, unknown>, ...keys: string[]): string {
  for (const k of keys) {
    const v = cf[k];
    if (typeof v === "string" && v.trim()) return v.trim();
    if (typeof v === "number" && Number.isFinite(v)) return String(v);
  }
  return "—";
}

function contactLine(client: ClientResponse | undefined): string {
  if (!client) return "—";
  const phone = client.phone?.trim();
  const email = client.email?.trim();
  const c0 = client.contacts?.[0];
  const extra = c0
    ? [c0.phone, c0.email].filter((x): x is string => typeof x === "string" && x.trim().length > 0).join(", ")
    : "";
  const parts = [phone, email, extra].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "—";
}

function scheduleInstant(task: TaskResponse): Date | null {
  const raw = task.started_at || task.due_date;
  if (!raw) return null;
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

function DiagonalHeader({
  topLeft,
  bottomRight,
  className,
}: {
  topLeft: string;
  bottomRight: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex h-14 min-w-[5.5rem] flex-col justify-center overflow-hidden border border-surface-200 bg-surface-50/80 px-0 py-0",
        className,
      )}
    >
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full text-surface-200"
        aria-hidden
        preserveAspectRatio="none"
      >
        <line x1="100%" y1="0" x2="0" y2="100%" stroke="currentColor" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      </svg>
      <span className="relative z-[1] self-start pl-1 pt-0.5 text-[10px] font-semibold uppercase tracking-wide text-surface-600">
        {topLeft}
      </span>
      <span className="relative z-[1] mt-auto self-end pr-1 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-surface-600">
        {bottomRight}
      </span>
    </div>
  );
}

export interface WorkScheduleTableProps {
  tasks: TaskResponse[];
  clientsById: Record<string, ClientResponse>;
  statusLabel: Record<string, string>;
  isTerminal: (status: string) => boolean;
}

export function WorkScheduleTable({
  tasks,
  clientsById,
  statusLabel,
  isTerminal,
}: WorkScheduleTableProps) {
  const rows = useMemo(() => {
    const list = [...tasks];
    list.sort((a, b) => {
      const da = scheduleInstant(a)?.getTime() ?? 0;
      const db = scheduleInstant(b)?.getTime() ?? 0;
      if (da !== db) return da - db;
      return a.title.localeCompare(b.title, "ru");
    });
    return list;
  }, [tasks]);

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] border-collapse text-sm">
          <thead>
            <tr className="text-left">
              <th className="sticky left-0 z-[2] bg-surface-50 p-0 align-bottom shadow-[2px_0_0_0_rgb(241_245_249)]">
                <DiagonalHeader topLeft="дата" bottomRight="время" />
              </th>
              <th className="border border-surface-200 bg-surface-50 px-2 py-2 text-xs font-semibold uppercase tracking-wide text-surface-600">
                объект
              </th>
              <th className="p-0 align-bottom">
                <DiagonalHeader topLeft="заказчик" bottomRight="контакт" className="min-w-[8rem]" />
              </th>
              <th className="p-0 align-bottom">
                <DiagonalHeader topLeft="вид работы" bottomRight="стоимость" className="min-w-[9rem]" />
              </th>
              <th className="border border-surface-200 bg-surface-50 px-2 py-2 text-xs font-semibold uppercase tracking-wide text-surface-600">
                оборудование
              </th>
              <th className="border border-surface-200 bg-surface-50 px-2 py-2 text-xs font-semibold uppercase tracking-wide text-surface-600">
                статус
              </th>
              <th className="border border-surface-200 bg-surface-50 px-2 py-2 text-xs font-semibold uppercase tracking-wide text-surface-600">
                исполнитель
              </th>
              <th className="border border-surface-200 bg-surface-50 px-2 py-2 text-xs font-semibold uppercase tracking-wide text-surface-600">
                исполнитель
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-100">
            {rows.map((task) => {
              const when = scheduleInstant(task);
              const dateStr = when
                ? when.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" })
                : "—";
              const timeStr = when
                ? when.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
                : "—";
              const cf = task.custom_fields ?? {};
              const client = task.client_id ? clientsById[task.client_id] : undefined;
              const objectLabel =
                (task.address && task.address.trim()) ||
                cfStr(cf, "object", "site", "объект") ||
                task.title;
              const workType = task.template?.name?.trim() || cfStr(cf, "work_type", "вид_работы", "kind");
              const cost = cfStr(cf, "cost", "стоимость", "estimated_cost", "price");
              const equipment = cfStr(cf, "equipment", "оборудование", "unit");
              const co = task.co_assignees ?? [];
              const exec2 = co[0]?.full_name ?? "—";
              const terminal = isTerminal(task.status);

              return (
                <tr key={task.id} className="hover:bg-surface-50/80">
                  <td className="sticky left-0 z-[1] border border-surface-100 bg-white px-2 py-2 shadow-[2px_0_0_0_rgb(241_245_249)]">
                    <div className="whitespace-nowrap text-surface-800">{dateStr}</div>
                    <div className="text-xs text-surface-500">{timeStr}</div>
                  </td>
                  <td className="max-w-[14rem] border border-surface-100 px-2 py-2">
                    <Link
                      href={`/tasks/${task.id}`}
                      className={cn(
                        "line-clamp-2 font-medium hover:text-primary-600",
                        terminal ? "text-surface-500 line-through decoration-surface-400/80" : "text-surface-900",
                      )}
                    >
                      {objectLabel}
                    </Link>
                  </td>
                  <td className="max-w-[12rem] border border-surface-100 px-2 py-2">
                    <div className="line-clamp-2 text-surface-800">{client?.name ?? "—"}</div>
                    <div className="line-clamp-2 text-xs text-surface-500">{contactLine(client)}</div>
                  </td>
                  <td className="max-w-[12rem] border border-surface-100 px-2 py-2">
                    <div className="line-clamp-2 text-surface-800">{workType}</div>
                    <div className="text-xs text-surface-600">{cost}</div>
                  </td>
                  <td className="max-w-[12rem] border border-surface-100 px-2 py-2 text-surface-700">
                    <span className="line-clamp-2">{equipment}</span>
                  </td>
                  <td className="whitespace-nowrap border border-surface-100 px-2 py-2">
                    <span
                      className={cn(
                        "inline-flex rounded-md px-2 py-0.5 text-xs font-medium",
                        task.status === "done" || task.status === "completed" || task.status === "closed"
                          ? "bg-green-50 text-green-800"
                          : task.status === "in_progress"
                            ? "bg-blue-50 text-blue-800"
                            : "bg-surface-100 text-surface-700",
                      )}
                    >
                      {statusLabel[task.status] ?? task.status}
                    </span>
                  </td>
                  <td className="max-w-[9rem] border border-surface-100 px-2 py-2 text-surface-700">
                    <span className="line-clamp-2">{task.assignee?.full_name ?? "—"}</span>
                  </td>
                  <td className="max-w-[9rem] border border-surface-100 px-2 py-2 text-surface-700">
                    <span className="line-clamp-2">{exec2}</span>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-surface-400">
                  Нет задач для плана. Создайте задачу или ослабьте фильтры.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="border-t border-surface-100 px-3 py-2 text-xs text-surface-500">
        Дата и время берутся из начала работы или срока; заказчик — из карточки клиента; вид работы, стоимость и
        оборудование можно задать в шаблоне и полях задачи (custom_fields).
      </p>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useMemo } from "react";
import type { TaskResponse } from "@/types";

export interface FieldWorkWeekBoardProps {
  tasks: TaskResponse[];
  weekStartDate: string;
  hourStart: number;
  hourEndExclusive: number;
  onSlotClick?: (slot: { dayKey: string; hour: number }) => void;
}

function startOfWeekMonday(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function isoDayKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function ruDayLabel(date: Date): string {
  return date.toLocaleDateString("ru-RU", { weekday: "short", day: "2-digit", month: "2-digit" });
}

export function FieldWorkWeekBoard({
  tasks,
  weekStartDate,
  hourStart,
  hourEndExclusive,
  onSlotClick,
}: FieldWorkWeekBoardProps) {
  const { days, hours, tasksByCell } = useMemo(() => {
    const monday = startOfWeekMonday(new Date(`${weekStartDate}T00:00:00`));
    const daysLocal = Array.from({ length: 7 }, (_, idx) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + idx);
      return { key: isoDayKey(d), label: ruDayLabel(d) };
    });
    const hoursLocal = Array.from({ length: Math.max(1, hourEndExclusive - hourStart) }, (_, i) => hourStart + i);

    const cellMap: Record<string, TaskResponse[]> = {};
    for (const day of daysLocal) {
      for (const h of hoursLocal) {
        cellMap[`${day.key}__${h}`] = [];
      }
    }
    for (const task of tasks) {
      const raw = task.started_at || task.due_date;
      if (!raw) continue;
      const d = new Date(raw);
      if (Number.isNaN(d.getTime())) continue;
      const dayKey = isoDayKey(d);
      const hour = d.getHours();
      const key = `${dayKey}__${hour}`;
      if (cellMap[key]) cellMap[key].push(task);
    }
    return { days: daysLocal, hours: hoursLocal, tasksByCell: cellMap };
  }, [tasks, weekStartDate, hourStart, hourEndExclusive]);

  return (
    <div className="card w-full overflow-hidden">
      <div className="overflow-x-auto">
        <div
          className="min-w-[980px]"
          style={{ display: "grid", gridTemplateColumns: `64px repeat(${days.length}, minmax(130px, 1fr))` }}
        >
          <div className="sticky left-0 z-20 border-b border-surface-100 bg-white px-2 py-2 text-xs font-semibold text-surface-500">
            Часы
          </div>
          {days.map((day) => (
            <div key={day.key} className="border-b border-surface-100 bg-white px-2 py-2 text-center text-xs font-semibold text-surface-700">
              {day.label}
            </div>
          ))}

          {hours.map((hour) => (
            <div key={`row-${hour}`} style={{ display: "contents" }}>
              <div className="sticky left-0 z-10 border-b border-surface-50 bg-white px-2 py-2 text-xs font-medium text-surface-600">
                {String(hour).padStart(2, "0")}:00
              </div>
              {days.map((day) => {
                const cellKey = `${day.key}__${hour}`;
                const cellTasks = tasksByCell[cellKey] ?? [];
                return (
                  <div
                    key={cellKey}
                    onClick={() => onSlotClick?.({ dayKey: day.key, hour })}
                    className="group min-h-[64px] cursor-pointer border-b border-surface-50 p-1.5 hover:bg-primary-50/40"
                  >
                    {cellTasks.length === 0 ? (
                      <div className="flex h-full min-h-[48px] items-center justify-center text-lg font-light text-primary-300 opacity-0 transition-opacity group-hover:opacity-100">
                        +
                      </div>
                    ) : (
                      <div className="space-y-1">
                        {cellTasks.slice(0, 3).map((task) => (
                          <Link
                            key={task.id}
                            href={`/tasks/${task.id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="block rounded border border-surface-200 bg-white px-1.5 py-1 text-[11px] text-surface-800 hover:border-primary-300 hover:text-primary-700"
                            title={task.title}
                          >
                            <div className="truncate">{task.title}</div>
                            {(() => {
                              const workerIdsRaw = task.custom_fields?.["worker_equipment_ids"];
                              const workerCount = Array.isArray(workerIdsRaw)
                                ? workerIdsRaw.length
                                : (() => {
                                    const one = task.custom_fields?.["worker_equipment_id"];
                                    return typeof one === "string" && one.trim() ? 1 : 0;
                                  })();
                              const vehicleIdsRaw = task.custom_fields?.["extra_equipment_ids"];
                              const vehicleCount = Array.isArray(vehicleIdsRaw) ? vehicleIdsRaw.length : 0;
                              const totalKm = Number(task.custom_fields?.["vehicle_mileage_total_km"] ?? 0);
                              if (workerCount <= 0 && vehicleCount <= 0 && (!Number.isFinite(totalKm) || totalKm <= 0)) {
                                return null;
                              }
                              return (
                                <div className="truncate text-[10px] text-surface-500">
                                  {workerCount > 0 ? `Рабочие: ${workerCount}` : ""}
                                  {workerCount > 0 && (vehicleCount > 0 || (Number.isFinite(totalKm) && totalKm > 0))
                                    ? " · "
                                    : ""}
                                  {(vehicleCount > 0 || (Number.isFinite(totalKm) && totalKm > 0)) ? `Авто: ${vehicleCount}` : ""}
                                  {Number.isFinite(totalKm) && totalKm > 0 ? ` · ${totalKm.toFixed(1)} км` : ""}
                                </div>
                              );
                            })()}
                          </Link>
                        ))}
                        {cellTasks.length > 3 && (
                          <div className="text-[10px] text-surface-500">+{cellTasks.length - 3} еще</div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

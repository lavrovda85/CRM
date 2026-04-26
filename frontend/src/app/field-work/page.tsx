"use client";

/**
 * Field / crew task board: tasks on a dedicated Kanban board, isolated from office ``/tasks``.
 * Workers are not CRM users — register crews as equipment with ``hourly_rate`` (category e.g. ``crew``).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Calendar, ChevronLeft, ChevronRight, HardHat, LayoutGrid, Plus } from "lucide-react";
import { KanbanBoard, type KanbanCard, type KanbanColumn } from "@/components/boards/KanbanBoard";
import { FieldWorkWeekBoard } from "@/components/boards/FieldWorkWeekBoard";
import { CreateTaskModal } from "@/components/tasks/CreateTaskModal";
import {
  ApiError,
  fetchActiveCompany,
  fetchTasks,
  transitionTask,
} from "@/lib/api";
import { isTerminalTaskStatus } from "@/lib/timelineTaskIntervals";
import type { TaskResponse } from "@/types";
import { useAuthStore } from "@/stores/auth";
import { useRouter } from "next/navigation";

const KANBAN_COLUMNS: KanbanColumn[] = [
  { id: "new", title: "Новая", color: "#94a3b8" },
  { id: "dispatched", title: "Назначена", color: "#38bdf8" },
  { id: "in_progress", title: "В работе", color: "#3b82f6" },
  { id: "testing", title: "Согласование", color: "#fbbf24" },
  { id: "done", title: "Выполнено", color: "#22c55e" },
];

const KANBAN_IDS = new Set(KANBAN_COLUMNS.map((c) => c.id));

function kanbanBoardColumnId(status: string): string {
  if (status === "act_signing") return "done";
  if (status === "photo_report") return "testing";
  return status;
}

const priorityColor: Record<string, string> = {
  low: "#22c55e",
  medium: "#eab308",
  high: "#f97316",
  critical: "#ef4444",
};

const priorityLabel: Record<string, string> = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
  critical: "Критический",
};

export default function FieldWorkBoardPage() {
  const router = useRouter();
  const authUser = useAuthStore((s) => s.user);
  const canConfigure = authUser?.role === "admin" || authUser?.role === "manager";

  const [boardId, setBoardId] = useState<string | null>(null);
  const [defaultTemplateId, setDefaultTemplateId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createPrefill, setCreatePrefill] = useState<{ startedAt?: string; dueDate?: string } | undefined>();
  const [view, setView] = useState<"kanban" | "week">("kanban");
  const [weekStartDate, setWeekStartDate] = useState(() => {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  });
  /** Saved allowlist: empty = all templates in create modal; non-empty = restrict dropdown. */
  const [fieldWorkTemplateIds, setFieldWorkTemplateIds] = useState<string[]>([]);

  const refreshCompany = useCallback(async () => {
    const c = await fetchActiveCompany();
    const bid = c.field_work_board_id?.trim() || null;
    const tid = c.default_field_task_template_id?.trim() || null;
    const ft = c.field_work_template_ids;
    const filterIds =
      Array.isArray(ft) && ft.length > 0 ? ft.map((x) => String(x).trim()).filter(Boolean) : [];
    setBoardId(bid);
    setDefaultTemplateId(tid);
    setFieldWorkTemplateIds(filterIds);
    return { bid, tid };
  }, []);

  const loadTasks = useCallback(async () => {
    const { bid } = await refreshCompany();
    if (!bid) {
      setTasks([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const res = await fetchTasks({
        board_id: bid,
        limit: 200,
        status_not_in: "closed,completed",
      });
      setTasks(res.items);
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [refreshCompany]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  const columns = useMemo(() => {
    const cols = [...KANBAN_COLUMNS];
    const unmapped = tasks.filter((t) => !KANBAN_IDS.has(kanbanBoardColumnId(t.status)));
    if (unmapped.length > 0) cols.push({ id: "_other", title: "Прочее", color: "#94a3b8" });
    return cols;
  }, [tasks]);

  const cards: Record<string, KanbanCard[]> = useMemo(() => {
    const out: Record<string, KanbanCard[]> = {};
    for (const col of columns) {
      out[col.id] = tasks
        .filter((t) =>
          col.id === "_other"
            ? !KANBAN_IDS.has(kanbanBoardColumnId(t.status))
            : kanbanBoardColumnId(t.status) === col.id,
        )
        .map((task) => ({
          ...(function () {
            const totalKmRaw = task.custom_fields?.["vehicle_mileage_total_km"];
            const totalKm = Number(totalKmRaw);
            const extraIdsRaw = task.custom_fields?.["extra_equipment_ids"];
            const vehicleCount = Array.isArray(extraIdsRaw) ? extraIdsRaw.length : 0;
            const workerIdsRaw = task.custom_fields?.["worker_equipment_ids"];
            const workerCount = Array.isArray(workerIdsRaw)
              ? workerIdsRaw.length
              : (() => {
                  const one = task.custom_fields?.["worker_equipment_id"];
                  return typeof one === "string" && one.trim() ? 1 : 0;
                })();
            const badges = [
              {
                label: priorityLabel[task.priority] ?? task.priority,
                color: priorityColor[task.priority] ?? "#94a3b8",
              },
            ];
            if (workerCount > 0) {
              badges.push({
                label: `Рабочие: ${workerCount}`,
                color: "#0f766e",
              });
            }
            if (vehicleCount > 0 || (Number.isFinite(totalKm) && totalKm > 0)) {
              const kmLabel = Number.isFinite(totalKm) && totalKm > 0 ? ` · ${totalKm.toFixed(1)} км` : "";
              badges.push({
                label: `Авто: ${vehicleCount}${kmLabel}`,
                color: "#475569",
              });
            }
            return {
              badges,
            };
          })(),
          id: task.id,
          title: task.title,
          subtitle: (() => {
            const namesRaw = task.custom_fields?.["worker_equipment_names"];
            if (Array.isArray(namesRaw) && namesRaw.length > 0) {
              const names = namesRaw.map((x) => String(x)).filter(Boolean);
              if (names.length === 1) return names[0];
              if (names.length > 1) return `${names[0]} +${names.length - 1}`;
            }
            if (typeof task.custom_fields?.["worker_equipment_name"] === "string") {
              return task.custom_fields["worker_equipment_name"];
            }
            return task.assignee?.full_name ?? undefined;
          })(),
          completed: isTerminalTaskStatus(task.status),
        }));
    }
    return out;
  }, [tasks, columns]);

  function setWeekByOffset(days: number) {
    const d = new Date(`${weekStartDate}T00:00:00`);
    d.setDate(d.getDate() + days);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    setWeekStartDate(`${y}-${m}-${day}`);
  }

  function handleWeekSlotClick(slot: { dayKey: string; hour: number }) {
    const pad = (n: number) => String(n).padStart(2, "0");
    const startedAt = `${slot.dayKey}T${pad(slot.hour)}:00`;
    const dueHour = Math.min(slot.hour + 1, 23);
    const dueDate = `${slot.dayKey}T${pad(dueHour)}:00`;
    setCreatePrefill({ startedAt, dueDate });
    setCreateOpen(true);
  }

  async function handleCardMove(cardId: string, _from: string, toCol: string) {
    if (toCol === "_other") return;
    const prev = [...tasks];
    setTasks((cur) => cur.map((t) => (t.id === cardId ? { ...t, status: toCol } : t)));
    try {
      await transitionTask(cardId, toCol);
    } catch {
      setTasks(prev);
    }
  }

  return (
    <div className="mx-auto w-full max-w-[100rem] space-y-4 overflow-x-hidden p-3 sm:p-4 lg:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-100 text-amber-800">
            <HardHat className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-surface-900">Выездные работы</h1>
            <p className="text-sm text-surface-500">
              Отдельная доска от офисных задач. Бригады учитывайте как{" "}
              <Link href="/equipment" className="text-primary-600 hover:underline">
                оборудование
              </Link>{" "}
              с почасовой ставкой (поле «Ставка часа»).
            </p>
          </div>
        </div>
        <button
          type="button"
          disabled={!boardId}
          onClick={() => setCreateOpen(true)}
          className="btn-primary inline-flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Создать задачу
        </button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex rounded-lg border border-surface-200 bg-white p-0.5">
          <button
            type="button"
            onClick={() => setView("kanban")}
            className={`rounded-md px-2 py-1.5 ${view === "kanban" ? "bg-primary-600 text-white" : "text-surface-500"}`}
            title="Канбан"
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setView("week")}
            className={`rounded-md px-2 py-1.5 ${view === "week" ? "bg-primary-600 text-white" : "text-surface-500"}`}
            title="Недельный календарь"
          >
            <Calendar className="h-4 w-4" />
          </button>
        </div>
        {view === "week" && (
          <div className="inline-flex items-center gap-1 rounded-lg border border-surface-200 bg-white p-1">
            <button type="button" onClick={() => setWeekByOffset(-7)} className="btn-ghost btn-sm">
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-1 text-xs text-surface-600">Неделя от {weekStartDate}</span>
            <button type="button" onClick={() => setWeekByOffset(7)} className="btn-ghost btn-sm">
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {!boardId && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Доска не настроена</p>
          {canConfigure ? (
            <p className="mt-1">
              Настройте доску выездных работ в разделе{" "}
              <Link href="/settings" className="text-primary-700 underline">
                Настройки
              </Link>.
            </p>
          ) : (
            <p className="mt-1">Попросите администратора или руководителя назначить доску для выездных работ.</p>
          )}
        </div>
      )}

      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{loadError}</div>
      )}

      {boardId && (
        <>
          {loading && <p className="text-sm text-surface-500">Загрузка…</p>}
          {view === "kanban" ? (
            <KanbanBoard
              columns={columns}
              cards={cards}
              onCardMove={handleCardMove}
              onCardClick={(id) => router.push(`/tasks/${id}`)}
            />
          ) : (
            <FieldWorkWeekBoard
              tasks={tasks}
              weekStartDate={weekStartDate}
              hourStart={8}
              hourEndExclusive={20}
              onSlotClick={handleWeekSlotClick}
            />
          )}
        </>
      )}

      <CreateTaskModal
        open={createOpen}
        onClose={() => {
          setCreateOpen(false);
          setCreatePrefill(undefined);
        }}
        variant="field_work"
        fixedBoardId={boardId ?? undefined}
        defaultTemplateId={defaultTemplateId ?? undefined}
        lockTemplate={false}
        fieldWorkTemplateAllowlist={fieldWorkTemplateIds.length > 0 ? fieldWorkTemplateIds : null}
        initialValues={createPrefill}
        onCreated={() => {
          void loadTasks();
        }}
      />
    </div>
  );
}

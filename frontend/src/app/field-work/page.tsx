"use client";

/**
 * Field / crew task board: tasks on a dedicated Kanban board, isolated from office ``/tasks``.
 * Workers are not CRM users — register crews as equipment with ``hourly_rate`` (category e.g. ``crew``).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Calendar, ChevronLeft, ChevronRight, HardHat, LayoutGrid, Plus, Save, Sparkles } from "lucide-react";
import { KanbanBoard, type KanbanCard, type KanbanColumn } from "@/components/boards/KanbanBoard";
import { FieldWorkWeekBoard } from "@/components/boards/FieldWorkWeekBoard";
import { CreateTaskModal } from "@/components/tasks/CreateTaskModal";
import {
  ApiError,
  createBoard,
  fetchActiveCompany,
  fetchBoards,
  fetchTasks,
  fetchTemplates,
  patchCompanyWorkspaceSettings,
  transitionTask,
} from "@/lib/api";
import { FIELD_WORK_BOARD_COLUMNS } from "@/lib/fieldWorkBoard";
import { isTerminalTaskStatus } from "@/lib/timelineTaskIntervals";
import type { BoardResponse, TaskResponse, TemplateResponse } from "@/types";
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
  const [settingsBoardDraft, setSettingsBoardDraft] = useState("");
  const [settingsTemplateDraft, setSettingsTemplateDraft] = useState("");
  const [settingsMsg, setSettingsMsg] = useState<string | null>(null);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [boards, setBoards] = useState<BoardResponse[]>([]);
  const [templates, setTemplates] = useState<TemplateResponse[]>([]);
  const [refsLoading, setRefsLoading] = useState(false);
  const [creatingBoard, setCreatingBoard] = useState(false);
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
    setSettingsBoardDraft(bid ?? "");
    setSettingsTemplateDraft(tid ?? "");
    setFieldWorkTemplateIds(filterIds);
    return { bid, tid };
  }, []);

  const loadSettingsRefs = useCallback(async () => {
    if (!canConfigure) return;
    setRefsLoading(true);
    try {
      const [br, tr] = await Promise.all([
        fetchBoards({ limit: 100, offset: 0 }),
        fetchTemplates({ limit: 100, offset: 0 }),
      ]);
      setBoards(br.items);
      setTemplates(tr.items);
    } catch {
      setBoards([]);
      setTemplates([]);
    } finally {
      setRefsLoading(false);
    }
  }, [canConfigure]);

  useEffect(() => {
    void loadSettingsRefs();
  }, [loadSettingsRefs]);

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
          id: task.id,
          title: task.title,
          subtitle:
            (typeof task.custom_fields?.["worker_equipment_name"] === "string"
              ? task.custom_fields["worker_equipment_name"]
              : undefined) ??
            task.assignee?.full_name ??
            undefined,
          badges: [
            {
              label: priorityLabel[task.priority] ?? task.priority,
              color: priorityColor[task.priority] ?? "#94a3b8",
            },
          ],
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

  async function saveWorkspaceSettings() {
    setSettingsSaving(true);
    setSettingsMsg(null);
    try {
      await patchCompanyWorkspaceSettings({
        field_work_board_id: settingsBoardDraft.trim() || null,
        default_field_task_template_id: settingsTemplateDraft.trim() || null,
        field_work_template_ids: fieldWorkTemplateIds.length > 0 ? fieldWorkTemplateIds : [],
      });
      setSettingsMsg("Сохранено");
      await loadTasks();
    } catch (e) {
      setSettingsMsg(e instanceof ApiError ? e.message : "Не удалось сохранить");
    } finally {
      setSettingsSaving(false);
    }
  }

  async function quickCreateFieldWorkBoard() {
    setCreatingBoard(true);
    setSettingsMsg(null);
    try {
      const b = await createBoard({
        name: "Выездные работы",
        description: "Канбан выездных бригад (создано из раздела «Выездные работы»).",
        columns: FIELD_WORK_BOARD_COLUMNS,
      });
      await patchCompanyWorkspaceSettings({
        field_work_board_id: b.id,
        default_field_task_template_id: settingsTemplateDraft.trim() || null,
        field_work_template_ids: fieldWorkTemplateIds.length > 0 ? fieldWorkTemplateIds : [],
      });
      setSettingsBoardDraft(b.id);
      setSettingsMsg("Доска создана и привязана к этому разделу.");
      const br = await fetchBoards({ limit: 100, offset: 0 });
      setBoards(br.items);
      await loadTasks();
    } catch (e) {
      setSettingsMsg(e instanceof ApiError ? e.message : "Не удалось создать доску");
    } finally {
      setCreatingBoard(false);
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
              Ниже выберите существующую доску Kanban или нажмите «Создать доску» — UUID вручную больше не нужен.
              Рекомендуется указать шаблон задачи, в workflow которого есть статусы:{" "}
              <code className="rounded bg-white/60 px-1">new</code>,{" "}
              <code className="rounded bg-white/60 px-1">dispatched</code>,{" "}
              <code className="rounded bg-white/60 px-1">in_progress</code>,{" "}
              <code className="rounded bg-white/60 px-1">testing</code>,{" "}
              <code className="rounded bg-white/60 px-1">done</code> — тогда перетаскивание между колонками будет
              согласовано с проверками на сервере.
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

      {canConfigure && (
        <div className="card space-y-4 p-4">
          <h2 className="text-sm font-semibold text-surface-800">Настройки доски (компания)</h2>
          <p className="text-xs text-surface-500">
            Доска и шаблон по умолчанию хранятся в настройках компании. Шаблон по умолчанию лишь подставляется в форме
            создания — исполнитель может выбрать другой шаблон из списка. Ограничить список шаблонов для выезда можно
            блоком ниже (пустой выбор = все шаблоны компании). Для согласованных переходов по колонкам задайте
            workflow со статусами new → dispatched → in_progress → testing → done.
          </p>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={creatingBoard || settingsSaving}
              onClick={() => void quickCreateFieldWorkBoard()}
              className="btn-primary inline-flex items-center gap-2 text-sm"
            >
              <Sparkles className="h-4 w-4" />
              {creatingBoard ? "Создание…" : "Создать доску «Выездные работы»"}
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-xs font-medium text-surface-600">
              Доска Kanban
              <select
                className="input mt-1 w-full text-sm"
                value={settingsBoardDraft}
                disabled={refsLoading}
                onChange={(e) => setSettingsBoardDraft(e.target.value)}
              >
                <option value="">— не выбрана —</option>
                {boards.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs font-medium text-surface-600">
              Шаблон по умолчанию (необязательно)
              <select
                className="input mt-1 w-full text-sm"
                value={settingsTemplateDraft}
                disabled={refsLoading}
                onChange={(e) => setSettingsTemplateDraft(e.target.value)}
              >
                <option value="">— без шаблона по умолчанию —</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs font-medium text-surface-600 sm:col-span-2">
              Шаблоны для выезда (необязательно)
              <span className="mt-0.5 block font-normal text-surface-500">
                Удерживайте Ctrl (Cmd на Mac) для нескольких. Пусто — в модалке создания задачи доступны все шаблоны
                компании.
              </span>
              <select
                multiple
                size={Math.min(10, Math.max(4, templates.length || 4))}
                className="input mt-1 w-full text-sm"
                value={fieldWorkTemplateIds}
                disabled={refsLoading}
                onChange={(e) =>
                  setFieldWorkTemplateIds(
                    Array.from(e.target.selectedOptions, (o) => o.value).filter(Boolean),
                  )
                }
              >
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {settingsMsg && <p className="text-xs text-surface-600">{settingsMsg}</p>}
          <button
            type="button"
            disabled={settingsSaving}
            onClick={() => void saveWorkspaceSettings()}
            className="btn-secondary inline-flex items-center gap-2 text-sm"
          >
            <Save className="h-4 w-4" />
            {settingsSaving ? "Сохранение…" : "Сохранить настройки"}
          </button>
        </div>
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

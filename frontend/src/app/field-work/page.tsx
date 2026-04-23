"use client";

/**
 * Field / crew task board: tasks on a dedicated Kanban board, isolated from office ``/tasks``.
 * Workers are not CRM users — register crews as equipment with ``hourly_rate`` (category e.g. ``crew``).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { HardHat, Plus, Save } from "lucide-react";
import { KanbanBoard, type KanbanCard, type KanbanColumn } from "@/components/boards/KanbanBoard";
import { CreateTaskModal } from "@/components/tasks/CreateTaskModal";
import {
  ApiError,
  fetchActiveCompany,
  fetchTasks,
  patchCompanyWorkspaceSettings,
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
  const [settingsBoardDraft, setSettingsBoardDraft] = useState("");
  const [settingsTemplateDraft, setSettingsTemplateDraft] = useState("");
  const [settingsMsg, setSettingsMsg] = useState<string | null>(null);
  const [settingsSaving, setSettingsSaving] = useState(false);

  const refreshCompany = useCallback(async () => {
    const c = await fetchActiveCompany();
    const bid = c.field_work_board_id?.trim() || null;
    const tid = c.default_field_task_template_id?.trim() || null;
    setBoardId(bid);
    setDefaultTemplateId(tid);
    setSettingsBoardDraft(bid ?? "");
    setSettingsTemplateDraft(tid ?? "");
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
          id: task.id,
          title: task.title,
          subtitle: task.assignee?.full_name ?? undefined,
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
      });
      setSettingsMsg("Сохранено");
      await loadTasks();
    } catch (e) {
      setSettingsMsg(e instanceof ApiError ? e.message : "Не удалось сохранить");
    } finally {
      setSettingsSaving(false);
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

      {!boardId && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Доска не настроена</p>
          <p className="mt-1">
            Создайте доску в компании (через API{" "}
            <code className="rounded bg-white/60 px-1">POST /boards</code>) и укажите её UUID ниже вместе с UUID
            шаблона задачи по умолчанию для этого канбана.
          </p>
        </div>
      )}

      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{loadError}</div>
      )}

      {boardId && (
        <>
          {loading && <p className="text-sm text-surface-500">Загрузка…</p>}
          <KanbanBoard
          columns={columns}
          cards={cards}
          onCardMove={handleCardMove}
          onCardClick={(id) => router.push(`/tasks/${id}`)}
          />
        </>
      )}

      {canConfigure && (
        <div className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold text-surface-800">Настройки доски (компания)</h2>
          <p className="text-xs text-surface-500">
            UUID доски Kanban для выездных задач и UUID шаблона, который подставляется при создании задачи на этой
            странице.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-xs font-medium text-surface-600">
              ID доски (board_id)
              <input
                className="input mt-1 w-full font-mono text-sm"
                value={settingsBoardDraft}
                onChange={(e) => setSettingsBoardDraft(e.target.value)}
                placeholder="uuid…"
              />
            </label>
            <label className="block text-xs font-medium text-surface-600">
              ID шаблона по умолчанию
              <input
                className="input mt-1 w-full font-mono text-sm"
                value={settingsTemplateDraft}
                onChange={(e) => setSettingsTemplateDraft(e.target.value)}
                placeholder="uuid…"
              />
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
        onClose={() => setCreateOpen(false)}
        variant="field_work"
        fixedBoardId={boardId ?? undefined}
        defaultTemplateId={defaultTemplateId ?? undefined}
        lockTemplate={Boolean(defaultTemplateId?.trim())}
        onCreated={() => {
          void loadTasks();
        }}
      />
    </div>
  );
}

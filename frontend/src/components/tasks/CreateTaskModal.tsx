"use client";

import { useState, useEffect, useCallback, useMemo, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { cn } from "@/lib/utils";
import { createTask, fetchEquipment, fetchTemplates, fetchUsers, type UserListItem } from "@/lib/api";
import { ClientSearchSelect } from "@/components/clients/ClientSearchSelect";
import type { EquipmentResponse, TemplateResponse, TaskResponse } from "@/types";

const NEW_CLIENT_VALUE = "__new_client__";

interface CreateTaskInitialValues {
  assignedTo?: string;
  startedAt?: string;  // datetime-local: YYYY-MM-DDTHH:mm
  dueDate?: string;    // datetime-local: YYYY-MM-DDTHH:mm
}

export type CreateTaskModalVariant = "default" | "field_work";

interface CreateTaskModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (task: TaskResponse) => void;
  initialValues?: CreateTaskInitialValues;
  /** Office vs field-work board UX (field: simpler form, default template). */
  variant?: CreateTaskModalVariant;
  /** Pre-select template when modal opens (e.g. company default for field board). */
  defaultTemplateId?: string;
  /** Always sent on create — isolates tasks to the field-work Kanban board. */
  fixedBoardId?: string;
  /** When true, template cannot be changed (default template locked). */
  lockTemplate?: boolean;
  /**
   * For field-work: if non-empty, only these template UUIDs appear in the template dropdown;
   * omit or null/empty → all company templates.
   */
  fieldWorkTemplateAllowlist?: string[] | null;
}

/**
 * Modal dialog for creating a new task (ad-hoc or from template).
 *
 * Модальное окно создания задачи. Позволяет выбрать шаблон,
 * клиента, исполнителя, заполнить основные поля и создать задачу.
 *
 * Args:
 *     open: Открыт ли модал.
 *     onClose: Callback закрытия.
 *     onCreated: Callback после успешного создания задачи.
 */
export function CreateTaskModal({
  open,
  onClose,
  onCreated,
  initialValues,
  variant = "default",
  defaultTemplateId,
  fixedBoardId,
  lockTemplate = false,
  fieldWorkTemplateAllowlist = null,
}: CreateTaskModalProps) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [templateId, setTemplateId] = useState("");
  const [clientId, setClientId] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [coAssigneeIds, setCoAssigneeIds] = useState<string[]>([]);
  const [observerIds, setObserverIds] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [templates, setTemplates] = useState<TemplateResponse[]>([]);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [equipment, setEquipment] = useState<EquipmentResponse[]>([]);
  const [workerEquipmentId, setWorkerEquipmentId] = useState("");
  const [loadingRefs, setLoadingRefs] = useState(false);

  const visibleTemplates = useMemo(() => {
    const allow = fieldWorkTemplateAllowlist?.filter((x) => x?.trim()) ?? [];
    if (allow.length === 0) return templates;
    const allowSet = new Set(allow);
    return templates.filter((t) => allowSet.has(t.id));
  }, [templates, fieldWorkTemplateAllowlist]);

  const loadReferences = useCallback(async () => {
    setLoadingRefs(true);
    setError(null);
    try {
      const [tmplRes, usersRes, equipmentRes] = await Promise.allSettled([
        fetchTemplates({ limit: 100 }),
        fetchUsers({ is_active: true, limit: 100 }),
        fetchEquipment({ limit: 200, status: "active" }),
      ]);

      const warnings: string[] = [];

      if (tmplRes.status === "fulfilled") {
        setTemplates(tmplRes.value.items);
      } else {
        setTemplates([]);
        warnings.push("шаблоны");
      }

      if (usersRes.status === "fulfilled") {
        setUsers(usersRes.value.items);
      } else {
        setUsers([]);
        warnings.push("пользователи");
      }

      if (equipmentRes.status === "fulfilled") {
        setEquipment(equipmentRes.value.items);
      } else {
        setEquipment([]);
        warnings.push("оборудование");
      }

      if (warnings.length > 0) {
        setError(`Часть справочников не загрузилась: ${warnings.join(", ")}. Можно продолжить создание задачи.`);
      }
    } catch (e) {
      setUsers([]);
      setTemplates([]);
      setEquipment([]);
      setError(
        e instanceof Error
          ? `Не удалось загрузить справочники (шаблоны, пользователи): ${e.message}. Убедитесь, что запросы идут на тот же хост и порт, что и страница (например :9000 → /api/v1 через Next.js), и что backend/nginx доступны.`
          : "Не удалось загрузить справочники",
      );
    } finally {
      setLoadingRefs(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      loadReferences();
      setTitle("");
      setDescription("");
      setPriority("medium");
      setTemplateId(defaultTemplateId?.trim() ? defaultTemplateId.trim() : "");
      setClientId("");
      setAssignedTo(initialValues?.assignedTo ?? "");
      setWorkerEquipmentId("");
      setCoAssigneeIds([]);
      setObserverIds([]);
      setStartedAt(initialValues?.startedAt ?? "");
      setDueDate(initialValues?.dueDate ?? "");
      setError(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, loadReferences, defaultTemplateId]);

  useEffect(() => {
    if (!open) return;
    if (!templateId) return;
    if (visibleTemplates.some((t) => t.id === templateId)) return;
    setTemplateId("");
  }, [open, templateId, visibleTemplates]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setError("Заполните название задачи");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        title: title.trim(),
        description: description.trim() || null,
        priority,
        visibility: "participants",
      };
      if (templateId) payload.template_id = templateId;
      if (fixedBoardId?.trim()) payload.board_id = fixedBoardId.trim();
      if (clientId) payload.client_id = clientId;
      if (assignedTo) payload.assigned_to = assignedTo;
      if (coAssigneeIds.length > 0) payload.co_assignee_ids = coAssigneeIds;
      if (observerIds.length > 0) payload.observer_ids = observerIds;
      if (startedAt) payload.started_at = new Date(startedAt).toISOString();
      if (dueDate) payload.due_date = new Date(dueDate).toISOString();
      if (variant === "field_work") {
        const selectedWorker = equipment.find((item) => item.id === workerEquipmentId);
        const existingCustomFields = (payload.custom_fields as Record<string, unknown> | undefined) ?? {};
        payload.custom_fields = {
          ...existingCustomFields,
          worker_equipment_id: workerEquipmentId || null,
          worker_equipment_name: selectedWorker?.name ?? null,
        };
      }

      const created = await createTask(payload);
      onCreated(created);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать задачу");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={variant === "field_work" ? "Новая задача (выезд)" : "Новая задача"}
      className="sm:max-w-xl"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="btn-ghost"
          >
            Отмена
          </button>
          <button
            type="submit"
            form="create-task-form"
            disabled={submitting || !title.trim()}
            className="btn-primary gap-1.5"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Создать
          </button>
        </>
      }
    >
      <form id="create-task-form" onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        <div>
          <label htmlFor="task-title" className="mb-1 block text-sm font-medium text-surface-700">
            Название <span className="text-red-500">*</span>
          </label>
          <input
            id="task-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="input"
            placeholder="Краткое описание задачи"
            autoFocus
          />
        </div>

        <div>
          <label htmlFor="task-desc" className="mb-1 block text-sm font-medium text-surface-700">
            Описание
          </label>
          <textarea
            id="task-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input min-h-[80px] resize-y"
            placeholder="Детальное описание (необязательно)"
            rows={3}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="task-priority" className="mb-1 block text-sm font-medium text-surface-700">
              Приоритет
            </label>
            <select
              id="task-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="input"
            >
              <option value="low">Низкий</option>
              <option value="medium">Средний</option>
              <option value="high">Высокий</option>
              <option value="critical">Критический</option>
            </select>
          </div>

          <div>
            <label htmlFor="task-started" className="mb-1 block text-sm font-medium text-surface-700">
              Начало
            </label>
            <input
              id="task-started"
              type="datetime-local"
              value={startedAt}
              onChange={(e) => setStartedAt(e.target.value)}
              className="input"
            />
          </div>
        </div>

        <div>
          <label htmlFor="task-due" className="mb-1 block text-sm font-medium text-surface-700">
            Срок выполнения
          </label>
          <input
            id="task-due"
            type="datetime-local"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="input"
          />
        </div>

        <div className={cn("grid gap-4", variant === "field_work" ? "grid-cols-1" : "grid-cols-2")}>
          <div>
            <label htmlFor="task-template" className="mb-1 block text-sm font-medium text-surface-700">
              Шаблон
            </label>
            <select
              id="task-template"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="input"
              disabled={loadingRefs || lockTemplate}
            >
              <option value="">Без шаблона</option>
              {visibleTemplates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          <ClientSearchSelect
            label="Клиент"
            selectId="task-client"
            value={clientId}
            onChange={(id) => setClientId(id)}
            disabled={loadingRefs}
            newOptionValue={NEW_CLIENT_VALUE}
            newOptionLabel="+ Создать клиента…"
            onPickCreateNew={() => {
              onClose();
              router.push("/clients?create=1");
            }}
          />
        </div>

        {variant === "field_work" ? (
          <div>
            <label htmlFor="task-worker-equipment" className="mb-1 block text-sm font-medium text-surface-700">
              Рабочие (оборудование)
            </label>
            <select
              id="task-worker-equipment"
              value={workerEquipmentId}
              onChange={(e) => setWorkerEquipmentId(e.target.value)}
              className="input"
              disabled={loadingRefs}
            >
              <option value="">Не выбраны</option>
              {equipment.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                  {item.hourly_rate ? ` · ${item.hourly_rate}/ч` : ""}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div>
            <label htmlFor="task-assignee" className="mb-1 block text-sm font-medium text-surface-700">
              Исполнитель
            </label>
            <select
              id="task-assignee"
              value={assignedTo}
              onChange={(e) => setAssignedTo(e.target.value)}
              className="input"
              disabled={loadingRefs}
            >
              <option value="">Не назначен</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>
              ))}
            </select>
          </div>
        )}

        {variant !== "field_work" && (
        <div>
          <span className="mb-1 block text-sm font-medium text-surface-700">Соисполнители</span>
          <div className="max-h-36 space-y-1.5 overflow-y-auto rounded-lg border border-surface-200 p-2">
            {users.length === 0 ? (
              <p className="text-xs text-surface-400">Нет пользователей</p>
            ) : (
              users.map((u) => (
                <label key={u.id} className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={coAssigneeIds.includes(u.id)}
                    onChange={() =>
                      setCoAssigneeIds((prev) =>
                        prev.includes(u.id) ? prev.filter((id) => id !== u.id) : [...prev, u.id],
                      )
                    }
                    disabled={loadingRefs}
                    className="rounded border-surface-300"
                  />
                  <span>{u.full_name}</span>
                </label>
              ))
            )}
          </div>
        </div>
        )}

        {variant !== "field_work" && (
        <div>
          <span className="mb-1 block text-sm font-medium text-surface-700">Наблюдатели</span>
          <div className="max-h-36 space-y-1.5 overflow-y-auto rounded-lg border border-surface-200 p-2">
            {users.length === 0 ? (
              <p className="text-xs text-surface-400">Нет пользователей</p>
            ) : (
              users.map((u) => (
                <label key={u.id} className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={observerIds.includes(u.id)}
                    onChange={() =>
                      setObserverIds((prev) =>
                        prev.includes(u.id) ? prev.filter((id) => id !== u.id) : [...prev, u.id],
                      )
                    }
                    disabled={loadingRefs}
                    className="rounded border-surface-300"
                  />
                  <span>{u.full_name}</span>
                </label>
              ))
            )}
          </div>
        </div>
        )}
      </form>
    </Modal>
  );
}

export default CreateTaskModal;

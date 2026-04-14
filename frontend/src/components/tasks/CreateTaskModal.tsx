"use client";

import { useState, useEffect, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { createTask, fetchTemplates, fetchClients, fetchUsers, type UserListItem } from "@/lib/api";
import type { TemplateResponse, ClientResponse, TaskResponse } from "@/types";

const NEW_CLIENT_VALUE = "__new_client__";

interface CreateTaskInitialValues {
  assignedTo?: string;
  startedAt?: string;  // datetime-local: YYYY-MM-DDTHH:mm
  dueDate?: string;    // datetime-local: YYYY-MM-DDTHH:mm
}

interface CreateTaskModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (task: TaskResponse) => void;
  initialValues?: CreateTaskInitialValues;
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
export function CreateTaskModal({ open, onClose, onCreated, initialValues }: CreateTaskModalProps) {
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
  const [clients, setClients] = useState<ClientResponse[]>([]);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [loadingRefs, setLoadingRefs] = useState(false);

  const loadReferences = useCallback(async () => {
    setLoadingRefs(true);
    setError(null);
    try {
      const [tmplRes, clientRes, usersRes] = await Promise.all([
        fetchTemplates({ limit: 100 }),
        fetchClients({ limit: 200 }),
        fetchUsers({ is_active: true, limit: 100 }),
      ]);
      setTemplates(tmplRes.items);
      setClients(clientRes.items);
      setUsers(usersRes.items);
    } catch (e) {
      setUsers([]);
      setTemplates([]);
      setClients([]);
      setError(
        e instanceof Error
          ? `Не удалось загрузить справочники (шаблоны, клиенты, пользователи): ${e.message}. Убедитесь, что запросы идут на тот же хост и порт, что и страница (например :9000 → /api/v1 через Next.js), и что backend/nginx доступны.`
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
      setTemplateId("");
      setClientId("");
      setAssignedTo(initialValues?.assignedTo ?? "");
      setCoAssigneeIds([]);
      setObserverIds([]);
      setStartedAt(initialValues?.startedAt ?? "");
      setDueDate(initialValues?.dueDate ?? "");
      setError(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, loadReferences]);

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
      if (clientId) payload.client_id = clientId;
      if (assignedTo) payload.assigned_to = assignedTo;
      if (coAssigneeIds.length > 0) payload.co_assignee_ids = coAssigneeIds;
      if (observerIds.length > 0) payload.observer_ids = observerIds;
      if (startedAt) payload.started_at = new Date(startedAt).toISOString();
      if (dueDate) payload.due_date = new Date(dueDate).toISOString();

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
      title="Новая задача"
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

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="task-template" className="mb-1 block text-sm font-medium text-surface-700">
              Шаблон
            </label>
            <select
              id="task-template"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="input"
              disabled={loadingRefs}
            >
              <option value="">Без шаблона</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="task-client" className="mb-1 block text-sm font-medium text-surface-700">
              Клиент
            </label>
            <select
              id="task-client"
              value={clientId}
              onChange={(e) => {
                const v = e.target.value;
                if (v === NEW_CLIENT_VALUE) {
                  onClose();
                  router.push("/clients?create=1");
                  return;
                }
                setClientId(v);
              }}
              className="input"
              disabled={loadingRefs}
            >
              <option value="">Не выбран</option>
              <option value={NEW_CLIENT_VALUE}>+ Создать клиента…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
        </div>

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
      </form>
    </Modal>
  );
}

export default CreateTaskModal;

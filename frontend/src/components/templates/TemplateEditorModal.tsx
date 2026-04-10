"use client";

import { useState, useEffect, type FormEvent } from "react";
import { Loader2, Plus, Trash2, GripVertical } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { createTemplate, updateTemplate } from "@/lib/api";
import type { TemplateResponse } from "@/types";

interface TemplateEditorModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: (tpl: TemplateResponse) => void;
  template?: TemplateResponse | null;
}

interface ChecklistDraft {
  title: string;
  gate_transition: string;
  items: string[];
}

const CATEGORIES = [
  { value: "installation", label: "Монтаж" },
  { value: "maintenance", label: "Обслуживание" },
  { value: "repair", label: "Ремонт" },
  { value: "inspection", label: "Осмотр" },
  { value: "general", label: "Общее" },
];

const DEFAULT_WORKFLOW = {
  initial_state: "new",
  states: ["new", "dispatched", "in_progress", "testing", "act_signing", "done"],
  transitions: [
    { from: "new", to: "dispatched" },
    { from: "dispatched", to: "in_progress" },
    { from: "in_progress", to: "testing" },
    { from: "testing", to: "act_signing" },
    { from: "testing", to: "in_progress" },
    { from: "act_signing", to: "done" },
    { from: "act_signing", to: "testing" },
  ],
};

/**
 * Modal for creating / editing task templates.
 *
 * Модальное окно для создания и редактирования шаблонов задач.
 * Включает настройку категории, описания, чек-листов с gate-переходами
 * и определение workflow.
 *
 * Args:
 *     open: Открыт ли модал.
 *     onClose: Callback закрытия.
 *     onSaved: Callback после сохранения.
 *     template: Шаблон для редактирования (null для создания нового).
 */
export function TemplateEditorModal({ open, onClose, onSaved, template }: TemplateEditorModalProps) {
  const isEdit = !!template;

  const [name, setName] = useState("");
  const [category, setCategory] = useState("general");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [checklists, setChecklists] = useState<ChecklistDraft[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (template) {
      setName(template.name);
      setCategory(template.category);
      setDescription(template.description ?? "");
      setIsActive(template.is_active);
      setChecklists(
        template.checklists.map((cl) => ({
          title: cl.title,
          gate_transition: cl.gate_transition ?? "",
          items: (cl.items as Array<string | { title: string }>).map((i) =>
            typeof i === "string" ? i : i.title
          ),
        })),
      );
    } else {
      setName("");
      setCategory("general");
      setDescription("");
      setIsActive(true);
      setChecklists([]);
    }
    setError(null);
  }, [open, template]);

  function addChecklist() {
    setChecklists((prev) => [...prev, { title: "", gate_transition: "", items: [""] }]);
  }

  function removeChecklist(idx: number) {
    setChecklists((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateChecklist(idx: number, field: keyof ChecklistDraft, value: string) {
    setChecklists((prev) =>
      prev.map((cl, i) => (i === idx ? { ...cl, [field]: value } : cl)),
    );
  }

  function addChecklistItem(clIdx: number) {
    setChecklists((prev) =>
      prev.map((cl, i) => (i === clIdx ? { ...cl, items: [...cl.items, ""] } : cl)),
    );
  }

  function removeChecklistItem(clIdx: number, itemIdx: number) {
    setChecklists((prev) =>
      prev.map((cl, i) =>
        i === clIdx ? { ...cl, items: cl.items.filter((_, j) => j !== itemIdx) } : cl,
      ),
    );
  }

  function updateChecklistItem(clIdx: number, itemIdx: number, value: string) {
    setChecklists((prev) =>
      prev.map((cl, i) =>
        i === clIdx
          ? { ...cl, items: cl.items.map((item, j) => (j === itemIdx ? value : item)) }
          : cl,
      ),
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Заполните название шаблона");
      return;
    }
    setSubmitting(true);
    setError(null);

    const payload: Record<string, unknown> = {
      name: name.trim(),
      category,
      description: description.trim() || null,
      is_active: isActive,
      workflow_definition: DEFAULT_WORKFLOW,
      checklists: checklists.map((cl) => ({
        title: cl.title || "Чек-лист",
        gate_transition: cl.gate_transition || null,
        items: cl.items.filter((s) => s.trim() !== ""),
      })),
    };

    try {
      let saved: TemplateResponse;
      if (isEdit && template) {
        saved = await updateTemplate(template.id, payload);
      } else {
        saved = await createTemplate(payload);
      }
      onSaved(saved);
      onClose();
    } catch (err) {
      if (err instanceof TypeError && err.message === "Failed to fetch") {
        setError(
          "Нет связи с API (Failed to fetch). Убедитесь, что backend запущен. " +
            "Если фронт через Next.js: оставьте NEXT_PUBLIC_API_URL пустым и задайте BACKEND_INTERNAL_URL " +
            "(в Docker: http://backend:8000), затем перезапустите Next.js.",
        );
      } else {
        setError(err instanceof Error ? err.message : "Не удалось сохранить шаблон");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "Редактировать шаблон" : "Новый шаблон"}
      className="sm:max-w-2xl"
      footer={
        <>
          <button type="button" onClick={onClose} disabled={submitting} className="btn-ghost">
            Отмена
          </button>
          <button
            type="submit"
            form="template-editor-form"
            disabled={submitting || !name.trim()}
            className="btn-primary gap-1.5"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {isEdit ? "Сохранить" : "Создать"}
          </button>
        </>
      }
    >
      <form id="template-editor-form" onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        {/* Basic Info */}
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label htmlFor="tpl-name" className="mb-1 block text-sm font-medium text-surface-700">
              Название <span className="text-red-500">*</span>
            </label>
            <input
              id="tpl-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
              placeholder="Название шаблона"
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="tpl-category" className="mb-1 block text-sm font-medium text-surface-700">
              Категория
            </label>
            <select
              id="tpl-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="input"
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm font-medium text-surface-700">Активен</span>
            </label>
          </div>
        </div>

        <div>
          <label htmlFor="tpl-desc" className="mb-1 block text-sm font-medium text-surface-700">
            Описание
          </label>
          <textarea
            id="tpl-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input min-h-[60px] resize-y"
            placeholder="Описание шаблона (необязательно)"
            rows={2}
          />
        </div>

        {/* Checklists */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-surface-700">Чек-листы</h3>
            <button type="button" onClick={addChecklist} className="btn-ghost btn-sm gap-1 text-primary-600">
              <Plus className="h-3.5 w-3.5" /> Добавить чек-лист
            </button>
          </div>

          {checklists.length === 0 && (
            <p className="rounded-lg bg-surface-50 p-4 text-sm text-surface-400 text-center">
              Чек-листы не добавлены
            </p>
          )}

          <div className="space-y-4">
            {checklists.map((cl, clIdx) => (
              <div key={clIdx} className="rounded-lg border border-surface-200 p-3 space-y-3">
                <div className="flex items-start gap-2">
                  <GripVertical className="h-4 w-4 mt-2 text-surface-300 shrink-0" />
                  <div className="flex-1 grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={cl.title}
                      onChange={(e) => updateChecklist(clIdx, "title", e.target.value)}
                      className="input"
                      placeholder="Название чек-листа"
                    />
                    <input
                      type="text"
                      value={cl.gate_transition}
                      onChange={(e) => updateChecklist(clIdx, "gate_transition", e.target.value)}
                      className="input"
                      placeholder="Gate: in_progress->testing"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => removeChecklist(clIdx)}
                    className="rounded p-1 text-surface-300 hover:text-red-500 hover:bg-red-50 mt-1"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <div className="pl-6 space-y-1.5">
                  {cl.items.map((item, itemIdx) => (
                    <div key={itemIdx} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        disabled
                        className="h-3.5 w-3.5 rounded border-surface-300"
                      />
                      <input
                        type="text"
                        value={item}
                        onChange={(e) => updateChecklistItem(clIdx, itemIdx, e.target.value)}
                        className="input flex-1"
                        placeholder="Пункт чек-листа"
                      />
                      <button
                        type="button"
                        onClick={() => removeChecklistItem(clIdx, itemIdx)}
                        className="rounded p-0.5 text-surface-300 hover:text-red-500"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => addChecklistItem(clIdx)}
                    className="text-xs text-primary-600 hover:underline ml-5"
                  >
                    + Добавить пункт
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </form>
    </Modal>
  );
}

export default TemplateEditorModal;

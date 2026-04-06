"use client";

import { useEffect, useState, useCallback } from "react";
import {
  FileStack,
  Plus,
  CheckSquare,
  Layers,
  Zap,
  Pencil,
  Trash2,
  Loader2,
} from "lucide-react";
import { fetchTemplates, deleteTemplate } from "@/lib/api";
import type { TemplateResponse } from "@/types";
import { TemplateEditorModal } from "@/components/templates/TemplateEditorModal";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

const categoryConfig: Record<string, { label: string; classes: string }> = {
  installation: { label: "Монтаж", classes: "bg-blue-50 text-blue-700" },
  maintenance: { label: "Обслуживание", classes: "bg-green-50 text-green-700" },
  repair: { label: "Ремонт", classes: "bg-orange-50 text-orange-700" },
  inspection: { label: "Осмотр", classes: "bg-violet-50 text-violet-700" },
  general: { label: "Общее", classes: "bg-surface-100 text-surface-600" },
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<TemplateResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<TemplateResponse | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchTemplates({
        category: categoryFilter || undefined,
        limit: 50,
      });
      setTemplates(res.items);
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, [categoryFilter]);

  useEffect(() => { load(); }, [load]);

  function handleCreate() {
    setEditingTemplate(null);
    setEditorOpen(true);
  }

  function handleEdit(tpl: TemplateResponse) {
    setEditingTemplate(tpl);
    setEditorOpen(true);
  }

  async function handleDelete(tpl: TemplateResponse) {
    if (!confirm(`Удалить шаблон "${tpl.name}"? Это действие нельзя отменить.`)) return;
    setDeletingId(tpl.id);
    try {
      await deleteTemplate(tpl.id);
      setTemplates((prev) => prev.filter((t) => t.id !== tpl.id));
    } catch {
      /* silent */
    } finally {
      setDeletingId(null);
    }
  }

  function handleSaved(saved: TemplateResponse) {
    setTemplates((prev) => {
      const existing = prev.findIndex((t) => t.id === saved.id);
      if (existing >= 0) {
        const copy = [...prev];
        copy[existing] = saved;
        return copy;
      }
      return [saved, ...prev];
    });
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Шаблоны</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Шаблоны</h1>
        <button onClick={handleCreate} className="btn-primary gap-1.5">
          <Plus className="h-4 w-4" /> Создать шаблон
        </button>
      </div>

      {/* Category Filter */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setCategoryFilter("")}
          className={`badge cursor-pointer transition-colors ${
            !categoryFilter ? "bg-primary-600 text-white" : "bg-surface-100 text-surface-600 hover:bg-surface-200"
          }`}
        >
          Все
        </button>
        {Object.entries(categoryConfig).map(([key, cfg]) => (
          <button
            key={key}
            onClick={() => setCategoryFilter(key)}
            className={`badge cursor-pointer transition-colors ${
              categoryFilter === key ? "bg-primary-600 text-white" : `${cfg.classes} hover:opacity-80`
            }`}
          >
            {cfg.label}
          </button>
        ))}
      </div>

      {/* Templates Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {templates.map((tpl) => {
          const cat = categoryConfig[tpl.category] ?? categoryConfig.general;
          const stagesCount = tpl.stages?.length ?? 0;
          const checklistsCount = tpl.checklists?.length ?? 0;

          return (
            <div
              key={tpl.id}
              className="card p-4 hover:border-primary-200 transition-colors group"
            >
              <div className="flex items-start justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600 group-hover:bg-primary-100 transition-colors">
                  <FileStack className="h-5 w-5" />
                </div>
                <div className="flex items-center gap-2">
                  <span className={`badge ${cat.classes}`}>{cat.label}</span>
                  {!tpl.is_active && (
                    <span className="badge bg-surface-100 text-surface-400">Неактивен</span>
                  )}
                </div>
              </div>

              <h3 className="mt-3 font-semibold">{tpl.name}</h3>
              {tpl.description && (
                <p className="mt-1 text-sm text-surface-500 line-clamp-2">{tpl.description}</p>
              )}

              <div className="mt-3 flex items-center gap-4 text-xs text-surface-500">
                <span className="flex items-center gap-1">
                  <Layers className="h-3.5 w-3.5" /> {stagesCount} этапов
                </span>
                <span className="flex items-center gap-1">
                  <CheckSquare className="h-3.5 w-3.5" /> {checklistsCount} чек-листов
                </span>
                {tpl.fields && tpl.fields.length > 0 && (
                  <span className="flex items-center gap-1">
                    <Zap className="h-3.5 w-3.5" /> {tpl.fields.length} полей
                  </span>
                )}
              </div>

              {/* Action buttons */}
              <div className="mt-3 flex items-center gap-2 pt-3 border-t border-surface-100">
                <button
                  onClick={() => handleEdit(tpl)}
                  className="btn-ghost btn-sm gap-1 text-surface-500"
                >
                  <Pencil className="h-3.5 w-3.5" /> Редактировать
                </button>
                <button
                  onClick={() => handleDelete(tpl)}
                  disabled={deletingId === tpl.id}
                  className="btn-ghost btn-sm gap-1 text-red-500 hover:bg-red-50"
                >
                  {deletingId === tpl.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                  Удалить
                </button>
              </div>
            </div>
          );
        })}
        {templates.length === 0 && (
          <div className="col-span-full py-16 text-center text-surface-400">
            <FileStack className="mx-auto h-10 w-10 mb-3" />
            <p className="font-medium">Шаблоны не найдены</p>
            <p className="mt-1 text-sm">Создайте первый шаблон задачи, чтобы начать работу</p>
          </div>
        )}
      </div>

      {/* Template Editor Modal */}
      <TemplateEditorModal
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        onSaved={handleSaved}
        template={editingTemplate}
      />
    </div>
  );
}

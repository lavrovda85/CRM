"use client";

import { useEffect, useState, useCallback } from "react";
import {
  DollarSign,
  Calendar,
  User,
  GripVertical,
  Plus,
} from "lucide-react";
import { fetchDeals, fetchDealStages, updateDeal } from "@/lib/api";
import type { DealResponse, DealStageResponse } from "@/types";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function DealsPage() {
  const [stages, setStages] = useState<DealStageResponse[]>([]);
  const [deals, setDeals] = useState<DealResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [dragItem, setDragItem] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [stagesData, dealsData] = await Promise.all([
        fetchDealStages(),
        fetchDeals({ limit: 200 }),
      ]);
      setStages(stagesData.sort((a, b) => a.order - b.order));
      setDeals(dealsData.items);
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function handleDragStart(dealId: string) {
    setDragItem(dealId);
  }

  async function handleDrop(stageId: string) {
    if (!dragItem) return;
    const deal = deals.find((d) => d.id === dragItem);
    if (!deal || deal.stage_id === stageId) {
      setDragItem(null);
      return;
    }
    setDeals((prev) =>
      prev.map((d) => (d.id === dragItem ? { ...d, stage_id: stageId } : d)),
    );
    setDragItem(null);
    try {
      await updateDeal(dragItem, { stage_id: stageId });
    } catch {
      load();
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[100rem] space-y-4 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Воронка сделок</h1>
        <div className="flex gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-64 w-64 shrink-0 lg:flex-1" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[100rem] space-y-4 p-4 lg:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Воронка сделок</h1>
        <button className="btn-primary gap-1.5">
          <Plus className="h-4 w-4" /> Новая сделка
        </button>
      </div>

      {/* Pipeline Kanban */}
      <div className="flex gap-4 overflow-x-auto pb-4">
        {stages.map((stage) => {
          const stageDeals = deals.filter((d) => d.stage_id === stage.id);
          const totalAmount = stageDeals.reduce((s, d) => s + Number(d.amount), 0);

          return (
            <div
              key={stage.id}
              className="flex w-72 shrink-0 flex-col lg:w-auto lg:flex-1"
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => handleDrop(stage.id)}
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: stage.color }}
                  />
                  <h3 className="text-sm font-semibold text-surface-700">
                    {stage.name}
                  </h3>
                  <span className="badge bg-surface-100 text-surface-500">
                    {stageDeals.length}
                  </span>
                </div>
                <span className="text-xs font-medium text-surface-400">
                  ₽{totalAmount.toLocaleString("ru-RU")}
                </span>
              </div>

              <div className="flex-1 space-y-3 rounded-xl bg-surface-50 p-2 min-h-[200px]">
                {stageDeals.map((deal) => (
                  <div
                    key={deal.id}
                    draggable
                    onDragStart={() => handleDragStart(deal.id)}
                    className={`card cursor-grab p-3 active:cursor-grabbing hover:border-primary-200 transition-colors ${
                      dragItem === deal.id ? "opacity-50" : ""
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <GripVertical className="mt-0.5 h-4 w-4 shrink-0 text-surface-300" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium leading-snug">{deal.title}</p>
                        <div className="mt-2 space-y-1">
                          <div className="flex items-center gap-1.5 text-xs text-primary-600 font-semibold">
                            <DollarSign className="h-3 w-3" />
                            ₽{Number(deal.amount).toLocaleString("ru-RU")}
                          </div>
                          {deal.expected_close && (
                            <div className="flex items-center gap-1 text-[10px] text-surface-400">
                              <Calendar className="h-3 w-3" />
                              {new Date(deal.expected_close).toLocaleDateString("ru-RU")}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {stageDeals.length === 0 && (
                  <p className="py-8 text-center text-xs text-surface-300">
                    Нет сделок
                  </p>
                )}
              </div>
            </div>
          );
        })}

        {stages.length === 0 && (
          <div className="flex flex-1 items-center justify-center py-20 text-surface-400">
            Этапы воронки не настроены. Создайте этапы в Настройках.
          </div>
        )}
      </div>
    </div>
  );
}

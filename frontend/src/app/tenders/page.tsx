"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Filter,
  Plus,
  Calendar,
  DollarSign,
  Globe,
  X,
  ChevronDown,
} from "lucide-react";
import { fetchTenders } from "@/lib/api";
import type { TenderResponse, TenderStatus } from "@/types";

const COLUMNS: { key: TenderStatus; label: string; color: string }[] = [
  { key: "search", label: "Search", color: "bg-surface-400" },
  { key: "participation", label: "Participation", color: "bg-blue-500" },
  { key: "won", label: "Won", color: "bg-green-500" },
  { key: "execution", label: "Execution", color: "bg-amber-500" },
  { key: "completed", label: "Completed", color: "bg-emerald-600" },
  { key: "lost", label: "Lost", color: "bg-red-500" },
];

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function TendersPage() {
  const [tenders, setTenders] = useState<TenderResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchTenders({ ...filters, limit: 200 });
      setTenders(res.items);
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  function setFilter(key: string, value: string) {
    setFilters((prev) => {
      const next = { ...prev };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  }

  const grouped = COLUMNS.map((col) => ({
    ...col,
    tenders: tenders.filter((t) => t.status === col.key),
  }));

  if (loading) {
    return (
      <div className="mx-auto max-w-[100rem] space-y-4 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Tenders</h1>
        <div className="flex gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-64 w-56 shrink-0 lg:flex-1" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[100rem] space-y-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Tenders</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFiltersOpen((o) => !o)}
            className={`btn-ghost gap-1.5 ${filtersOpen ? "bg-surface-100" : ""}`}
          >
            <Filter className="h-4 w-4" /> Filters
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${filtersOpen ? "rotate-180" : ""}`} />
          </button>
          <button className="btn-primary gap-1.5">
            <Plus className="h-4 w-4" /> New Tender
          </button>
        </div>
      </div>

      {/* Filters */}
      {filtersOpen && (
        <div className="card flex flex-wrap items-center gap-3 p-3">
          <select
            className="input max-w-[160px]"
            value={filters.status ?? ""}
            onChange={(e) => setFilter("status", e.target.value)}
          >
            <option value="">All statuses</option>
            {COLUMNS.map((c) => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </select>
          {Object.keys(filters).length > 0 && (
            <button onClick={() => setFilters({})} className="btn-ghost btn-sm text-red-600 gap-1">
              <X className="h-3.5 w-3.5" /> Clear
            </button>
          )}
        </div>
      )}

      {/* Kanban */}
      <div className="flex gap-4 overflow-x-auto pb-4">
        {grouped.map((col) => (
          <div key={col.key} className="flex w-60 shrink-0 flex-col lg:w-auto lg:flex-1">
            <div className="mb-3 flex items-center gap-2">
              <div className={`h-2.5 w-2.5 rounded-full ${col.color}`} />
              <h3 className="text-sm font-semibold text-surface-700">{col.label}</h3>
              <span className="badge bg-surface-100 text-surface-500">{col.tenders.length}</span>
            </div>
            <div className="flex-1 space-y-3 rounded-xl bg-surface-50 p-2 min-h-[200px]">
              {col.tenders.map((tender) => (
                <div key={tender.id} className="card p-3 hover:border-primary-200 transition-colors">
                  <p className="text-sm font-medium leading-snug">{tender.title}</p>
                  <div className="mt-2 space-y-1.5">
                    {tender.budget != null && (
                      <div className="flex items-center gap-1 text-xs text-surface-600">
                        <DollarSign className="h-3 w-3 text-surface-400" />
                        Budget: ₽{Number(tender.budget).toLocaleString("ru-RU")}
                      </div>
                    )}
                    {tender.deadline && (
                      <div className="flex items-center gap-1 text-xs text-surface-600">
                        <Calendar className="h-3 w-3 text-surface-400" />
                        {new Date(tender.deadline).toLocaleDateString("ru-RU")}
                      </div>
                    )}
                    {tender.source && (
                      <div className="flex items-center gap-1 text-xs text-surface-400">
                        <Globe className="h-3 w-3" />
                        {tender.source}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {col.tenders.length === 0 && (
                <p className="py-8 text-center text-xs text-surface-300">No tenders</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

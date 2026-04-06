"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Play,
  Square,
  Clock,
  Plus,
  Calendar,
  FileText,
  Timer,
} from "lucide-react";
import { fetchTimeEntries, fetchTimeSummary, startTimer, stopTimer } from "@/lib/api";
import type { TimeEntryResponse, TimeSummary } from "@/types";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}h ${m}m`;
}

export default function TimePage() {
  const [entries, setEntries] = useState<TimeEntryResponse[]>([]);
  const [summary, setSummary] = useState<TimeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTimer, setActiveTimer] = useState<TimeEntryResponse | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [showManual, setShowManual] = useState(false);
  const [manualForm, setManualForm] = useState({ task_id: "", duration_minutes: "", notes: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [entriesData, summaryData] = await Promise.all([
        fetchTimeEntries({ limit: 20 }),
        fetchTimeSummary({}),
      ]);
      setEntries(entriesData.items);
      setSummary(summaryData);

      const running = entriesData.items.find(
        (e) => e.entry_type === "timer" && !e.ended_at,
      );
      if (running) {
        setActiveTimer(running);
        const startedMs = new Date(running.started_at!).getTime();
        setElapsed(Math.floor((Date.now() - startedMs) / 1000));
      }
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (activeTimer) {
      intervalRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [activeTimer]);

  async function handleStart() {
    if (!manualForm.task_id) return;
    try {
      const entry = await startTimer(manualForm.task_id);
      setActiveTimer(entry);
      setElapsed(0);
    } catch {
      /* silent */
    }
  }

  async function handleStop() {
    try {
      await stopTimer();
      setActiveTimer(null);
      setElapsed(0);
      if (intervalRef.current) clearInterval(intervalRef.current);
      load();
    } catch {
      /* silent */
    }
  }

  const hours = Math.floor(elapsed / 3600);
  const minutes = Math.floor((elapsed % 3600) / 60);
  const seconds = elapsed % 60;

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Учёт времени</h1>
        <Skeleton className="h-40" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 lg:p-6">
      <h1 className="text-2xl font-bold">Учёт времени</h1>

      {/* Active Timer */}
      <div className="card overflow-hidden">
        <div className={`p-6 text-center ${activeTimer ? "bg-primary-600 text-white" : "bg-surface-50"}`}>
          <div className="mb-2 flex items-center justify-center gap-2">
            <Timer className="h-5 w-5" />
            <span className="text-sm font-medium">
              {activeTimer ? "Таймер запущен" : "Нет активного таймера"}
            </span>
          </div>
          <div className="font-mono text-5xl font-bold tracking-wider lg:text-6xl">
            {String(hours).padStart(2, "0")}:{String(minutes).padStart(2, "0")}:
            {String(seconds).padStart(2, "0")}
          </div>
          <div className="mt-4 flex items-center justify-center gap-3">
            {activeTimer ? (
              <button onClick={handleStop} className="btn bg-white text-red-600 hover:bg-red-50 gap-1.5">
                <Square className="h-4 w-4" /> Остановить таймер
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="ID задачи..."
                  className="input max-w-xs bg-white"
                  value={manualForm.task_id}
                  onChange={(e) => setManualForm({ ...manualForm, task_id: e.target.value })}
                />
                <button
                  onClick={handleStart}
                  disabled={!manualForm.task_id}
                  className="btn-primary gap-1.5"
                >
                  <Play className="h-4 w-4" /> Запустить
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Week Summary */}
      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <div className="card p-4 text-center">
            <p className="text-sm text-surface-500">Всего часов</p>
            <p className="text-2xl font-bold">{summary.total_hours}</p>
          </div>
          <div className="card p-4 text-center">
            <p className="text-sm text-surface-500">Записи</p>
            <p className="text-2xl font-bold">{summary.entries_count}</p>
          </div>
          <div className="card p-4 text-center">
            <p className="text-sm text-surface-500">Среднее в день</p>
            <p className="text-2xl font-bold">
              {summary.entries_count > 0
                ? (summary.total_hours / Math.max(1, 7)).toFixed(1)
                : "0"}
            </p>
          </div>
        </div>
      )}

      {/* Today's Entries */}
      <div className="card">
        <div className="flex items-center justify-between border-b border-surface-100 p-4">
          <h2 className="font-semibold flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary-500" /> Последние записи
          </h2>
          <button onClick={() => setShowManual((o) => !o)} className="btn-ghost btn-sm gap-1">
            <Plus className="h-3.5 w-3.5" /> Ручной ввод
          </button>
        </div>

        {showManual && (
          <div className="border-b border-surface-100 bg-surface-50 p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <input
                type="text"
                placeholder="ID задачи"
                className="input"
                value={manualForm.task_id}
                onChange={(e) => setManualForm({ ...manualForm, task_id: e.target.value })}
              />
              <input
                type="number"
                placeholder="Длительность (мин)"
                className="input"
                value={manualForm.duration_minutes}
                onChange={(e) => setManualForm({ ...manualForm, duration_minutes: e.target.value })}
              />
              <input
                type="text"
                placeholder="Заметки"
                className="input"
                value={manualForm.notes}
                onChange={(e) => setManualForm({ ...manualForm, notes: e.target.value })}
              />
            </div>
            <button className="btn-primary mt-3 btn-sm">Сохранить запись</button>
          </div>
        )}

        <div className="divide-y divide-surface-50">
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between p-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className={`badge ${
                    entry.entry_type === "timer"
                      ? "bg-primary-50 text-primary-700"
                      : "bg-surface-100 text-surface-600"
                  }`}>
                    {entry.entry_type === "timer" ? (
                      <><Timer className="mr-1 h-3 w-3" /> таймер</>
                    ) : (
                      <><FileText className="mr-1 h-3 w-3" /> ручной</>
                    )}
                  </span>
                  {entry.is_billable && (
                    <span className="badge bg-green-50 text-green-700">оплачиваемый</span>
                  )}
                  {!entry.ended_at && (
                    <span className="badge bg-amber-50 text-amber-700 animate-pulse">в процессе</span>
                  )}
                </div>
                {entry.notes && (
                  <p className="mt-1 text-sm text-surface-500 truncate">{entry.notes}</p>
                )}
                <p className="mt-1 text-xs text-surface-400">
                  {entry.started_at && new Date(entry.started_at).toLocaleString("ru-RU")}
                </p>
              </div>
              <div className="text-right">
                <span className="text-sm font-semibold">
                  {formatDuration(entry.duration_minutes)}
                </span>
              </div>
            </div>
          ))}
          {entries.length === 0 && (
            <p className="p-8 text-center text-sm text-surface-400">Записей пока нет</p>
          )}
        </div>
      </div>
    </div>
  );
}

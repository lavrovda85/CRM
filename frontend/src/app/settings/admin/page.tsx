"use client";

import { useEffect, useState } from "react";
import { Shield, Save, Plus, Trash2, Play, ArrowUp, ArrowDown } from "lucide-react";
import {
  createAdminSchedulerRule,
  deleteAdminSchedulerRule,
  fetchAdminSettings,
  fetchAdminSchedulerRules,
  fetchDeployBranches,
  fetchDeployJobs,
  fetchDeployStatus,
  fetchProjectLogs,
  fetchUsers,
  runAdminSchedulerRuleNow,
  runDeploy,
  updateAdminSchedulerRule,
  updateAdminSchedulerSettings,
} from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

type Priority = "low" | "medium" | "high" | "critical";

export default function AdminSettingsPage() {
  const authUser = useAuthStore((s) => s.user);
  const isAdmin = authUser?.role === "admin";
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [tab, setTab] = useState<"rules" | "env" | "deploy" | "logs">("rules");
  const [deployStatus, setDeployStatus] = useState<{
    deploy_ui_enabled: boolean;
    agent_reachable: boolean | null;
    agent_error: string | null;
    github_repo_configured: boolean;
  } | null>(null);
  const [deployBranches, setDeployBranches] = useState<string[]>([]);
  const [deployBranch, setDeployBranch] = useState("");
  const [deployBusy, setDeployBusy] = useState(false);
  const [deployJobs, setDeployJobs] = useState<
    Array<{
      id: string;
      branch: string;
      status: string;
      log_excerpt: string | null;
      error_message: string | null;
      created_at: string;
    }>
  >([]);
  const [projectLogText, setProjectLogText] = useState("");
  const [logsBusy, setLogsBusy] = useState(false);
  const [logTail, setLogTail] = useState(400);
  const [envPreview, setEnvPreview] = useState<Record<string, string>>({});
  const [staff, setStaff] = useState<Array<{ id: string; full_name: string }>>([]);
  const [rules, setRules] = useState<Array<{ id: string; name: string; order: number }>>([]);
  const [selectedRuleId, setSelectedRuleId] = useState<string>("");
  const [dragRuleId, setDragRuleId] = useState<string | null>(null);
  const [scheduler, setScheduler] = useState({
    enabled: false,
    cron_minute: "0",
    cron_hour: "9",
    cron_day_of_month: "*",
    cron_month_of_year: "*",
    cron_day_of_week: "1-5",
    title: "Daily control task",
    description: "",
    priority: "medium" as Priority,
    template_id: "",
    assigned_to: "",
    requested_by: "",
    board_id: "",
    client_id: "",
    due_in_hours: 24,
    observer_ids: [] as string[],
    co_assignee_ids: [] as string[],
    dedup_window_minutes: 180,
  });

  useEffect(() => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [settings, users] = await Promise.all([
          fetchAdminSettings(),
          fetchUsers({ limit: 200, offset: 0, is_active: true }),
        ]);
        if (cancelled) return;
        setEnvPreview(settings.env_preview || {});
        setRules((settings.scheduler_rules || []).map((r) => ({ id: String(r.id || ""), name: String(r.name || "Rule"), order: Number(r.order || 0) })));
        setSelectedRuleId(String(settings.scheduler?.id || settings.scheduler_rules?.[0]?.id || ""));
        setScheduler({
          enabled: !!settings.scheduler.enabled,
          cron_minute: settings.scheduler.cron_minute || "0",
          cron_hour: settings.scheduler.cron_hour || "9",
          cron_day_of_month: settings.scheduler.cron_day_of_month || "*",
          cron_month_of_year: settings.scheduler.cron_month_of_year || "*",
          cron_day_of_week: settings.scheduler.cron_day_of_week || "1-5",
          title: settings.scheduler.title || "Daily control task",
          description: settings.scheduler.description || "",
          priority: (settings.scheduler.priority || "medium") as Priority,
          template_id: settings.scheduler.template_id || "",
          assigned_to: settings.scheduler.assigned_to || "",
          requested_by: settings.scheduler.requested_by || "",
          board_id: settings.scheduler.board_id || "",
          client_id: settings.scheduler.client_id || "",
          due_in_hours: Number(settings.scheduler.due_in_hours || 24),
          observer_ids: settings.scheduler.observer_ids || [],
          co_assignee_ids: settings.scheduler.co_assignee_ids || [],
          dedup_window_minutes: Number(settings.scheduler.dedup_window_minutes || 180),
        });
        setStaff(users.items.map((u) => ({ id: String(u.id), full_name: u.full_name })));
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Не удалось загрузить настройки");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin || tab !== "deploy") return;
    let cancelled = false;
    void (async () => {
      try {
        const [st, jobs, branches] = await Promise.all([
          fetchDeployStatus(),
          fetchDeployJobs(20),
          fetchDeployBranches().catch(() => [] as string[]),
        ]);
        if (cancelled) return;
        setDeployStatus(st);
        setDeployJobs(
          jobs.map((j) => ({
            id: j.id,
            branch: j.branch,
            status: j.status,
            log_excerpt: j.log_excerpt,
            error_message: j.error_message,
            created_at: j.created_at,
          })),
        );
        setDeployBranches(branches);
        setDeployBranch((prev) => {
          if (prev) return prev;
          if (!branches.length) return "";
          const mainOrMaster = branches.find((b) => b === "main" || b === "master");
          return mainOrMaster || branches[0] || "";
        });
      } catch {
        if (!cancelled) setDeployStatus(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAdmin, tab]);

  useEffect(() => {
    if (!isAdmin || tab !== "logs") return;
    let cancelled = false;
    void (async () => {
      setLogsBusy(true);
      try {
        const lines = await fetchProjectLogs(logTail);
        if (!cancelled) setProjectLogText(lines);
      } catch {
        if (!cancelled) setProjectLogText("Не удалось загрузить логи (deploy-agent и ADMIN_DEPLOY_ENABLED).");
      } finally {
        if (!cancelled) setLogsBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAdmin, tab, logTail]);

  async function onSave() {
    setSaving(true);
    setError(null);
    setOk(null);
    try {
      if (!selectedRuleId) {
        await updateAdminSchedulerSettings({
          enabled: scheduler.enabled,
          cron_minute: scheduler.cron_minute,
          cron_hour: scheduler.cron_hour,
          cron_day_of_month: scheduler.cron_day_of_month,
          cron_month_of_year: scheduler.cron_month_of_year,
          cron_day_of_week: scheduler.cron_day_of_week,
          title: scheduler.title,
          description: scheduler.description || null,
          priority: scheduler.priority,
          template_id: scheduler.template_id || null,
          assigned_to: scheduler.assigned_to || null,
          requested_by: scheduler.requested_by || null,
          board_id: scheduler.board_id || null,
          client_id: scheduler.client_id || null,
          due_in_hours: Number(scheduler.due_in_hours),
          observer_ids: scheduler.observer_ids,
          co_assignee_ids: scheduler.co_assignee_ids,
          dedup_window_minutes: Number(scheduler.dedup_window_minutes),
        });
      } else {
        await updateAdminSchedulerRule(selectedRuleId, {
          name: rules.find((r) => r.id === selectedRuleId)?.name || "Rule",
          enabled: scheduler.enabled,
          cron_minute: scheduler.cron_minute,
          cron_hour: scheduler.cron_hour,
          cron_day_of_month: scheduler.cron_day_of_month,
          cron_month_of_year: scheduler.cron_month_of_year,
          cron_day_of_week: scheduler.cron_day_of_week,
          title: scheduler.title,
          description: scheduler.description || null,
          priority: scheduler.priority,
          template_id: scheduler.template_id || null,
          assigned_to: scheduler.assigned_to || null,
          requested_by: scheduler.requested_by || null,
          board_id: scheduler.board_id || null,
          client_id: scheduler.client_id || null,
          due_in_hours: Number(scheduler.due_in_hours),
          observer_ids: scheduler.observer_ids,
          co_assignee_ids: scheduler.co_assignee_ids,
          dedup_window_minutes: Number(scheduler.dedup_window_minutes),
        });
      }
      const freshRules = await fetchAdminSchedulerRules();
      setRules(freshRules.map((r) => ({ id: String(r.id || ""), name: String(r.name || "Rule"), order: Number(r.order || 0) })));
      if (selectedRuleId) {
        const current = freshRules.find((r) => String(r.id) === selectedRuleId);
        if (current) {
          setScheduler((s) => ({
            ...s,
            enabled: !!current.enabled,
            cron_minute: current.cron_minute || "0",
            cron_hour: current.cron_hour || "9",
            cron_day_of_month: current.cron_day_of_month || "*",
            cron_month_of_year: current.cron_month_of_year || "*",
            cron_day_of_week: current.cron_day_of_week || "1-5",
            title: current.title || "",
            description: current.description || "",
            priority: (current.priority || "medium") as Priority,
            template_id: current.template_id || "",
            assigned_to: current.assigned_to || "",
            requested_by: current.requested_by || "",
            board_id: current.board_id || "",
            client_id: current.client_id || "",
            due_in_hours: Number(current.due_in_hours || 24),
            observer_ids: current.observer_ids || [],
            co_assignee_ids: current.co_assignee_ids || [],
            dedup_window_minutes: Number(current.dedup_window_minutes || 180),
          }));
        }
      }
      setOk("Сохранено");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  }

  async function onCreateRule() {
    setError(null);
    const created = await createAdminSchedulerRule({
      name: `Rule ${rules.length + 1}`,
      enabled: false,
      cron_minute: "0",
      cron_hour: "9",
      cron_day_of_month: "*",
      cron_month_of_year: "*",
      cron_day_of_week: "1-5",
      title: "Scheduled task",
      priority: "medium",
      due_in_hours: 24,
      dedup_window_minutes: 180,
    });
    const ruleId = String(created.id || "");
    setRules((prev) => [...prev, { id: ruleId, name: String(created.name || "Rule"), order: Number(created.order || prev.length) }]);
    setSelectedRuleId(ruleId);
    setScheduler({
      enabled: !!created.enabled,
      cron_minute: created.cron_minute || "0",
      cron_hour: created.cron_hour || "9",
      cron_day_of_month: created.cron_day_of_month || "*",
      cron_month_of_year: created.cron_month_of_year || "*",
      cron_day_of_week: created.cron_day_of_week || "1-5",
      title: created.title || "Scheduled task",
      description: created.description || "",
      priority: (created.priority || "medium") as Priority,
      template_id: created.template_id || "",
      assigned_to: created.assigned_to || "",
      requested_by: created.requested_by || "",
      board_id: created.board_id || "",
      client_id: created.client_id || "",
      due_in_hours: Number(created.due_in_hours || 24),
      observer_ids: created.observer_ids || [],
      co_assignee_ids: created.co_assignee_ids || [],
      dedup_window_minutes: Number(created.dedup_window_minutes || 180),
    });
  }

  async function onDeleteRule() {
    if (!selectedRuleId) return;
    await deleteAdminSchedulerRule(selectedRuleId);
    const fresh = await fetchAdminSchedulerRules();
    setRules(fresh.map((r) => ({ id: String(r.id || ""), name: String(r.name || "Rule"), order: Number(r.order || 0) })));
    const next = fresh[0];
    if (!next) {
      setSelectedRuleId("");
      return;
    }
    setSelectedRuleId(String(next.id || ""));
    setScheduler({
      enabled: !!next.enabled,
      cron_minute: next.cron_minute || "0",
      cron_hour: next.cron_hour || "9",
      cron_day_of_month: next.cron_day_of_month || "*",
      cron_month_of_year: next.cron_month_of_year || "*",
      cron_day_of_week: next.cron_day_of_week || "1-5",
      title: next.title || "Scheduled task",
      description: next.description || "",
      priority: (next.priority || "medium") as Priority,
      template_id: next.template_id || "",
      assigned_to: next.assigned_to || "",
      requested_by: next.requested_by || "",
      board_id: next.board_id || "",
      client_id: next.client_id || "",
      due_in_hours: Number(next.due_in_hours || 24),
      observer_ids: next.observer_ids || [],
      co_assignee_ids: next.co_assignee_ids || [],
      dedup_window_minutes: Number(next.dedup_window_minutes || 180),
    });
  }

  async function onSelectRule(ruleId: string) {
    setSelectedRuleId(ruleId);
    const fresh = await fetchAdminSchedulerRules();
    const one = fresh.find((r) => String(r.id) === ruleId);
    if (!one) return;
    setScheduler({
      enabled: !!one.enabled,
      cron_minute: one.cron_minute || "0",
      cron_hour: one.cron_hour || "9",
      cron_day_of_month: one.cron_day_of_month || "*",
      cron_month_of_year: one.cron_month_of_year || "*",
      cron_day_of_week: one.cron_day_of_week || "1-5",
      title: one.title || "Scheduled task",
      description: one.description || "",
      priority: (one.priority || "medium") as Priority,
      template_id: one.template_id || "",
      assigned_to: one.assigned_to || "",
      requested_by: one.requested_by || "",
      board_id: one.board_id || "",
      client_id: one.client_id || "",
      due_in_hours: Number(one.due_in_hours || 24),
      observer_ids: one.observer_ids || [],
      co_assignee_ids: one.co_assignee_ids || [],
      dedup_window_minutes: Number(one.dedup_window_minutes || 180),
    });
  }

  async function onRunNow() {
    if (!selectedRuleId) return;
    setError(null);
    setOk(null);
    try {
      const result = await runAdminSchedulerRuleNow(selectedRuleId);
      setOk(result.created > 0 ? `Запущено: создано ${result.created}` : "Запуск выполнен, но задача не создана (дедуп/валидность)");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка запуска правила");
    }
  }

  async function onDeployRun() {
    if (!deployBranch.trim()) return;
    setError(null);
    setOk(null);
    setDeployBusy(true);
    try {
      const job = await runDeploy(deployBranch.trim());
      setOk(`Деплой завершён: ${job.status}`);
      const jobs = await fetchDeployJobs(20);
      setDeployJobs(
        jobs.map((j) => ({
          id: j.id,
          branch: j.branch,
          status: j.status,
          log_excerpt: j.log_excerpt,
          error_message: j.error_message,
          created_at: j.created_at,
        })),
      );
      setDeployStatus(await fetchDeployStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка деплоя");
    } finally {
      setDeployBusy(false);
    }
  }

  async function moveRule(delta: -1 | 1) {
    const idx = rules.findIndex((r) => r.id === selectedRuleId);
    if (idx < 0) return;
    const nextIdx = idx + delta;
    if (nextIdx < 0 || nextIdx >= rules.length) return;
    const reordered = [...rules];
    const [item] = reordered.splice(idx, 1);
    reordered.splice(nextIdx, 0, item);
    const normalized = reordered.map((r, i) => ({ ...r, order: i }));
    setRules(normalized);
    await Promise.all(normalized.map((r) => updateAdminSchedulerRule(r.id, { order: r.order, name: r.name })));
  }

  async function persistRuleOrder(nextRules: Array<{ id: string; name: string; order: number }>) {
    const normalized = nextRules.map((r, i) => ({ ...r, order: i }));
    setRules(normalized);
    await Promise.all(normalized.map((r) => updateAdminSchedulerRule(r.id, { order: r.order, name: r.name })));
  }

  async function onDropRule(targetId: string) {
    if (!dragRuleId || dragRuleId === targetId) {
      setDragRuleId(null);
      return;
    }
    const from = rules.findIndex((r) => r.id === dragRuleId);
    const to = rules.findIndex((r) => r.id === targetId);
    if (from < 0 || to < 0) {
      setDragRuleId(null);
      return;
    }
    const reordered = [...rules];
    const [moved] = reordered.splice(from, 1);
    reordered.splice(to, 0, moved);
    setDragRuleId(null);
    await persistRuleOrder(reordered);
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 p-4 lg:p-6">
        <Skeleton className="h-10 w-80" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (!authUser) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-950">
          <p className="font-medium">Вы не вошли в систему на этом адресе.</p>
          <p className="mt-2 text-sm">
            Сессия и токены с localhost не переносятся на URL туннеля — выполните вход заново.
          </p>
          <a href="/login" className="mt-3 inline-block font-medium text-primary-700 underline">
            Войти
          </a>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800">
          Доступ только для администратора.
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 lg:p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Shield className="h-6 w-6 text-primary-600" />
          Админка
        </h1>
        <button onClick={() => void onSave()} className="btn-primary gap-1" disabled={saving}>
          <Save className="h-4 w-4" />
          {saving ? "Сохранение..." : "Сохранить"}
        </button>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className={`rounded-md px-3 py-1.5 text-sm ${tab === "rules" ? "bg-primary-600 text-white" : "bg-surface-100 text-surface-700"}`}
          onClick={() => setTab("rules")}
        >
          Rules
        </button>
        <button
          type="button"
          className={`rounded-md px-3 py-1.5 text-sm ${tab === "env" ? "bg-primary-600 text-white" : "bg-surface-100 text-surface-700"}`}
          onClick={() => setTab("env")}
        >
          Environment
        </button>
        <button
          type="button"
          className={`rounded-md px-3 py-1.5 text-sm ${tab === "deploy" ? "bg-primary-600 text-white" : "bg-surface-100 text-surface-700"}`}
          onClick={() => setTab("deploy")}
        >
          Deploy
        </button>
        <button
          type="button"
          className={`rounded-md px-3 py-1.5 text-sm ${tab === "logs" ? "bg-primary-600 text-white" : "bg-surface-100 text-surface-700"}`}
          onClick={() => setTab("logs")}
        >
          Логи сервисов
        </button>
      </div>

      {error && <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      {ok && <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{ok}</div>}

      {tab === "rules" && (
      <div className="card space-y-4 p-4">
        <h2 className="text-lg font-semibold">Планировщик задач</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select className="input min-w-[260px]" value={selectedRuleId} onChange={(e) => void onSelectRule(e.target.value)}>
            {rules.map((r) => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </select>
          <input
            className="input min-w-[220px]"
            placeholder="Rule name"
            value={rules.find((r) => r.id === selectedRuleId)?.name || ""}
            onChange={(e) =>
              setRules((prev) => prev.map((r) => (r.id === selectedRuleId ? { ...r, name: e.target.value } : r)))
            }
          />
          <button type="button" className="btn-ghost btn-sm gap-1" onClick={() => void onCreateRule()}>
            <Plus className="h-4 w-4" /> Новое правило
          </button>
          <button type="button" className="btn-ghost btn-sm gap-1 text-red-600" onClick={() => void onDeleteRule()} disabled={!selectedRuleId}>
            <Trash2 className="h-4 w-4" /> Удалить правило
          </button>
          <button type="button" className="btn-ghost btn-sm gap-1" onClick={() => void moveRule(-1)} disabled={!selectedRuleId}>
            <ArrowUp className="h-4 w-4" /> Выше
          </button>
          <button type="button" className="btn-ghost btn-sm gap-1" onClick={() => void moveRule(1)} disabled={!selectedRuleId}>
            <ArrowDown className="h-4 w-4" /> Ниже
          </button>
          <button type="button" className="btn-primary btn-sm gap-1" onClick={() => void onRunNow()} disabled={!selectedRuleId}>
            <Play className="h-4 w-4" /> Run now
          </button>
        </div>
        <div className="space-y-1 rounded-lg border border-surface-200 p-2">
          <div className="px-2 pb-1 text-xs font-semibold text-surface-500">Порядок правил (drag & drop)</div>
          {rules.map((r) => (
            <button
              key={r.id}
              type="button"
              draggable
              onDragStart={() => setDragRuleId(r.id)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => void onDropRule(r.id)}
              onClick={() => void onSelectRule(r.id)}
              className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm ${
                selectedRuleId === r.id ? "bg-primary-50 text-primary-700" : "hover:bg-surface-50"
              } ${dragRuleId === r.id ? "opacity-60" : ""}`}
              title="Перетащите для изменения приоритета"
            >
              <span className="truncate">
                {r.order + 1}. {r.name}
              </span>
              <span className="text-xs text-surface-400">::</span>
            </button>
          ))}
        </div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={scheduler.enabled}
              onChange={(e) => setScheduler((s) => ({ ...s, enabled: e.target.checked }))}
            />
            Включить
          </label>
          <input className="input" placeholder="Minute" value={scheduler.cron_minute} onChange={(e) => setScheduler((s) => ({ ...s, cron_minute: e.target.value }))} />
          <input className="input" placeholder="Hour" value={scheduler.cron_hour} onChange={(e) => setScheduler((s) => ({ ...s, cron_hour: e.target.value }))} />
          <input className="input" placeholder="Day of week" value={scheduler.cron_day_of_week} onChange={(e) => setScheduler((s) => ({ ...s, cron_day_of_week: e.target.value }))} />
          <input className="input" placeholder="Day of month" value={scheduler.cron_day_of_month} onChange={(e) => setScheduler((s) => ({ ...s, cron_day_of_month: e.target.value }))} />
          <input className="input" placeholder="Month of year" value={scheduler.cron_month_of_year} onChange={(e) => setScheduler((s) => ({ ...s, cron_month_of_year: e.target.value }))} />
          <select className="input" value={scheduler.priority} onChange={(e) => setScheduler((s) => ({ ...s, priority: e.target.value as Priority }))}>
            <option value="low">Низкий</option>
            <option value="medium">Средний</option>
            <option value="high">Высокий</option>
            <option value="critical">Критический</option>
          </select>
          <input className="input" type="number" min={0} max={744} value={scheduler.due_in_hours} onChange={(e) => setScheduler((s) => ({ ...s, due_in_hours: Number(e.target.value || 0) }))} placeholder="Due in hours" />
        </div>
        <input className="input w-full" placeholder="Заголовок задачи" value={scheduler.title} onChange={(e) => setScheduler((s) => ({ ...s, title: e.target.value }))} />
        <textarea className="input min-h-[84px] w-full" placeholder="Описание задачи" value={scheduler.description} onChange={(e) => setScheduler((s) => ({ ...s, description: e.target.value }))} />
        <div className="grid gap-3 md:grid-cols-2">
          <select className="input" value={scheduler.assigned_to} onChange={(e) => setScheduler((s) => ({ ...s, assigned_to: e.target.value }))}>
            <option value="">Исполнитель (optional)</option>
            {staff.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </select>
          <select className="input" value={scheduler.requested_by} onChange={(e) => setScheduler((s) => ({ ...s, requested_by: e.target.value }))}>
            <option value="">Постановщик (optional)</option>
            {staff.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </select>
        </div>
      </div>
      )}

      {tab === "env" && (
      <div className="card p-4">
        <h2 className="mb-2 text-lg font-semibold">Текущее окружение (без секретов)</h2>
        <div className="grid gap-1 md:grid-cols-2 lg:grid-cols-3">
          {Object.entries(envPreview).map(([k, v]) => (
            <div key={k} className="rounded bg-surface-50 px-2 py-1 text-xs">
              <span className="font-mono text-surface-500">{k}</span>: <span>{v}</span>
            </div>
          ))}
        </div>
      </div>
      )}

      {tab === "deploy" && (
        <div className="card space-y-4 p-4">
          <h2 className="text-lg font-semibold">Деплой с сервера</h2>
          <p className="text-sm text-surface-600">
            Нужны <code className="rounded bg-surface-100 px-1">ADMIN_DEPLOY_ENABLED=true</code>,{" "}
            <code className="rounded bg-surface-100 px-1">DEPLOY_AGENT_URL</code>, контейнер{" "}
            <code className="rounded bg-surface-100 px-1">deploy-agent</code> и переменные{" "}
            <code className="rounded bg-surface-100 px-1">GITHUB_SSH_KEY</code> /{" "}
            <code className="rounded bg-surface-100 px-1">GITHUB_REPO_URL</code> на сервере. После pull выполняется
            применение схемы БД и перезапуск compose; при ошибке или падении health — откат на предыдущий commit.
          </p>
          {deployStatus && (
            <div className="rounded border border-surface-200 bg-surface-50 px-3 py-2 text-sm">
              <div>
                UI: {deployStatus.deploy_ui_enabled ? "включён" : "выключен"} · агент:{" "}
                {deployStatus.agent_reachable === null
                  ? "—"
                  : deployStatus.agent_reachable
                    ? "ok"
                    : `недоступен${deployStatus.agent_error ? ` (${deployStatus.agent_error})` : ""}`}{" "}
                · repo env: {deployStatus.github_repo_configured ? "задан" : "не задан"}
              </div>
            </div>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1 text-sm">
              Ветка
              <select
                className="input min-w-[220px]"
                value={deployBranch}
                onChange={(e) => setDeployBranch(e.target.value)}
                disabled={deployBusy || !deployBranches.length}
              >
                {deployBranches.length === 0 ? (
                  <option value="">(список веток недоступен)</option>
                ) : (
                  deployBranches.map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))
                )}
              </select>
            </label>
            <button
              type="button"
              className="btn-primary"
              disabled={deployBusy || !deployBranch || !deployStatus?.deploy_ui_enabled}
              onClick={() => void onDeployRun()}
            >
              {deployBusy ? "Деплой…" : "Деплоить"}
            </button>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-semibold text-surface-700">Последние запуски</h3>
            <div className="max-h-48 overflow-auto rounded border border-surface-200 text-xs">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-surface-100 text-left">
                    <th className="p-2">Время</th>
                    <th className="p-2">Ветка</th>
                    <th className="p-2">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {deployJobs.map((j) => (
                    <tr key={j.id} className="border-t border-surface-200">
                      <td className="p-2 whitespace-nowrap">{new Date(j.created_at).toLocaleString()}</td>
                      <td className="p-2 font-mono">{j.branch}</td>
                      <td className="p-2">
                        {j.status}
                        {j.error_message ? (
                          <span className="block text-red-600">{j.error_message}</span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {deployJobs[0]?.log_excerpt ? (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-surface-700">Лог последнего деплоя</h3>
              <pre className="max-h-96 overflow-auto rounded border border-surface-200 bg-surface-950 p-3 text-xs text-surface-100 whitespace-pre-wrap">
                {deployJobs[0].log_excerpt}
              </pre>
            </div>
          ) : null}
        </div>
      )}

      {tab === "logs" && (
        <div className="card space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">Логи docker compose</h2>
            <label className="flex items-center gap-2 text-sm">
              tail
              <input
                type="number"
                className="input w-24"
                min={50}
                max={5000}
                value={logTail}
                onChange={(e) => setLogTail(Number(e.target.value) || 400)}
              />
            </label>
            <button
              type="button"
              className="btn-ghost btn-sm"
              disabled={logsBusy}
              onClick={() => {
                setTab("logs");
                void (async () => {
                  setLogsBusy(true);
                  try {
                    setProjectLogText(await fetchProjectLogs(logTail));
                  } finally {
                    setLogsBusy(false);
                  }
                })();
              }}
            >
              Обновить
            </button>
          </div>
          <pre className="max-h-[32rem] overflow-auto rounded border border-surface-200 bg-surface-950 p-3 text-xs text-surface-100 whitespace-pre-wrap">
            {logsBusy ? "Загрузка…" : projectLogText || "Пусто"}
          </pre>
        </div>
      )}
    </div>
  );
}


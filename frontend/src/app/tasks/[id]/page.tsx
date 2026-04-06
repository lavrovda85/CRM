"use client";

import { useEffect, useState, use } from "react";
import {
  ArrowLeft,
  Clock,
  FileText,
  Image,
  MessageSquare,
  CheckSquare,
  ChevronRight,
  Shield,
  Paperclip,
  Send,
  Play,
  User,
} from "lucide-react";
import Link from "next/link";
import { fetchTask, toggleChecklistItem, transitionTask } from "@/lib/api";
import type { TaskDetail } from "@/types";

const statusColor: Record<string, string> = {
  new: "bg-surface-100 text-surface-600",
  dispatched: "bg-sky-50 text-sky-700",
  in_progress: "bg-blue-50 text-blue-700",
  testing: "bg-amber-50 text-amber-700",
  photo_report: "bg-violet-50 text-violet-700",
  act_signing: "bg-orange-50 text-orange-700",
  done: "bg-green-50 text-green-700",
  completed: "bg-green-50 text-green-700",
};

const priorityColor: Record<string, string> = {
  low: "bg-green-50 text-green-700 border-green-200",
  medium: "bg-yellow-50 text-yellow-700 border-yellow-200",
  high: "bg-orange-50 text-orange-700 border-orange-200",
  critical: "bg-red-50 text-red-700 border-red-200",
};

const TRANSITIONS: Record<string, string[]> = {
  new: ["dispatched"],
  dispatched: ["in_progress"],
  in_progress: ["testing"],
  testing: ["photo_report", "in_progress"],
  photo_report: ["act_signing"],
  act_signing: ["done"],
};

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function TaskDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);

  useEffect(() => {
    fetchTask(id)
      .then(setTask)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  async function handleToggleItem(checklistId: string, itemId: string) {
    if (!task) return;
    try {
      const updated = await toggleChecklistItem(task.id, checklistId, itemId);
      setTask(updated);
    } catch {
      /* silent */
    }
  }

  async function handleTransition(toStatus: string) {
    if (!task || transitioning) return;
    setTransitioning(true);
    try {
      await transitionTask(task.id, toStatus);
      const updated = await fetchTask(task.id);
      setTask(updated);
    } catch {
      /* silent */
    } finally {
      setTransitioning(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 p-4 lg:p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-center">
          <p className="text-lg font-medium text-surface-500">Task not found</p>
          <Link href="/tasks" className="mt-2 text-primary-600 hover:underline">Back to tasks</Link>
        </div>
      </div>
    );
  }

  const availableTransitions = TRANSITIONS[task.status] ?? [];
  const completedItems = task.checklists.flatMap((c) => c.items).filter((i) => i.is_completed).length;
  const totalItems = task.checklists.flatMap((c) => c.items).length;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 lg:p-6">
      {/* Back */}
      <Link href="/tasks" className="inline-flex items-center gap-1 text-sm text-surface-500 hover:text-surface-900">
        <ArrowLeft className="h-4 w-4" /> Back to tasks
      </Link>

      {/* Header */}
      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold lg:text-2xl">{task.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`badge ${statusColor[task.status] ?? "bg-surface-100 text-surface-600"}`}>
                {task.status.replace(/_/g, " ")}
              </span>
              <span className={`badge border ${priorityColor[task.priority] ?? ""}`}>
                {task.priority}
              </span>
              {task.assignee && (
                <span className="flex items-center gap-1 text-sm text-surface-500">
                  <User className="h-3.5 w-3.5" /> {task.assignee.full_name}
                </span>
              )}
              {task.due_date && (
                <span className="flex items-center gap-1 text-sm text-surface-500">
                  <Clock className="h-3.5 w-3.5" /> {new Date(task.due_date).toLocaleDateString("ru-RU")}
                </span>
              )}
            </div>
          </div>

          {/* Transition Buttons */}
          {availableTransitions.length > 0 && (
            <div className="flex gap-2">
              {availableTransitions.map((t) => (
                <button
                  key={t}
                  disabled={transitioning}
                  onClick={() => handleTransition(t)}
                  className="btn-primary gap-1.5"
                >
                  <Play className="h-3.5 w-3.5" />
                  {t.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Description */}
        {task.description && (
          <div className="mt-4 rounded-lg bg-surface-50 p-4 text-sm text-surface-600 leading-relaxed">
            {task.description}
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Main Content */}
        <div className="space-y-6 lg:col-span-3">
          {/* Checklists */}
          {task.checklists.length > 0 && (
            <div className="card">
              <div className="flex items-center justify-between border-b border-surface-100 p-4">
                <h2 className="flex items-center gap-2 font-semibold">
                  <CheckSquare className="h-4 w-4 text-primary-500" />
                  Checklists
                  <span className="text-sm font-normal text-surface-400">
                    {completedItems}/{totalItems}
                  </span>
                </h2>
                {totalItems > 0 && (
                  <div className="h-2 w-24 overflow-hidden rounded-full bg-surface-100">
                    <div
                      className="h-full rounded-full bg-primary-500 transition-all"
                      style={{ width: `${(completedItems / totalItems) * 100}%` }}
                    />
                  </div>
                )}
              </div>
              <div className="divide-y divide-surface-50">
                {task.checklists.map((cl) => (
                  <div key={cl.id} className="p-4">
                    <div className="mb-2 flex items-center gap-2">
                      <h3 className="text-sm font-medium">{cl.title}</h3>
                      {cl.gate_transition && (
                        <span className="badge bg-amber-50 text-amber-700 gap-1">
                          <Shield className="h-3 w-3" /> Gate
                        </span>
                      )}
                      {cl.is_completed && (
                        <span className="badge bg-green-50 text-green-700">Complete</span>
                      )}
                    </div>
                    <ul className="space-y-1.5">
                      {cl.items.map((item) => (
                        <li key={item.id}>
                          <label className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-50 transition-colors">
                            <input
                              type="checkbox"
                              checked={item.is_completed}
                              onChange={() => handleToggleItem(cl.id, item.id)}
                              className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
                            />
                            <span className={`text-sm ${item.is_completed ? "text-surface-400 line-through" : ""}`}>
                              {item.title}
                            </span>
                          </label>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Documents & Photos */}
          {task.documents.length > 0 && (
            <div className="card">
              <div className="border-b border-surface-100 p-4">
                <h2 className="flex items-center gap-2 font-semibold">
                  <Paperclip className="h-4 w-4 text-primary-500" /> Documents
                </h2>
              </div>
              <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3">
                {task.documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex flex-col items-center gap-2 rounded-lg border border-surface-100 p-3 text-center"
                  >
                    {doc.mime_type.startsWith("image/") ? (
                      <Image className="h-8 w-8 text-violet-400" />
                    ) : (
                      <FileText className="h-8 w-8 text-blue-400" />
                    )}
                    <span className="text-xs font-medium text-surface-700 truncate w-full">{doc.filename}</span>
                    <span className="text-[10px] text-surface-400">
                      {(doc.file_size / 1024).toFixed(0)} KB
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Time Entries */}
          {task.time_entries.length > 0 && (
            <div className="card">
              <div className="border-b border-surface-100 p-4">
                <h2 className="flex items-center gap-2 font-semibold">
                  <Clock className="h-4 w-4 text-primary-500" /> Time Entries
                </h2>
              </div>
              <div className="divide-y divide-surface-50">
                {task.time_entries.map((entry) => (
                  <div key={entry.id} className="flex items-center justify-between p-4">
                    <div>
                      <span className="badge bg-surface-100 text-surface-600">{entry.entry_type}</span>
                      {entry.notes && <p className="mt-1 text-sm text-surface-500">{entry.notes}</p>}
                    </div>
                    <span className="text-sm font-medium">
                      {Math.floor(entry.duration_minutes / 60)}h {entry.duration_minutes % 60}m
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Comments */}
          <div className="card">
            <div className="border-b border-surface-100 p-4">
              <h2 className="flex items-center gap-2 font-semibold">
                <MessageSquare className="h-4 w-4 text-primary-500" /> Comments
                <span className="text-sm font-normal text-surface-400">{task.comments.length}</span>
              </h2>
            </div>
            <div className="divide-y divide-surface-50">
              {task.comments.map((comment) => (
                <div key={comment.id} className="p-4">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-100 text-xs font-medium text-primary-700">
                      {(comment.author_name ?? "?").charAt(0)}
                    </div>
                    <span className="text-sm font-medium">{comment.author_name ?? "Unknown"}</span>
                    <span className="text-xs text-surface-400">
                      {new Date(comment.created_at).toLocaleString("ru-RU")}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-surface-600 pl-9">{comment.body}</p>
                </div>
              ))}
              {task.comments.length === 0 && (
                <p className="p-6 text-center text-sm text-surface-400">No comments yet</p>
              )}
            </div>
            <div className="border-t border-surface-100 p-4">
              <div className="flex gap-2">
                <input type="text" placeholder="Write a comment..." className="input" />
                <button className="btn-primary shrink-0 px-3">
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar — Activity Timeline */}
        <div className="lg:col-span-2">
          <div className="card sticky top-6">
            <div className="border-b border-surface-100 p-4">
              <h2 className="font-semibold">Activity</h2>
            </div>
            <div className="max-h-[60vh] overflow-y-auto p-4">
              {task.status_history.length === 0 ? (
                <p className="text-sm text-surface-400">No activity yet</p>
              ) : (
                <div className="relative space-y-4 pl-5 before:absolute before:left-[7px] before:top-2 before:h-[calc(100%-16px)] before:w-0.5 before:bg-surface-100">
                  {[...task.status_history].reverse().map((entry) => (
                    <div key={entry.id} className="relative">
                      <div className="absolute -left-5 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-primary-400" />
                      <div className="rounded-lg bg-surface-50 p-3">
                        <div className="flex items-center gap-1 text-xs">
                          <span className={`badge ${statusColor[entry.from_status] ?? "bg-surface-100 text-surface-600"}`}>
                            {entry.from_status.replace(/_/g, " ")}
                          </span>
                          <ChevronRight className="h-3 w-3 text-surface-400" />
                          <span className={`badge ${statusColor[entry.to_status] ?? "bg-surface-100 text-surface-600"}`}>
                            {entry.to_status.replace(/_/g, " ")}
                          </span>
                        </div>
                        {entry.reason && (
                          <p className="mt-1.5 text-xs text-surface-500">{entry.reason}</p>
                        )}
                        <p className="mt-1 text-[10px] text-surface-400">
                          {new Date(entry.created_at).toLocaleString("ru-RU")}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState, useRef, useCallback, use, useMemo } from "react";
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
  Mic,
  StopCircle,
  Send,
  Play,
  User,
  Trash2,
  Pencil,
  Loader2,
  Save,
  X,
  Package,
  CheckCircle2,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ApiError,
  fetchTask,
  toggleChecklistItem,
  transitionTask,
  addComment,
  deleteTask,
  updateTask,
  uploadDocument,
  getDocumentDownloadUrl,
  deleteDocument,
  fetchUsers,
  fetchWarehouseItems,
  fetchWarehouseMovements,
  createWarehouseMovement,
  fetchCurrentUser,
  fetchTaskChatRoom,
} from "@/lib/api";
import { cn, formatEnumLabel } from "@/lib/utils";
import type {
  TaskDetail,
  UserSummary,
  DocumentResponse,
  ChatRoomResponse,
  WarehouseItemResponse,
  WarehouseMovementResponse,
} from "@/types";
import { FileUpload, type FileEntry } from "@/components/file-upload/FileUpload";
import { Modal } from "@/components/ui/Modal";
import { YandexTaskLocationPicker } from "@/components/tasks/YandexTaskLocationPicker";

const statusColor: Record<string, string> = {
  new: "bg-surface-100 text-surface-600",
  dispatched: "bg-sky-50 text-sky-700",
  in_progress: "bg-blue-50 text-blue-700",
  testing: "bg-amber-50 text-amber-700",
  photo_report: "bg-amber-50 text-amber-700",
  act_signing: "bg-orange-50 text-orange-700",
  done: "bg-green-50 text-green-700",
  completed: "bg-green-50 text-green-700",
  closed: "bg-surface-200 text-surface-600",
};

const priorityColor: Record<string, string> = {
  low: "bg-green-50 text-green-700 border-green-200",
  medium: "bg-yellow-50 text-yellow-700 border-yellow-200",
  high: "bg-orange-50 text-orange-700 border-orange-200",
  critical: "bg-red-50 text-red-700 border-red-200",
};

const TERMINAL_STATUSES = new Set(["done", "completed", "closed"]);
function isTerminal(status: string) { return TERMINAL_STATUSES.has(status); }

const TRANSITIONS: Record<string, string[]> = {
  new: ["dispatched"],
  dispatched: ["new", "in_progress"],
  in_progress: ["dispatched", "testing"],
  testing: ["in_progress", "done"],
  photo_report: ["testing", "done"],
  /** Legacy rows created before the act-signing stage was removed from the pipeline. */
  act_signing: ["testing", "done"],
  done: ["testing", "closed"],
  closed: ["done"],
};

const statusLabel: Record<string, string> = {
  new: "Новая",
  dispatched: "Назначена",
  in_progress: "В работе",
  testing: "Согласование",
  photo_report: "Согласование",
  act_signing: "Подписание акта",
  done: "Выполнено",
  completed: "Выполнено",
  closed: "Закрыта",
};

const priorityLabel: Record<string, string> = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
  critical: "Критический",
};

/** Value for ``<input type="datetime-local" />`` in local timezone. */
function toDatetimeLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day}T${h}:${min}`;
}

/** Parse datetime-local to ISO for API; empty clears the date. */
function parseDatetimeLocalToIso(local: string): string | null {
  const t = local.trim();
  if (!t) return null;
  const d = new Date(t);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

function instantMs(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const n = new Date(iso).getTime();
  return Number.isNaN(n) ? null : n;
}

function datesDiffer(
  previous: string | null | undefined,
  nextIso: string | null,
): boolean {
  return instantMs(previous) !== instantMs(nextIso);
}

function formatTaskDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function TaskDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const fromFieldWork = searchParams.get("from") === "field-work";
  const backHref = fromFieldWork ? "/field-work" : "/tasks";
  const backLabel = fromFieldWork ? "Назад к выездным работам" : "Назад к задачам";
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [taskChatRoom, setTaskChatRoom] = useState<ChatRoomResponse | null>(null);
  const [transitioning, setTransitioning] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [submittingComment, setSubmittingComment] = useState(false);
  const [pendingCommentFiles, setPendingCommentFiles] = useState<File[]>([]);
  const [commentRecording, setCommentRecording] = useState(false);
  const [commentMediaError, setCommentMediaError] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<{ src: string; alt: string } | null>(null);
  const [docUrls, setDocUrls] = useState<Record<string, string>>({});
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editPriority, setEditPriority] = useState("");
  const [saving, setSaving] = useState(false);
  const commentInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const voiceChunksRef = useRef<BlobPart[]>([]);
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [editAssigneeId, setEditAssigneeId] = useState<string>("");
  const [editRequestedById, setEditRequestedById] = useState<string>("");
  const [editCoAssigneeIds, setEditCoAssigneeIds] = useState<string[]>([]);
  const [editObserverIds, setEditObserverIds] = useState<string[]>([]);
  const [editDueDate, setEditDueDate] = useState("");
  const [editStartedAt, setEditStartedAt] = useState("");
  const [editCompletedAt, setEditCompletedAt] = useState("");
  const [editSlaDeadline, setEditSlaDeadline] = useState("");
  const [editAddress, setEditAddress] = useState("");
  const [editLatitude, setEditLatitude] = useState("");
  const [editLongitude, setEditLongitude] = useState("");
  const [materialsOpen, setMaterialsOpen] = useState(false);
  const [warehouseItems, setWarehouseItems] = useState<WarehouseItemResponse[]>([]);
  const [selectedItemId, setSelectedItemId] = useState<string>("");
  const [materialQty, setMaterialQty] = useState<string>("");
  const [materialError, setMaterialError] = useState<string | null>(null);
  const [materialSubmitting, setMaterialSubmitting] = useState(false);
  const [taskMovements, setTaskMovements] = useState<WarehouseMovementResponse[]>([]);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  const applyTaskData = useCallback((data: TaskDetail) => {
    setTask(data);
    setEditTitle(data.title);
    setEditDescription(data.description ?? "");
    setEditPriority(data.priority);
    setEditAssigneeId(data.assignee?.id ?? "");
    setEditRequestedById(data.requested_by ?? "");
    setEditCoAssigneeIds((data.co_assignees ?? []).map((c) => c.id));
    setEditObserverIds((data.observers ?? []).map((c) => c.id));
    setEditDueDate(toDatetimeLocalInput(data.due_date));
    setEditStartedAt(toDatetimeLocalInput(data.started_at));
    setEditCompletedAt(toDatetimeLocalInput(data.completed_at));
    setEditSlaDeadline(toDatetimeLocalInput(data.sla_deadline));
    setEditAddress((data.address ?? "") as string);
    setEditLatitude(data.latitude !== null && data.latitude !== undefined ? String(data.latitude) : "");
    setEditLongitude(data.longitude !== null && data.longitude !== undefined ? String(data.longitude) : "");
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    setNotFound(false);
    setTask(null);

    fetchTask(id)
      .then((data) => {
        if (cancelled) return;
        applyTaskData(data);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.isNotFound) {
          setNotFound(true);
          return;
        }
        const msg = e instanceof ApiError
          ? `${e.message} (HTTP ${e.status}${e.code ? `, code=${e.code}` : ""})`
          : e instanceof Error
            ? e.message
            : "Request failed";
        setLoadError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id, applyTaskData]);

  // Load users for assignee select and comment author resolution
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const pageSize = 200;
        let offset = 0;
        const all: UserSummary[] = [];
        while (!cancelled) {
          const res = await fetchUsers({ is_active: true, limit: pageSize, offset });
          all.push(...res.items);
          offset += res.items.length;
          if (offset >= res.total || res.items.length < pageSize) break;
        }
        if (!cancelled) setUsers(all);
      } catch {
        if (!cancelled) setUsers([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void fetchCurrentUser()
      .then((u) => {
        if (!cancelled) setCurrentUserId(u.id);
      })
      .catch(() => {
        if (!cancelled) setCurrentUserId(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!task?.id) {
      setTaskChatRoom(null);
      return;
    }
    let cancelled = false;
    fetchTaskChatRoom(task.id)
      .then((room) => {
        if (!cancelled) setTaskChatRoom(room);
      })
      .catch(() => {
        if (!cancelled) setTaskChatRoom(null);
      });
    return () => {
      cancelled = true;
    };
  }, [task?.id, task?.comments.length]);

  // Load warehouse items when materials dialog is opened
  useEffect(() => {
    if (!materialsOpen) return;
    fetchWarehouseItems({ limit: 200 })
      .then((res) => setWarehouseItems(res.items))
      .catch(() => {});
  }, [materialsOpen]);

  // Load movements linked to this task (after task is loaded)
  useEffect(() => {
    if (!task?.id) return;
    fetchWarehouseMovements({ task_id: task.id, limit: 100 })
      .then((res) => setTaskMovements(res.items))
      .catch(() => {});
  }, [task?.id]);

  const documentById = useMemo(() => {
    const map = new Map<string, DocumentResponse>();
    if (!task) return map;
    for (const d of task.documents) map.set(d.id, d);
    return map;
  }, [task]);

  /** Resolve comment author when API omits ``author_name`` (cache / older backend). */
  const commentAuthorNameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const u of users) {
      const n = u.full_name?.trim();
      if (n) m.set(String(u.id), n);
    }
    if (task) {
      const pool: UserSummary[] = [
        ...(task.assignee ? [task.assignee] : []),
        ...(task.creator ? [task.creator] : []),
        ...(task.requester ? [task.requester] : []),
        ...(task.co_assignees ?? []),
        ...(task.observers ?? []),
      ];
      for (const u of pool) {
        const n = u.full_name?.trim();
        if (n) m.set(String(u.id), n);
      }
    }
    return m;
  }, [users, task]);

  const commentAttachmentIds = useMemo(() => {
    if (!task) return [];
    const ids: string[] = [];
    for (const c of task.comments) {
      const raw = (c.attachments ?? []) as unknown[];
      for (const a of raw) {
        if (a !== null && a !== undefined && String(a).trim()) ids.push(String(a));
      }
    }
    return Array.from(new Set(ids));
  }, [task]);

  const attachmentImageOrAudioIdsToFetch = useMemo(() => {
    const out: string[] = [];
    for (const id of commentAttachmentIds) {
      const doc = documentById.get(id);
      if (!doc) continue;
      if (
        (doc.mime_type?.startsWith("image/") || doc.mime_type?.startsWith("audio/")) &&
        !docUrls[id]
      ) {
        out.push(id);
      }
    }
    return out;
  }, [commentAttachmentIds, documentById, docUrls]);

  useEffect(() => {
    if (attachmentImageOrAudioIdsToFetch.length === 0) return;

    let cancelled = false;
    Promise.all(
      attachmentImageOrAudioIdsToFetch.map(async (docId) => {
        const { url } = await getDocumentDownloadUrl(docId);
        return { docId, url };
      }),
    )
      .then((results) => {
        if (cancelled) return;
        setDocUrls((prev) => {
          const next = { ...prev };
          for (const r of results) next[r.docId] = r.url;
          return next;
        });
      })
      .catch(() => {
        /* silent */
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attachmentImageOrAudioIdsToFetch.join("|")]);

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

  async function handleQuickComplete() {
    if (!task || transitioning || isTerminal(task.status)) return;
    setTransitioning(true);
    try {
      await transitionTask(task.id, "done", "Quick complete from task card");
      const updated = await fetchTask(task.id);
      setTask(updated);
    } catch {
      /* silent */
    } finally {
      setTransitioning(false);
    }
  }

  async function handleAddComment() {
    if (!task || submittingComment) return;
    if (!commentText.trim() && pendingCommentFiles.length === 0) return;
    setSubmittingComment(true);
    try {
      const attachmentDocIds: string[] = [];
      for (const file of pendingCommentFiles) {
        const uploaded = await uploadDocument(file, task.id, "other");
        attachmentDocIds.push(uploaded.id);
      }

      await addComment(task.id, commentText.trim(), [], attachmentDocIds);
      setCommentText("");
      setPendingCommentFiles([]);
      setCommentMediaError(null);
      const updated = await fetchTask(task.id);
      setTask(updated);
    } catch {
      /* silent */
    } finally {
      setSubmittingComment(false);
    }
  }

  async function startVoiceRecording() {
    setCommentMediaError(null);
    if (commentRecording) return;
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        setCommentMediaError("Voice recording is not supported in this browser.");
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      voiceChunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) voiceChunksRef.current.push(event.data);
      };

      recorder.onstop = () => {
        try {
          stream.getTracks().forEach((t) => t.stop());
        } catch {
          /* silent */
        }

        const blob = new Blob(voiceChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        const ext = recorder.mimeType.includes("ogg") ? "ogg" : "webm";
        const file = new File([blob], `voice-${Date.now()}.${ext}`, { type: blob.type || "audio/webm" });

        setPendingCommentFiles((prev) => [...prev, file]);
        setCommentRecording(false);
      };

      recorder.start();
      setCommentRecording(true);
    } catch (e) {
      setCommentMediaError(e instanceof Error ? e.message : "Voice recording failed.");
      setCommentRecording(false);
    }
  }

  function stopVoiceRecording() {
    const recorder = mediaRecorderRef.current;
    if (!recorder) return;
    if (recorder.state === "inactive") return;
    recorder.stop();
  }

  async function handleDelete() {
    if (!task || !confirm("Удалить задачу? Это действие нельзя отменить.")) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteTask(task.id);
      router.push(backHref);
    } catch (e) {
      setDeleteError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка удаления",
      );
      setDeleting(false);
    }
  }

  async function handleSaveEdit() {
    if (!task) return;
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      if (editTitle.trim() !== task.title) payload.title = editTitle.trim();
      if ((editDescription.trim() || null) !== (task.description ?? null)) {
        payload.description = editDescription.trim() || null;
      }
      if (editPriority !== task.priority) payload.priority = editPriority;
       // assignee can be changed from the details view
      if ((task.assignee?.id ?? "") !== editAssigneeId) {
        payload.assigned_to = editAssigneeId || null;
      }

      const prevReq = task.requested_by ?? "";
      if (editRequestedById !== prevReq) {
        payload.requested_by = editRequestedById || null;
      }

      const prevCo = [...(task.co_assignees ?? []).map((c) => c.id)].sort().join(",");
      const nextCo = [...editCoAssigneeIds].sort().join(",");
      if (prevCo !== nextCo) {
        payload.co_assignee_ids = [...editCoAssigneeIds];
      }

      const prevObs = [...(task.observers ?? []).map((c) => c.id)].sort().join(",");
      const nextObs = [...editObserverIds].sort().join(",");
      if (prevObs !== nextObs) {
        payload.observer_ids = [...editObserverIds];
      }

      const nextDue = parseDatetimeLocalToIso(editDueDate);
      if (datesDiffer(task.due_date, nextDue)) payload.due_date = nextDue;

      const nextStarted = parseDatetimeLocalToIso(editStartedAt);
      if (datesDiffer(task.started_at, nextStarted)) payload.started_at = nextStarted;

      const nextCompleted = parseDatetimeLocalToIso(editCompletedAt);
      if (datesDiffer(task.completed_at, nextCompleted)) payload.completed_at = nextCompleted;

      const nextSla = parseDatetimeLocalToIso(editSlaDeadline);
      if (datesDiffer(task.sla_deadline, nextSla)) payload.sla_deadline = nextSla;
      if ((task.address ?? "") !== editAddress.trim()) payload.address = editAddress.trim() || null;
      const prevLat = task.latitude !== null && task.latitude !== undefined ? String(task.latitude) : "";
      const prevLng = task.longitude !== null && task.longitude !== undefined ? String(task.longitude) : "";
      if (prevLat !== editLatitude.trim()) payload.latitude = editLatitude.trim() ? Number(editLatitude) : null;
      if (prevLng !== editLongitude.trim()) payload.longitude = editLongitude.trim() ? Number(editLongitude) : null;

      if (Object.keys(payload).length > 0) {
        await updateTask(task.id, payload);
        const updated = await fetchTask(task.id);
        setTask(updated);
      }
      setEditing(false);
    } catch {
      /* silent */
    } finally {
      setSaving(false);
    }
  }

  function cancelEdit() {
    if (!task) return;
    setEditTitle(task.title);
    setEditDescription(task.description ?? "");
    setEditPriority(task.priority);
    setEditAssigneeId(task.assignee?.id ?? "");
    setEditRequestedById(task.requested_by ?? "");
    setEditCoAssigneeIds((task.co_assignees ?? []).map((c) => c.id));
    setEditObserverIds((task.observers ?? []).map((c) => c.id));
    setEditDueDate(toDatetimeLocalInput(task.due_date));
    setEditStartedAt(toDatetimeLocalInput(task.started_at));
    setEditCompletedAt(toDatetimeLocalInput(task.completed_at));
    setEditSlaDeadline(toDatetimeLocalInput(task.sla_deadline));
    setEditAddress((task.address ?? "") as string);
    setEditLatitude(task.latitude !== null && task.latitude !== undefined ? String(task.latitude) : "");
    setEditLongitude(task.longitude !== null && task.longitude !== undefined ? String(task.longitude) : "");
    setEditing(false);
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
    if (loadError) {
      return (
        <div className="mx-auto max-w-lg space-y-4 p-6 text-center">
          <p className="text-lg font-medium text-surface-700">Ошибка загрузки задачи</p>
          <p className="text-sm text-surface-500">{loadError}</p>
          <div className="flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={() => {
                setLoading(true);
                setLoadError(null);
                setNotFound(false);
                fetchTask(id)
                  .then((data) => applyTaskData(data))
                  .catch((e) => {
                    if (e instanceof ApiError && e.isNotFound) {
                      setNotFound(true);
                      setLoadError(null);
                      return;
                    }
                    setLoadError(
                      e instanceof ApiError
                        ? `${e.message} (HTTP ${e.status}${e.code ? `, code=${e.code}` : ""})`
                        : "Request failed",
                    );
                  })
                  .finally(() => setLoading(false));
              }}
              className="btn-primary"
            >
              Повторить
            </button>
            <Link href={backHref} className="btn-ghost">
              {backLabel}
            </Link>
          </div>
        </div>
      );
    }
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-center">
          <p className="text-lg font-medium text-surface-500">
            {notFound ? "Задача не найдена" : "Не удалось открыть задачу"}
          </p>
          <Link href={backHref} className="mt-2 text-primary-600 hover:underline">{backLabel}</Link>
        </div>
      </div>
    );
  }

  const availableTransitions = TRANSITIONS[task.status] ?? [];
  const completedItems = task.checklists.flatMap((c) => c.items).filter((i) => i.is_completed).length;
  const totalItems = task.checklists.flatMap((c) => c.items).length;
  const workerNames = Array.isArray(task.custom_fields?.["worker_equipment_names"])
    ? (task.custom_fields["worker_equipment_names"] as unknown[])
      .map((v) => String(v).trim())
      .filter(Boolean)
    : [];
  const extraEquipmentNames = Array.isArray(task.custom_fields?.["extra_equipment_names"])
    ? (task.custom_fields["extra_equipment_names"] as unknown[])
      .map((v) => String(v).trim())
      .filter(Boolean)
    : [];
  const vehicleMileageByEquipmentRaw = task.custom_fields?.["vehicle_mileage_by_equipment"];
  const vehicleMileagePairs = vehicleMileageByEquipmentRaw && typeof vehicleMileageByEquipmentRaw === "object"
    ? Object.entries(vehicleMileageByEquipmentRaw as Record<string, unknown>)
      .map(([equipmentId, km]) => ({ equipmentId, km: Number(km) }))
      .filter((row) => Number.isFinite(row.km) && row.km > 0)
    : [];
  const totalVehicleMileageKm = Number(task.custom_fields?.["vehicle_mileage_total_km"] ?? 0);
  const hasFieldWorkMeta =
    workerNames.length > 0 ||
    extraEquipmentNames.length > 0 ||
    vehicleMileagePairs.length > 0 ||
    (Number.isFinite(totalVehicleMileageKm) && totalVehicleMileageKm > 0);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 lg:p-6">
      {/* Back */}
      <Link href={backHref} className="inline-flex items-center gap-1 text-sm text-surface-500 hover:text-surface-900">
        <ArrowLeft className="h-4 w-4" /> {backLabel}
      </Link>

      {deleteError && (
        <div
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
          role="alert"
        >
          <span>Не удалось удалить задачу: {deleteError}</span>
          <button
            type="button"
            onClick={() => setDeleteError(null)}
            className="btn-ghost btn-sm shrink-0"
          >
            Закрыть
          </button>
        </div>
      )}

      {/* Header */}
      <div className="card p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          <div className="min-w-0 flex-1">
            {editing ? (
              <div className="space-y-3">
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="input text-xl font-bold"
                />
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  className="input min-h-[60px] resize-y text-sm"
                  placeholder="Описание задачи"
                  rows={3}
                />
                <select
                  value={editPriority}
                  onChange={(e) => setEditPriority(e.target.value)}
                  className="input max-w-[160px]"
                >
                  <option value="low">Низкий</option>
                  <option value="medium">Средний</option>
                  <option value="high">Высокий</option>
                  <option value="critical">Критический</option>
                </select>
                <div>
                  <label className="mb-1 block text-xs font-medium text-surface-500">
                    Исполнитель
                  </label>
                  <select
                    value={editAssigneeId}
                    onChange={(e) => setEditAssigneeId(e.target.value)}
                    className="input max-w-xs"
                  >
                    <option value="">Не назначен</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-surface-500">
                    Постановщик
                  </label>
                  <select
                    value={editRequestedById}
                    onChange={(e) => setEditRequestedById(e.target.value)}
                    className="input max-w-xs"
                  >
                    <option value="">Как автор записи</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <span className="mb-1 block text-xs font-medium text-surface-500">
                    Соисполнители
                  </span>
                  <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-surface-200 p-2">
                    {users.map((u) => (
                      <label key={u.id} className="flex cursor-pointer items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={editCoAssigneeIds.includes(u.id)}
                          onChange={() =>
                            setEditCoAssigneeIds((prev) =>
                              prev.includes(u.id)
                                ? prev.filter((id) => id !== u.id)
                                : [...prev, u.id],
                            )
                          }
                          className="rounded border-surface-300"
                        />
                        <span>{u.full_name}</span>
                      </label>
                    ))}
                  </div>
                </div>

              <div>
                <span className="mb-1 block text-xs font-medium text-surface-500">
                  Наблюдатели
                </span>
                <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-surface-200 p-2">
                  {users.map((u) => (
                    <label key={u.id} className="flex cursor-pointer items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={editObserverIds.includes(u.id)}
                        onChange={() =>
                          setEditObserverIds((prev) =>
                            prev.includes(u.id)
                              ? prev.filter((id) => id !== u.id)
                              : [...prev, u.id],
                          )
                        }
                        className="rounded border-surface-300"
                      />
                      <span>{u.full_name}</span>
                    </label>
                  ))}
                </div>
              </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-surface-500">
                      Срок выполнения (due date)
                    </label>
                    <input
                      type="datetime-local"
                      value={editDueDate}
                      onChange={(e) => setEditDueDate(e.target.value)}
                      className="input w-full max-w-xs"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-surface-500">
                      Начало работ (started_at)
                    </label>
                    <input
                      type="datetime-local"
                      value={editStartedAt}
                      onChange={(e) => setEditStartedAt(e.target.value)}
                      className="input w-full max-w-xs"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-surface-500">
                      Завершение (completed_at)
                    </label>
                    <input
                      type="datetime-local"
                      value={editCompletedAt}
                      onChange={(e) => setEditCompletedAt(e.target.value)}
                      className="input w-full max-w-xs"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-surface-500">
                      Дедлайн SLA
                    </label>
                    <input
                      type="datetime-local"
                      value={editSlaDeadline}
                      onChange={(e) => setEditSlaDeadline(e.target.value)}
                      className="input w-full max-w-xs"
                    />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-surface-500">
                    Геолокация задачи
                  </label>
                  <YandexTaskLocationPicker
                    address={editAddress}
                    latitude={editLatitude}
                    longitude={editLongitude}
                    onAddressChange={setEditAddress}
                    onLatitudeChange={setEditLatitude}
                    onLongitudeChange={setEditLongitude}
                  />
                </div>
                <p className="text-xs text-surface-400">
                  Очистите поле даты и сохраните, чтобы сбросить значение в системе.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={handleSaveEdit}
                    disabled={saving || !editTitle.trim()}
                    className="btn-primary gap-1.5"
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Сохранить
                  </button>
                  <button onClick={cancelEdit} className="btn-ghost gap-1.5">
                    <X className="h-4 w-4" /> Отмена
                  </button>
                </div>
              </div>
            ) : (
              <>
                <h1 className="text-xl font-bold lg:text-2xl">{task.title}</h1>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className={`badge ${statusColor[task.status] ?? "bg-surface-100 text-surface-600"}`}>
                    {formatEnumLabel(task.status, statusLabel)}
                  </span>
                  <span className={`badge border ${priorityColor[task.priority] ?? ""}`}>
                    {formatEnumLabel(task.priority, priorityLabel)}
                  </span>
                </div>
                <div className="mt-3 flex flex-col gap-2 text-sm text-surface-600">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <User className="h-4 w-4 shrink-0 text-surface-400" />
                    <strong className="text-surface-500">Исполнитель:</strong>
                    {task.assignee ? task.assignee.full_name : "Не назначен"}
                  </span>
                  <span className="flex flex-wrap items-center gap-1.5">
                    <User className="h-4 w-4 shrink-0 text-surface-400" />
                    <strong className="text-surface-500">Постановщик:</strong>
                    {task.requester?.full_name ?? "—"}
                  </span>
                  <span className="flex flex-wrap items-start gap-1.5">
                    <User className="mt-0.5 h-4 w-4 shrink-0 text-surface-400" />
                    <span>
                      <strong className="text-surface-500">Соисполнители:</strong>{" "}
                      {(task.co_assignees ?? []).length > 0
                        ? (task.co_assignees ?? []).map((c) => c.full_name).join(", ")
                        : "—"}
                    </span>
                  </span>

                  <span className="flex flex-wrap items-start gap-1.5">
                    <User className="mt-0.5 h-4 w-4 shrink-0 text-surface-400" />
                    <span>
                      <strong className="text-surface-500">Наблюдатели:</strong>{" "}
                      {(task.observers ?? []).length > 0
                        ? (task.observers ?? []).map((c) => c.full_name).join(", ")
                        : "—"}
                    </span>
                  </span>
                </div>
                <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
                  <div className="flex flex-col gap-0.5 rounded-lg bg-surface-50 px-3 py-2">
                    <dt className="text-xs font-medium text-surface-500">Срок выполнения</dt>
                    <dd className="text-surface-800">{formatTaskDate(task.due_date)}</dd>
                  </div>
                  <div className="flex flex-col gap-0.5 rounded-lg bg-surface-50 px-3 py-2">
                    <dt className="text-xs font-medium text-surface-500">Начало работ</dt>
                    <dd className="text-surface-800">{formatTaskDate(task.started_at)}</dd>
                  </div>
                  <div className="flex flex-col gap-0.5 rounded-lg bg-surface-50 px-3 py-2">
                    <dt className="text-xs font-medium text-surface-500">Завершение</dt>
                    <dd className="text-surface-800">{formatTaskDate(task.completed_at)}</dd>
                  </div>
                  <div className="flex flex-col gap-0.5 rounded-lg bg-surface-50 px-3 py-2">
                    <dt className="text-xs font-medium text-surface-500">SLA</dt>
                    <dd className="text-surface-800">{formatTaskDate(task.sla_deadline)}</dd>
                  </div>
                  <div className="flex flex-col gap-0.5 rounded-lg bg-surface-50 px-3 py-2 sm:col-span-2">
                    <dt className="text-xs font-medium text-surface-500">Геолокация</dt>
                    <dd className="text-surface-800">
                      {task.address || "—"}
                      {task.latitude !== null && task.latitude !== undefined && task.longitude !== null && task.longitude !== undefined
                        ? ` (${task.latitude}, ${task.longitude})`
                        : ""}
                    </dd>
                  </div>
                </dl>
                {hasFieldWorkMeta && (
                  <div className="mt-4 rounded-lg border border-primary-100 bg-primary-50/40 p-3">
                    <h3 className="text-sm font-semibold text-primary-800">Поля выездных работ</h3>
                    <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
                      <div className="rounded bg-white/70 px-2.5 py-2">
                        <dt className="text-xs font-medium text-surface-500">Рабочие/бригады</dt>
                        <dd className="text-surface-800">{workerNames.length > 0 ? workerNames.join(", ") : "—"}</dd>
                      </div>
                      <div className="rounded bg-white/70 px-2.5 py-2">
                        <dt className="text-xs font-medium text-surface-500">Доп. техника</dt>
                        <dd className="text-surface-800">{extraEquipmentNames.length > 0 ? extraEquipmentNames.join(", ") : "—"}</dd>
                      </div>
                      <div className="rounded bg-white/70 px-2.5 py-2 sm:col-span-2">
                        <dt className="text-xs font-medium text-surface-500">Пробег транспорта</dt>
                        <dd className="text-surface-800">
                          {vehicleMileagePairs.length > 0
                            ? vehicleMileagePairs.map((row) => `${row.km.toFixed(1)} км`).join(", ")
                            : "—"}
                          {Number.isFinite(totalVehicleMileageKm) && totalVehicleMileageKm > 0
                            ? ` (итого ${totalVehicleMileageKm.toFixed(1)} км)`
                            : ""}
                        </dd>
                      </div>
                    </dl>
                  </div>
                )}
              </>
            )}
          </div>

          {!editing && (
            <div className="flex shrink-0 flex-wrap gap-2 sm:flex-col sm:items-end">
              {/* Action buttons row */}
              <div className="flex flex-wrap gap-2">
                {!isTerminal(task.status) && (
                  <button
                    disabled={transitioning}
                    onClick={handleQuickComplete}
                    className="btn-primary gap-1.5 bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-500"
                    title="Завершить задачу одним кликом"
                  >
                    {transitioning
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <CheckCircle2 className="h-3.5 w-3.5" />}
                    Завершить
                  </button>
                )}
                {availableTransitions.map((t) => (
                  <button
                    key={t}
                    disabled={transitioning}
                    onClick={() => handleTransition(t)}
                    className="btn-primary gap-1.5"
                  >
                    {transitioning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                    {formatEnumLabel(t, statusLabel)}
                  </button>
                ))}
              </div>
              {/* Edit / Delete icons */}
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setEditing(true)}
                  className="btn-ghost gap-1.5"
                  title="Редактировать"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="btn-ghost text-red-500 hover:bg-red-50 gap-1.5"
                  title="Удалить"
                >
                  {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Description (read-only when not editing) */}
        {!editing && task.description && (
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
                  Чек-листы
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
                        <span className="badge bg-green-50 text-green-700">Выполнен</span>
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
          <div className="card">
            <div className="border-b border-surface-100 p-4">
              <h2 className="flex items-center gap-2 font-semibold">
                <Paperclip className="h-4 w-4 text-primary-500" /> Документы
                <span className="text-sm font-normal text-surface-400">{task.documents.length}</span>
              </h2>
            </div>
            {task.documents.length > 0 && (
              <div className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-2">
                {task.documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center gap-3 rounded-lg border border-surface-100 p-3"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-100">
                      {doc.mime_type.startsWith("image/") ? (
                        <Image className="h-5 w-5 text-violet-400" />
                      ) : (
                        <FileText className="h-5 w-5 text-blue-400" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-surface-700 truncate">{doc.filename}</p>
                      <p className="text-[10px] text-surface-400">{(doc.file_size / 1024).toFixed(0)} KB</p>
                    </div>
                    <button
                      onClick={async () => {
                        try {
                          const { url } = await getDocumentDownloadUrl(doc.id);
                          window.open(url, "_blank");
                        } catch { /* silent */ }
                      }}
                      className="rounded p-1.5 text-surface-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
                      title="Скачать"
                    >
                      <Paperclip className="h-4 w-4" />
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          await deleteDocument(doc.id);
                          const updated = await fetchTask(task.id);
                          setTask(updated);
                        } catch { /* silent */ }
                      }}
                      className="rounded p-1.5 text-surface-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                      title="Удалить"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="border-t border-surface-100 p-4">
              <FileUpload
                accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.zip"
                maxFiles={5}
                onFilesAdded={async (entries: FileEntry[]) => {
                  for (const entry of entries) {
                    try {
                      await uploadDocument(entry.file, task.id, "other");
                    } catch { /* silent */ }
                  }
                  const updated = await fetchTask(task.id);
                  setTask(updated);
                }}
              />
            </div>
          </div>

          {/* Materials & tools (main column) */}
          <div className="card">
            <div className="flex items-center justify-between border-b border-surface-100 p-4">
              <h2 className="flex items-center gap-2 font-semibold">
                <Package className="h-4 w-4 text-primary-500" />
                Материалы и инструмент
                <span className="text-sm font-normal text-surface-400">{taskMovements.length}</span>
              </h2>
              <button
                type="button"
                onClick={() => {
                  setMaterialError(null);
                  setSelectedItemId("");
                  setMaterialQty("");
                  setMaterialsOpen(true);
                }}
                className="btn-ghost btn-sm text-primary-600"
              >
                Добавить
              </button>
            </div>
            {taskMovements.length > 0 ? (
              <ul className="divide-y divide-surface-50 p-4">
                {taskMovements.map((mov) => (
                  <li key={mov.id} className="flex items-center justify-between py-2 text-sm">
                    <span className="text-surface-700">
                      {mov.item_name ?? mov.item_id} — {mov.quantity} (тип: {mov.movement_type})
                    </span>
                    <span className="text-surface-400 text-xs">
                      {new Date(mov.created_at).toLocaleDateString("ru-RU")}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-4 text-sm text-surface-500">
                Списания со склада по задаче пока не добавлены. Нажмите «Добавить», чтобы привязать материалы или инструмент.
                Списания, привязанные к задаче, учитываются в отчётах по складу.
              </p>
            )}
          </div>

          {/* Time Entries */}
          {task.time_entries.length > 0 && (
            <div className="card">
              <div className="border-b border-surface-100 p-4">
                <h2 className="flex items-center gap-2 font-semibold">
                  <Clock className="h-4 w-4 text-primary-500" /> Записи времени
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
                      {Math.floor(entry.duration_minutes / 60)}ч {entry.duration_minutes % 60}м
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Comments */}
          <div className="card">
            <div className="border-b border-surface-100 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="flex items-center gap-2 font-semibold">
                  <MessageSquare className="h-4 w-4 text-primary-500" /> Комментарии
                  <span className="text-sm font-normal text-surface-400">{task.comments.length}</span>
                </h2>
                {taskChatRoom ? (
                  <Link
                    href={`/chat?room=${encodeURIComponent(taskChatRoom.code)}&show_archived=1`}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary-600 hover:underline"
                  >
                    Чат задачи
                    {taskChatRoom.is_archived ? " (архив)" : ""}
                  </Link>
                ) : (
                  <span className="text-xs text-surface-400">
                    Чат задачи появится после первого комментария
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-3 bg-surface-50/50 p-3 sm:p-4">
              {task.comments.map((comment) => {
                const isMine =
                  currentUserId !== null && String(comment.author_id) === String(currentUserId);
                const label =
                  (comment.author_name && comment.author_name.trim()) ||
                  commentAuthorNameById.get(String(comment.author_id)) ||
                  "Участник";
                const initials = (label === "Участник" ? "?" : label).charAt(0).toUpperCase();
                return (
                  <div key={comment.id} className={cn("flex gap-2", isMine && "flex-row-reverse")}>
                    <div
                      className={cn(
                        "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                        isMine ? "bg-primary-600 text-white" : "bg-surface-200 text-surface-700",
                      )}
                      aria-hidden
                    >
                      {initials}
                    </div>
                    <div className={cn("min-w-0 max-w-[min(100%,36rem)]", isMine && "flex flex-col items-end")}>
                      <div
                        className={cn(
                          "flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs",
                          isMine && "flex-row-reverse justify-end",
                        )}
                      >
                        <span className="font-semibold text-surface-800">{label}</span>
                        <span className="text-surface-400">
                          {new Date(comment.created_at).toLocaleString("ru-RU", {
                            day: "2-digit",
                            month: "2-digit",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      {(comment.body ||
                        (Array.isArray(comment.attachments) && comment.attachments.length > 0)) && (
                        <div
                          className={cn(
                            "mt-1 w-full rounded-2xl px-3 py-2 text-left text-sm text-surface-800 shadow-sm",
                            isMine
                              ? "rounded-tr-sm bg-primary-100 text-surface-900"
                              : "rounded-tl-sm border border-surface-100 bg-white",
                          )}
                        >
                          {comment.body ? (
                            <p className="whitespace-pre-wrap break-words">{comment.body}</p>
                          ) : null}

                          {Array.isArray(comment.attachments) && comment.attachments.length > 0 ? (
                            <div className={cn("space-y-2", comment.body ? "mt-2" : "")}>
                              {(comment.attachments as unknown[])
                                .map((a) => String(a))
                                .filter(Boolean)
                                .map((docId) => {
                                  const doc = documentById.get(docId);
                                  if (!doc) return null;

                                  const downloadUrl = docUrls[docId];
                                  const filename = doc.filename;
                                  const isImage = doc.mime_type?.startsWith("image/");
                                  const isAudio = doc.mime_type?.startsWith("audio/");

                                  if (isImage) {
                                    if (!downloadUrl) {
                                      return (
                                        <div
                                          key={docId}
                                          className="rounded-lg border border-surface-100 p-3 text-xs text-surface-500"
                                        >
                                          {filename} (loading...)
                                        </div>
                                      );
                                    }
                                    return (
                                      <img
                                        key={docId}
                                        src={downloadUrl}
                                        alt={filename}
                                        className="mt-1 max-h-[220px] w-full cursor-zoom-in rounded-lg border border-surface-100 bg-white/20 object-contain"
                                        onClick={() => setImagePreview({ src: downloadUrl, alt: filename })}
                                      />
                                    );
                                  }

                                  if (isAudio) {
                                    if (!downloadUrl) {
                                      return (
                                        <div
                                          key={docId}
                                          className="rounded-lg border border-surface-100 p-3 text-xs text-surface-500"
                                        >
                                          {filename} (loading...)
                                        </div>
                                      );
                                    }
                                    return (
                                      <div
                                        key={docId}
                                        className="rounded-lg border border-surface-100 bg-white/40 p-3"
                                      >
                                        <p className="mb-1 truncate text-xs text-surface-600">{filename}</p>
                                        <audio controls src={downloadUrl} className="w-full" />
                                      </div>
                                    );
                                  }

                                  return (
                                    <div
                                      key={docId}
                                      className="flex items-center justify-between rounded-lg border border-surface-100 bg-white/40 p-3"
                                    >
                                      <div className="min-w-0">
                                        <p className="truncate text-xs font-medium text-surface-700">{filename}</p>
                                        <p className="text-[10px] text-surface-400">{doc.mime_type}</p>
                                      </div>
                                      <button
                                        type="button"
                                        onClick={async () => {
                                          try {
                                            const { url } = await getDocumentDownloadUrl(docId);
                                            window.open(url, "_blank");
                                          } catch {
                                            /* silent */
                                          }
                                        }}
                                        className="rounded p-1.5 text-surface-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
                                        title="Скачать"
                                      >
                                        <Paperclip className="h-4 w-4" />
                                      </button>
                                    </div>
                                  );
                                })}
                            </div>
                          ) : null}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
              {task.comments.length === 0 && (
                <p className="py-6 text-center text-sm text-surface-400">Комментариев пока нет</p>
              )}
            </div>
            <div className="border-t border-surface-100 p-4">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAddComment();
                }}
                className="space-y-2"
              >
                <div className="flex items-center gap-2">
                  <input
                    ref={commentInputRef}
                    type="text"
                    value={commentText}
                    onChange={(e) => setCommentText(e.target.value)}
                    placeholder="Написать комментарий..."
                    className="input"
                    disabled={submittingComment}
                  />

                  <label
                    className="btn-ghost shrink-0 p-2 text-surface-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                    title="Прикрепить файл"
                  >
                    <Paperclip className="h-4 w-4" />
                    <input
                      type="file"
                      className="hidden"
                      accept="image/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.zip"
                      multiple
                      disabled={submittingComment || commentRecording}
                      onChange={(e) => {
                        const files = Array.from(e.target.files ?? []);
                        if (files.length === 0) return;
                        const maxFiles = 5;
                        const remaining = Math.max(0, maxFiles - pendingCommentFiles.length);
                        if (remaining === 0) return;
                        setPendingCommentFiles((prev) => [...prev, ...files.slice(0, remaining)]);
                        e.currentTarget.value = "";
                      }}
                    />
                  </label>

                  <button
                    type="button"
                    disabled={submittingComment}
                    onClick={() => {
                      if (commentRecording) stopVoiceRecording();
                      else startVoiceRecording();
                    }}
                    className="btn-ghost shrink-0 p-2 text-surface-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                    title={commentRecording ? "Остановить запись" : "Записать голос"}
                  >
                    {commentRecording ? <StopCircle className="h-4 w-4 text-red-500" /> : <Mic className="h-4 w-4" />}
                  </button>

                  <button
                    type="submit"
                    disabled={submittingComment || commentRecording || (!commentText.trim() && pendingCommentFiles.length === 0)}
                    className="btn-primary shrink-0 px-3"
                    title="Отправить"
                  >
                    {submittingComment ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </div>

                {commentMediaError && (
                  <p className="text-xs text-red-500">{commentMediaError}</p>
                )}

                {pendingCommentFiles.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {pendingCommentFiles.map((f, idx) => (
                      <div
                        key={`${f.name}-${idx}`}
                        className="flex items-center gap-2 rounded-lg border border-surface-100 bg-white/40 px-2 py-1"
                      >
                        <span className="max-w-[220px] truncate text-xs text-surface-600">{f.name}</span>
                        <button
                          type="button"
                          className="rounded p-1 text-surface-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                          title="Убрать"
                          onClick={() => {
                            setPendingCommentFiles((prev) => prev.filter((_, i) => i !== idx));
                          }}
                          disabled={submittingComment}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </form>
            </div>
          </div>
        </div>

        {/* Sidebar — activity only (materials live in the main column) */}
        <div className="space-y-4 lg:col-span-2">
          <div className="card sticky top-6">
            <div className="border-b border-surface-100 p-4">
              <h2 className="font-semibold">Активность</h2>
            </div>
            <div className="max-h-[min(50vh,28rem)] overflow-y-auto p-4">
              {task.status_history.length === 0 ? (
                <p className="text-sm text-surface-400">Активности пока нет</p>
              ) : (
                <div className="relative space-y-4 pl-5 before:absolute before:left-[7px] before:top-2 before:h-[calc(100%-16px)] before:w-0.5 before:bg-surface-100">
                  {[...task.status_history].reverse().map((entry) => (
                    <div key={entry.id} className="relative">
                      <div className="absolute -left-5 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-primary-400" />
                      <div className="rounded-lg bg-surface-50 p-3">
                        <div className="flex items-center gap-1 text-xs">
                          <span className={`badge ${statusColor[entry.from_status] ?? "bg-surface-100 text-surface-600"}`}>
                            {formatEnumLabel(entry.from_status, statusLabel)}
                          </span>
                          <ChevronRight className="h-3 w-3 text-surface-400" />
                          <span className={`badge ${statusColor[entry.to_status] ?? "bg-surface-100 text-surface-600"}`}>
                            {formatEnumLabel(entry.to_status, statusLabel)}
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
      {imagePreview && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4"
          onClick={() => setImagePreview(null)}
        >
          <div
            className="relative max-h-[92vh] max-w-[92vw]"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="absolute -top-2 -right-2 z-[101] inline-flex h-9 w-9 items-center justify-center rounded-full bg-black/70 text-white hover:bg-black"
              onClick={() => setImagePreview(null)}
              title="Закрыть"
            >
              <X className="h-4 w-4" />
            </button>
            <img
              className="max-h-[92vh] max-w-[92vw] rounded-lg object-contain bg-black"
              src={imagePreview.src}
              alt={imagePreview.alt}
            />
          </div>
        </div>
      )}
      {/* Materials modal */}
      {materialsOpen && (
        <Modal
          open={materialsOpen}
          onClose={() => setMaterialsOpen(false)}
          title="Добавить материалы / инструмент"
          className="sm:max-w-lg"
          footer={
            <>
              <button
                type="button"
                onClick={() => setMaterialsOpen(false)}
                disabled={materialSubmitting}
                className="btn-ghost"
              >
                Отмена
              </button>
              <button
                type="button"
                disabled={materialSubmitting || !selectedItemId || !materialQty}
                onClick={async () => {
                  if (!task) return;
                  setMaterialSubmitting(true);
                  setMaterialError(null);
                  try {
                    const qty = Number(materialQty.replace(",", "."));
                    if (!Number.isFinite(qty) || qty <= 0) {
                      setMaterialError("Введите корректное количество");
                    } else {
                      await createWarehouseMovement({
                        item_id: selectedItemId,
                        movement_type: "consumption",
                        quantity: qty,
                        task_id: task.id,
                        reason: "Списание материалов по задаче",
                      });
                      const res = await fetchWarehouseMovements({ task_id: task.id, limit: 100 });
                      setTaskMovements(res.items);
                      setMaterialsOpen(false);
                    }
                  } catch (e) {
                    setMaterialError(
                      e instanceof ApiError ? e.message : "Не удалось создать списание",
                    );
                  } finally {
                    setMaterialSubmitting(false);
                  }
                }}
                className="btn-primary gap-1.5"
              >
                {materialSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                Списать
              </button>
            </>
          }
        >
          <div className="space-y-4">
            {materialError && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
                {materialError}
              </div>
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">
                Позиция склада
              </label>
              <select
                className="input"
                value={selectedItemId}
                onChange={(e) => setSelectedItemId(e.target.value)}
              >
                <option value="">Не выбрана</option>
                {warehouseItems.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name} ({w.sku}) — остаток {w.quantity} {w.unit}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">
                Количество
              </label>
              <input
                type="number"
                min="0"
                step="0.001"
                value={materialQty}
                onChange={(e) => setMaterialQty(e.target.value)}
                className="input"
                placeholder="Например, 1 или 2.5"
              />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

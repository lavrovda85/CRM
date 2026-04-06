"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  ExternalLink,
  FileText,
  Image,
  LayoutDashboard,
  ListTodo,
  Loader2,
  Mic,
  MessageSquare,
  Package,
  Paperclip,
  Send,
  StopCircle,
  Table2,
  Trash2,
  TrendingUp,
  CheckSquare,
  Clock,
  Receipt,
  X,
  Plus,
  Save,
  ListChecks,
  Calculator,
} from "lucide-react";

import type {
  TenderDetailResponse,
  TenderChecklistItemResponse,
  DocumentResponse,
  TaskResponse,
  TenderStatus,
  TenderAnalysisState,
  TenderSmetaCalculationState,
} from "@/types";
import {
  ApiError,
  fetchTender,
  fetchUsers,
  transitionTender,
  toggleTenderChecklistItem,
  updateTenderChecklistItem,
  uploadDocument,
  getDocumentDownloadUrl,
  deleteDocument,
  deleteTender,
  addTenderComment,
  retryTenderAnalysis,
  calculateTenderSmeta,
  createTenderEstimatorTask,
  patchTenderBillOfWorks,
  createTasksFromBill,
  type UserListItem,
} from "@/lib/api";
import {
  TENDER_MAIN_PIPELINE,
  TENDER_STATUS_LABELS,
  tenderStatusLabel,
} from "@/lib/tenderPipeline";
import { FileUpload, type FileEntry } from "@/components/file-upload/FileUpload";
import { Modal } from "@/components/ui/Modal";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

function formatMoney(v: string | number | null) {
  if (v == null) return "-";
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  return `₽${n.toLocaleString("ru-RU")}`;
}

function formatDateTime(iso: string | null | undefined) {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("ru-RU");
}

function SmetaRowEstimatesTable({
  smeta,
  formatMoney: fmt,
}: {
  smeta: TenderSmetaCalculationState;
  formatMoney: (v: string | number | null) => string;
}) {
  const estimates = smeta.row_estimates ?? [];
  const slice = estimates.slice(0, 40);
  let rowSum = 0;
  for (const row of slice) {
    const r = row as Record<string, unknown>;
    const lt = r.line_total_rub;
    if (lt != null && Number.isFinite(Number(lt))) rowSum += Number(lt);
  }
  const direct = smeta.estimated_direct_cost_rub;
  const sumMismatch =
    direct != null &&
    Number.isFinite(Number(direct)) &&
    rowSum > 0 &&
    Math.abs(rowSum - Number(direct)) / Math.max(Number(direct), 1) > 0.05;

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-lg border border-surface-100">
        <table className="min-w-full text-xs">
          <thead className="bg-surface-50">
            <tr>
              <th className="px-2 py-1.5 text-left">Позиция</th>
              <th className="px-2 py-1.5 text-right whitespace-nowrap">Кол-во</th>
              <th className="px-2 py-1.5 text-left">Ед.</th>
              <th className="px-2 py-1.5 text-right whitespace-nowrap">Цена за ед.</th>
              <th className="px-2 py-1.5 text-right whitespace-nowrap">Сумма строки</th>
              <th className="px-2 py-1.5 text-left">Заметка</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((row, i) => {
              const r = row as Record<string, unknown>;
              return (
                <tr key={i} className="border-t border-surface-100">
                  <td className="px-2 py-1.5">{String(r.name ?? r.position ?? "—")}</td>
                  <td className="px-2 py-1.5 text-right">{r.quantity != null ? String(r.quantity) : "—"}</td>
                  <td className="px-2 py-1.5">{String(r.unit ?? "—")}</td>
                  <td className="px-2 py-1.5 text-right">
                    {r.unit_cost_assumption_rub != null ? fmt(Number(r.unit_cost_assumption_rub)) : "—"}
                  </td>
                  <td className="px-2 py-1.5 text-right font-medium">
                    {r.line_total_rub != null ? fmt(Number(r.line_total_rub)) : "—"}
                  </td>
                  <td className="px-2 py-1.5 text-surface-600">{String(r.notes_ru ?? "")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-surface-600">
        Сумма по строкам: <span className="font-medium text-surface-900">{fmt(rowSum)}</span>
        {direct != null && (
          <>
            {" "}
            · прямые затраты (оценка): <span className="font-medium text-surface-900">{fmt(direct)}</span>
          </>
        )}
        {sumMismatch && (
          <span className="ml-2 text-amber-800">
            Заметное расхождение — перезапустите расчёт; сервер сводит строки к итогам.
          </span>
        )}
      </p>
    </div>
  );
}

type TenderTabId = "overview" | "analysis" | "bill" | "workflow" | "files" | "comments";

type BillWorkRow = NonNullable<TenderAnalysisState["bill_of_works"]>[number];

function emptyBillRow(): BillWorkRow {
  return { position: "", name: "", unit: "", quantity: "", remarks: "" };
}

function billToCsvBlob(rows: BillWorkRow[], tenderTitle: string): Blob {
  const sep = ";";
  const esc = (s: string) => {
    const t = String(s ?? "");
    if (/[";\n\r]/.test(t)) return `"${t.replace(/"/g, '""')}"`;
    return t;
  };
  const header = ["№", "Наименование", "Ед.изм.", "Кол-во", "Примечание"].map(esc).join(sep);
  const dataLines = rows.map((r) =>
    [r.position ?? "", r.name ?? "", r.unit ?? "", r.quantity ?? "", r.remarks ?? ""].map(esc).join(sep),
  );
  const lines = [`Ведомость работ — ${tenderTitle}`, header, ...dataLines];
  const bom = "\uFEFF";
  return new Blob([bom + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
}

const TENDER_TABS: { id: TenderTabId; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { id: "overview", label: "Обзор", icon: LayoutDashboard },
  { id: "analysis", label: "Риски и рентабельность", icon: AlertTriangle },
  { id: "bill", label: "Ведомость работ", icon: Table2 },
  { id: "workflow", label: "Чеклист и задачи", icon: ListTodo },
  { id: "files", label: "Документы", icon: Paperclip },
  { id: "comments", label: "Комментарии", icon: MessageSquare },
];

function recommendationLabel(v: string | undefined) {
  const s = (v || "").toLowerCase();
  if (s === "go") return "Рекомендуется участие";
  if (s === "no_go") return "Участие не рекомендуется";
  return "Осторожно / оцените риски";
}

function recommendationBadgeClass(v: string | undefined) {
  const s = (v || "").toLowerCase();
  if (s === "go") return "bg-emerald-100 text-emerald-800";
  if (s === "no_go") return "bg-red-100 text-red-800";
  return "bg-amber-100 text-amber-800";
}

const EXTRACTION_SKIP_HINTS: Record<string, string> = {
  archive_not_unpacked: "архив не удалось разобрать",
  archive_empty_or_unreadable: "архив пустой или повреждён",
  archive_no_supported_text: "в архиве нет читаемых PDF/DOCX/XLSX с текстом",
  archive_rar_tool_missing: "RAR: в образе нет unrar — добавьте PDF/DOCX отдельно или используйте ZIP",
  archive_7z_tool_missing: "7z недоступен (py7zr) — проверьте зависимости сервера",
  legacy_doc_not_supported_use_docx: "старый .doc не читается — сохраните как .docx",
  image_no_ocr: "изображение без OCR",
  html_not_extracted: "HTML не разбирается",
  no_text_layer_or_empty_extract: "нет текстового слоя или пусто",
};

const ZAKUPKI_LABELS: Record<string, string> = {
  subject: "Предмет",
  customer: "Заказчик",
  nmck: "НМЦК (текст)",
  procedure_type: "Способ закупки",
  purchase_id: "ИКЗ",
  placement_date: "Дата размещения",
  contact_person: "Контактное лицо",
  phones: "Телефоны",
  emails: "E-mail",
  fax: "Факс",
  customer_inn: "ИНН заказчика",
  customer_address: "Адрес заказчика",
  delivery_place: "Место поставки",
  etp_name: "ЭТП",
  bid_security: "Обеспечение заявки",
  contract_security: "Обеспечение контракта",
  okpd2_line: "ОКПД2",
  notice_card_url: "Карточка на zakupki",
  documents_url: "Документы (из импорта)",
  submission_deadline_utc: "Срок подачи (UTC, импорт)",
};

function zakupkiEntries(z: unknown): [string, string][] {
  if (!z || typeof z !== "object") return [];
  const out: [string, string][] = [];
  for (const [k, v] of Object.entries(z as Record<string, unknown>)) {
    if (v == null || v === "") continue;
    if (typeof v === "object") continue;
    const label = ZAKUPKI_LABELS[k] ?? k;
    out.push([label, String(v)]);
  }
  return out;
}

export default function TenderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  const [tender, setTender] = useState<TenderDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [documentsBusy, setDocumentsBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [tenderDeleting, setTenderDeleting] = useState(false);
  const [tenderDeleteError, setTenderDeleteError] = useState<string | null>(null);
  const [pipelineBusy, setPipelineBusy] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  const [commentText, setCommentText] = useState("");
  const [submittingComment, setSubmittingComment] = useState(false);
  const [pendingCommentFiles, setPendingCommentFiles] = useState<File[]>([]);
  const [commentRecording, setCommentRecording] = useState(false);
  const [commentMediaError, setCommentMediaError] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<{ src: string; alt: string } | null>(null);
  const [docUrls, setDocUrls] = useState<Record<string, string>>({});

  const [tab, setTab] = useState<TenderTabId>("overview");
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [estimatorBusy, setEstimatorBusy] = useState(false);
  const [estimatorModalOpen, setEstimatorModalOpen] = useState(false);
  const [estimatorUsers, setEstimatorUsers] = useState<UserListItem[]>([]);
  const [estimatorUsersLoading, setEstimatorUsersLoading] = useState(false);
  const [estAssignee, setEstAssignee] = useState("");
  const [estDescription, setEstDescription] = useState("");
  const [estAttachCsv, setEstAttachCsv] = useState(true);
  const [bulkTasksModalOpen, setBulkTasksModalOpen] = useState(false);
  const [bulkAssignee, setBulkAssignee] = useState("");
  const [bulkTasksBusy, setBulkTasksBusy] = useState(false);
  const [billRows, setBillRows] = useState<BillWorkRow[]>([]);
  const [billNotesEdit, setBillNotesEdit] = useState("");
  const [billSaving, setBillSaving] = useState(false);
  const [smetaBusy, setSmetaBusy] = useState(false);
  const [tenderActionError, setTenderActionError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const voiceChunksRef = useRef<BlobPart[]>([]);

  const loadTender = useCallback(async () => {
    setLoadError(null);
    setNotFound(false);
    setTender(null);
    setLoading(true);
    try {
      const data = await fetchTender(id);
      setTender(data);
    } catch (e) {
      if (e instanceof ApiError && e.isNotFound) {
        setNotFound(true);
        return;
      }
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Request failed";
      setLoadError(msg);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadTender().catch(() => {});
  }, [loadTender]);

  const mainChecklist = useMemo(() => {
    if (!tender?.checklists?.length) return null;
    return tender.checklists[0];
  }, [tender]);

  const calculationItem = useMemo(() => {
    const items = mainChecklist?.items ?? [];
    return items.find((i) => i.item_type === "calculation") ?? null;
  }, [mainChecklist]);

  const tasksForCalculation: TaskResponse[] = tender?.tasks ?? [];

  const tradeStart = tender?.trade_start_at ? new Date(tender.trade_start_at) : null;
  const hoursUntilTrade = tradeStart
    ? (tradeStart.getTime() - Date.now()) / (1000 * 60 * 60)
    : null;

  const analysis = (tender?.tender_analysis ?? {}) as TenderAnalysisState;
  const smeta = (analysis.smeta_calculation ?? {}) as TenderSmetaCalculationState;

  useEffect(() => {
    if (!tender) return;
    const a = tender.tender_analysis ?? {};
    const rows = a.bill_of_works;
    if (Array.isArray(rows) && rows.length > 0) {
      setBillRows(rows.map((r) => ({ ...r })));
    } else {
      setBillRows([]);
    }
    setBillNotesEdit(typeof a.bill_of_works_notes === "string" ? a.bill_of_works_notes : "");
  }, [tender?.id, tender?.updated_at]);

  useEffect(() => {
    if (!estimatorModalOpen && !bulkTasksModalOpen) return;
    let cancelled = false;
    setEstimatorUsersLoading(true);
    fetchUsers({ is_active: true, limit: 200 })
      .then((res) => {
        if (!cancelled) setEstimatorUsers(res.items);
      })
      .catch(() => {
        if (!cancelled) setEstimatorUsers([]);
      })
      .finally(() => {
        if (!cancelled) setEstimatorUsersLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [estimatorModalOpen, bulkTasksModalOpen]);

  const zakupkiPairs = useMemo(() => {
    const z =
      tender?.requirements &&
      typeof tender.requirements === "object" &&
      tender.requirements !== null &&
      "zakupki" in tender.requirements
        ? (tender.requirements as { zakupki?: unknown }).zakupki
        : undefined;
    return zakupkiEntries(z);
  }, [tender?.requirements]);

  const tradeTone = hoursUntilTrade == null ? null : hoursUntilTrade <= 2 ? "danger" : hoursUntilTrade <= 24 ? "warning" : null;

  const documentById = useMemo(() => {
    const map = new Map<string, DocumentResponse>();
    if (!tender) return map;
    for (const d of tender.documents) map.set(d.id, d);
    return map;
  }, [tender]);

  const commentAttachmentIds = useMemo(() => {
    if (!tender) return [];
    const ids: string[] = [];
    for (const c of tender.comments ?? []) {
      const raw = (c.attachments ?? []) as unknown[];
      for (const a of raw) {
        if (a !== null && a !== undefined && String(a).trim()) ids.push(String(a));
      }
    }
    return Array.from(new Set(ids));
  }, [tender]);

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
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [attachmentImageOrAudioIdsToFetch.join("|")]);

  async function refreshAfterChecklistAction() {
    try {
      const data = await fetchTender(id);
      setTender(data);
    } catch {
      // keep stale UI
    }
  }

  async function handlePipelineTransition(toStatus: TenderStatus) {
    if (!tender || pipelineBusy) return;
    setPipelineError(null);
    setPipelineBusy(true);
    try {
      await transitionTender(tender.id, toStatus);
      const full = await fetchTender(id);
      setTender(full);
    } catch (e) {
      setPipelineError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка перехода по пайплайну",
      );
    } finally {
      setPipelineBusy(false);
    }
  }

  async function handleRetryAnalysis() {
    if (!tender || analysisBusy) return;
    setTenderActionError(null);
    setAnalysisBusy(true);
    try {
      await retryTenderAnalysis(tender.id);
      await loadTender();
    } catch (e) {
      setTenderActionError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось запустить анализ",
      );
    } finally {
      setAnalysisBusy(false);
    }
  }

  function openEstimatorModal() {
    setEstDescription("");
    setEstAttachCsv(true);
    setEstimatorModalOpen(true);
  }

  async function handleSaveBillOfWorks() {
    if (!tender || billSaving) return;
    setTenderActionError(null);
    setBillSaving(true);
    try {
      const cleaned = billRows
        .filter((r) => (r.name ?? "").trim().length > 0)
        .map((r) => ({
          position: (r.position ?? "").trim(),
          name: (r.name ?? "").trim(),
          unit: (r.unit ?? "").trim(),
          quantity: (r.quantity ?? "").trim(),
          remarks: (r.remarks ?? "").trim(),
        }));
      await patchTenderBillOfWorks(tender.id, {
        bill_of_works: cleaned,
        bill_of_works_notes: billNotesEdit.trim() || null,
      });
      await loadTender();
    } catch (e) {
      setTenderActionError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось сохранить ведомость",
      );
    } finally {
      setBillSaving(false);
    }
  }

  async function handleSubmitEstimatorModal() {
    if (!tender || estimatorBusy) return;
    setTenderActionError(null);
    setEstimatorBusy(true);
    try {
      const ids: string[] = [];
      if (estAttachCsv) {
        const rowsForFile = billRows.filter((r) => (r.name ?? "").trim().length > 0);
        if (rowsForFile.length > 0) {
          const blob = billToCsvBlob(rowsForFile, tender.title);
          const file = new File([blob], `vedomost-${tender.id.slice(0, 8)}.csv`, {
            type: "text/csv;charset=utf-8",
          });
          const doc = await uploadDocument(
            file,
            undefined,
            "other",
            "Ведомость работ (CRM)",
            tender.id,
          );
          ids.push(doc.id);
        }
      }
      await createTenderEstimatorTask(tender.id, {
        assigned_to: estAssignee || null,
        description: estDescription.trim() || null,
        attachment_document_ids: ids.length ? ids : undefined,
      });
      setEstimatorModalOpen(false);
      await loadTender();
    } catch (e) {
      setTenderActionError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось создать задачу",
      );
    } finally {
      setEstimatorBusy(false);
    }
  }

  async function handleCalculateSmeta() {
    if (!tender || smetaBusy) return;
    setTenderActionError(null);
    setSmetaBusy(true);
    try {
      await calculateTenderSmeta(tender.id);
      await loadTender();
    } catch (e) {
      setTenderActionError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось запустить расчёт сметы",
      );
    } finally {
      setSmetaBusy(false);
    }
  }

  async function handleBulkTasksFromBill() {
    if (!tender || bulkTasksBusy || billSaving) return;
    const valid = billRows.filter((r) => (r.name ?? "").trim().length > 0);
    if (valid.length === 0) {
      setTenderActionError("Нет строк с заполненным наименованием.");
      return;
    }
    setTenderActionError(null);
    setBulkTasksBusy(true);
    try {
      await handleSaveBillOfWorks();
      await createTasksFromBill(tender.id, {
        assigned_to: bulkAssignee || null,
        row_indices: null,
      });
      setBulkTasksModalOpen(false);
      await loadTender();
    } catch (e) {
      setTenderActionError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось создать задачи",
      );
    } finally {
      setBulkTasksBusy(false);
    }
  }

  async function handleDeleteTender() {
    if (tenderDeleting) return;
    if (!confirm("Удалить тендер?")) return;
    setTenderDeleteError(null);
    setTenderDeleting(true);
    try {
      await deleteTender(id);
      router.replace("/tenders");
    } catch (e) {
      setTenderDeleteError(
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка удаления тендера",
      );
    } finally {
      setTenderDeleting(false);
    }
  }

  async function handleToggleChecklist(item: TenderChecklistItemResponse) {
    if (!tender) return;
    try {
      await toggleTenderChecklistItem(tender.id, item.id);
      await refreshAfterChecklistAction();
    } catch {
      // silent
    }
  }

  async function handleLinkCalculationTask(item: TenderChecklistItemResponse, taskId: string | null) {
    if (!tender) return;
    try {
      await updateTenderChecklistItem(tender.id, item.id, { calculation_task_id: taskId });
      await refreshAfterChecklistAction();
    } catch {
      // silent
    }
  }

  async function handleAddTenderComment() {
    if (!tender || submittingComment) return;
    if (!commentText.trim() && pendingCommentFiles.length === 0) return;
    setSubmittingComment(true);

    try {
      const attachmentDocIds: string[] = [];
      for (const file of pendingCommentFiles) {
        const uploaded = await uploadDocument(file, undefined, "other", undefined, tender.id);
        attachmentDocIds.push(uploaded.id);
      }

      await addTenderComment(tender.id, commentText.trim(), [], attachmentDocIds);

      setCommentText("");
      setPendingCommentFiles([]);
      setCommentMediaError(null);
      await refreshAfterChecklistAction();
    } catch {
      // silent
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
          // silent
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

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl space-y-6 p-4 lg:p-6">
        <Skeleton className="h-10 w-60" />
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (!tender) {
    if (loadError) {
      return (
        <div className="mx-auto max-w-lg space-y-4 p-6 text-center">
          <p className="text-lg font-medium text-surface-700">Ошибка загрузки тендера</p>
          <p className="text-sm text-surface-500">{loadError}</p>
          <div className="flex flex-wrap justify-center gap-2">
            <button type="button" onClick={() => loadTender()} className="btn-primary">
              Повторить
            </button>
            <Link href="/tenders" className="btn-ghost">
              Назад
            </Link>
          </div>
        </div>
      );
    }
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-center">
          <p className="text-lg font-medium text-surface-500">{notFound ? "Тендер не найден" : "Не удалось открыть тендер"}</p>
          <Link href="/tenders" className="mt-2 text-primary-600 hover:underline">
            Назад к тендерам
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
    <div className="mx-auto max-w-6xl space-y-6 p-4 lg:p-6">
      <Link
        href="/tenders"
        className="inline-flex items-center gap-1 text-sm text-surface-500 hover:text-surface-900"
      >
        <ArrowLeft className="h-4 w-4" /> Назад к тендерам
      </Link>

      {tradeTone === "danger" && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Срочные торги: осталось {Math.max(0, Math.round(hoursUntilTrade!))}ч
        </div>
      )}
      {tradeTone === "warning" && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Скоро торги: осталось {Math.max(0, Math.round(hoursUntilTrade!))}ч
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-b border-surface-200 pb-3">
        {TENDER_TABS.map(({ id: tid, label, icon: Icon }) => (
          <button
            key={tid}
            type="button"
            onClick={() => setTab(tid)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              tab === tid
                ? "bg-primary-600 text-white shadow-sm"
                : "bg-surface-100 text-surface-600 hover:bg-surface-200"
            }`}
          >
            <Icon className="h-4 w-4 shrink-0 opacity-90" />
            {label}
          </button>
        ))}
      </div>

      {tenderActionError && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">
          {tenderActionError}
        </div>
      )}

      {tab === "overview" && (
        <>
      <div className="card p-4">
        <h2 className="text-sm font-semibold text-surface-800">Пайплайн тендера</h2>
        <p className="mt-1 text-xs text-surface-500">
          От поиска до завершения. Допустимые переходы проверяются на сервере.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-y-2">
          {TENDER_MAIN_PIPELINE.map((stage, i) => {
            const mainIdx =
              tender.status === "lost"
                ? -1
                : TENDER_MAIN_PIPELINE.indexOf(tender.status as TenderStatus);
            const done = mainIdx >= 0 && i < mainIdx;
            const current = tender.status === stage;
            return (
              <div key={stage} className="flex items-center">
                {i > 0 && <span className="mx-1.5 text-surface-300 select-none">→</span>}
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    current
                      ? "bg-primary-600 text-white"
                      : done
                        ? "bg-green-100 text-green-800"
                        : "bg-surface-100 text-surface-500"
                  }`}
                >
                  {TENDER_STATUS_LABELS[stage]}
                </span>
              </div>
            );
          })}
          {tender.status === "lost" && (
            <span className="ml-2 rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-800">
              Проигран
            </span>
          )}
        </div>
        {pipelineError && (
          <p className="mt-2 text-sm text-red-600" role="alert">
            {pipelineError}
          </p>
        )}
        {(tender.allowed_next_statuses?.length ?? 0) > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-surface-100 pt-4">
            <span className="w-full text-xs font-medium text-surface-600">Следующий шаг:</span>
            {tender.allowed_next_statuses!.map((s) => (
              <button
                key={s}
                type="button"
                disabled={pipelineBusy}
                className="btn-secondary inline-flex items-center gap-2 text-sm"
                onClick={() => handlePipelineTransition(s as TenderStatus)}
              >
                {pipelineBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                → {tenderStatusLabel(s)}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold lg:text-2xl">{tender.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-surface-600">
              {tender.customer_name && (
                <span className="flex items-center gap-1">
                  <Receipt className="h-4 w-4 text-surface-400" />
                  {tender.customer_name}
                </span>
              )}
              {tender.trade_start_at && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-4 w-4 text-surface-400" />
                  {new Date(tender.trade_start_at).toLocaleString("ru-RU")}
                </span>
              )}
              {tender.trade_end_at && (
                <span className="flex items-center gap-1">
                  <Clock className="h-4 w-4 text-surface-400" />
                  до {new Date(tender.trade_end_at).toLocaleString("ru-RU")}
                </span>
              )}
            </div>

            {tender.tender_link && (
              <div className="mt-2">
                <a
                  href={tender.tender_link}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-primary-600 hover:underline"
                >
                  Ссылка на тендер
                </a>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <span className={`badge ${tradeTone === "danger" ? "bg-red-50 text-red-700" : tradeTone === "warning" ? "bg-amber-50 text-amber-700" : "bg-surface-100 text-surface-600"}`}>
              {tenderStatusLabel(tender.status)}
            </span>

            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleDeleteTender().catch(() => {});
              }}
              className="rounded bg-surface-100 px-2 py-1 text-surface-500 hover:text-red-500 hover:bg-red-50 transition-colors"
              title="Удалить тендер"
              disabled={tenderDeleting}
            >
              {tenderDeleting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {tenderDeleteError && (
          <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {tenderDeleteError}
          </div>
        )}

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-lg bg-surface-50 p-3 text-sm">
            <div className="text-xs text-surface-500">Гарантийная сумма</div>
            <div className="font-semibold">{formatMoney(tender.guarantee_amount)}</div>
          </div>
          <div className="rounded-lg bg-surface-50 p-3 text-sm">
            <div className="text-xs text-surface-500">Максимальная цена</div>
            <div className="font-semibold">{formatMoney(tender.max_price)}</div>
          </div>
          <div className="rounded-lg bg-surface-50 p-3 text-sm">
            <div className="text-xs text-surface-500">Себестоимость (минимальная)</div>
            <div className="font-semibold">{formatMoney(tender.min_price)}</div>
          </div>
        </div>

        {(tender.description?.trim() ||
          tender.notes?.trim() ||
          tender.documents_url ||
          tender.deadline ||
          tender.execution_deadline ||
          (tender.budget != null && Number.isFinite(Number(tender.budget))) ||
          zakupkiPairs.length > 0) && (
          <div className="mt-4 border-t border-surface-100 pt-4">
            <h3 className="text-sm font-semibold text-surface-800">Данные закупки (импорт)</h3>
            <div className="mt-3 grid gap-4 lg:grid-cols-2">
              <dl className="space-y-2 text-sm">
                {tender.deadline && (
                  <div>
                    <dt className="text-xs text-surface-500">Срок подачи заявок</dt>
                    <dd className="font-medium text-surface-800">{formatDateTime(tender.deadline)}</dd>
                  </div>
                )}
                {tender.execution_deadline && (
                  <div>
                    <dt className="text-xs text-surface-500">Срок исполнения контракта</dt>
                    <dd className="font-medium text-surface-800">{formatDateTime(tender.execution_deadline)}</dd>
                  </div>
                )}
                {tender.budget != null && Number.isFinite(Number(tender.budget)) && (
                  <div>
                    <dt className="text-xs text-surface-500">
                      {tender.max_price == null ? "НМЦК / бюджет (из источника)" : "Бюджет (из источника)"}
                    </dt>
                    <dd className="font-medium text-surface-800">{formatMoney(tender.budget)}</dd>
                  </div>
                )}
                {tender.documents_url && (
                  <div>
                    <dt className="text-xs text-surface-500">Документация на ЕИС</dt>
                    <dd>
                      <a
                        href={tender.documents_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-medium text-primary-600 hover:underline"
                      >
                        Открыть раздел документов
                        <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                      </a>
                    </dd>
                  </div>
                )}
              </dl>
              {zakupkiPairs.length > 0 && (
                <dl className="space-y-2 rounded-lg bg-surface-50 p-3 text-sm">
                  {zakupkiPairs
                    .filter(([label, val]) => {
                      if (label === "Документы (из импорта)" && tender.documents_url && val === tender.documents_url) {
                        return false;
                      }
                      return true;
                    })
                    .map(([label, val]) => (
                      <div key={label}>
                        <dt className="text-xs text-surface-500">{label}</dt>
                        <dd className="break-words font-medium text-surface-800">
                          {label === "Карточка на zakupki" || val.startsWith("http") ? (
                            <a
                              href={val}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-primary-600 hover:underline"
                            >
                              {val.length > 80 ? `${val.slice(0, 80)}…` : val}
                              <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                            </a>
                          ) : (
                            val
                          )}
                        </dd>
                      </div>
                    ))}
                </dl>
              )}
            </div>
            {tender.description?.trim() && (
              <div className="mt-4">
                <div className="text-xs font-medium text-surface-500">Описание</div>
                <p className="mt-1 whitespace-pre-wrap text-sm text-surface-700">{tender.description}</p>
              </div>
            )}
            {tender.notes?.trim() && (
              <div className="mt-4">
                <div className="text-xs font-medium text-surface-500">Заметки и контакты</div>
                <p className="mt-1 whitespace-pre-wrap text-sm text-surface-700">{tender.notes}</p>
              </div>
            )}
          </div>
        )}
      </div>
        </>
      )}

      {tab === "analysis" && (
        <div className="card p-5 space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-surface-900">Подводные камни и рентабельность</h2>
              <p className="mt-1 text-sm text-surface-500">
                Автоанализ загруженных документов (PDF, DOCX, XLSX). Обновите при добавлении файлов.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2 text-sm"
                disabled={analysisBusy}
                onClick={() => handleRetryAnalysis().catch(() => {})}
              >
                {analysisBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Повторить анализ
              </button>
              <button
                type="button"
                className="btn-primary inline-flex items-center gap-2 text-sm"
                disabled={estimatorBusy}
                onClick={() => openEstimatorModal()}
              >
                {estimatorBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Задача сметчику
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-surface-500">Статус анализа:</span>
            <span className="rounded-full bg-surface-100 px-2 py-0.5 font-medium text-surface-800">
              {analysis.status ?? "—"}
            </span>
            {analysis.stage_label && (
              <span className="text-surface-500">
                ({analysis.stage_label}
                {analysis.updated_at ? ` · ${formatDateTime(analysis.updated_at)}` : ""})
              </span>
            )}
          </div>

          {(analysis.documents_total != null || (analysis.document_extraction_report?.length ?? 0) > 0) && (
            <div className="rounded-lg border border-surface-100 bg-surface-50/90 p-3 text-xs text-surface-600">
              <p className="font-semibold text-surface-800">Что ушло в автоматический анализ</p>
              <p className="mt-1 leading-relaxed">
                Файлов в тендере: <strong>{analysis.documents_total ?? "—"}</strong> · С извлечённым текстом:{" "}
                <strong>{analysis.documents_with_extracted_text ?? "—"}</strong> · Символов в запросе к ИИ:{" "}
                <strong>{analysis.text_chars_used ?? "—"}</strong>
                {analysis.max_text_per_document != null && (
                  <> (до {analysis.max_text_per_document.toLocaleString("ru-RU")} симв. на файл, общий лимит 120 000)</>
                )}
              </p>
              {analysis.document_extraction_report && analysis.document_extraction_report.length > 0 && (
                <ul className="mt-2 max-h-44 space-y-1 overflow-y-auto text-[11px] leading-snug">
                  {analysis.document_extraction_report.map((r) => (
                    <li key={r.document_id} className="flex flex-wrap gap-x-1 border-b border-surface-100/80 py-0.5 last:border-0">
                      <span className="max-w-[min(100%,280px)] truncate font-medium text-surface-800" title={r.filename}>
                        {r.filename}
                      </span>
                      <span className="text-surface-500">
                        {r.chars_extracted > 0 ? (
                          <>— {r.chars_extracted.toLocaleString("ru-RU")} симв.</>
                        ) : (
                          <>
                            —{" "}
                            <span className="text-amber-800">
                              0 симв.: {EXTRACTION_SKIP_HINTS[r.skip_note ?? ""] ?? r.skip_note ?? "нет текста"}
                            </span>
                          </>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {analysis.status === "failed" && analysis.error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              {String(analysis.error)}
            </div>
          )}

          <div
            className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${recommendationBadgeClass(
              analysis.participation_recommendation,
            )}`}
          >
            {recommendationLabel(analysis.participation_recommendation)}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-surface-100 bg-surface-50/80 p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-surface-800">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                Подводные камни и риски
              </h3>
              <div className="mt-2 whitespace-pre-wrap text-sm text-surface-700">
                {analysis.pitfalls_and_risks?.trim() || "Нет данных — дождитесь завершения анализа или загрузите документы."}
              </div>
            </div>
            <div className="rounded-lg border border-surface-100 bg-surface-50/80 p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-surface-800">
                <TrendingUp className="h-4 w-4 text-emerald-600" />
                Рентабельность
              </h3>
              <div className="mt-2 whitespace-pre-wrap text-sm text-surface-700">
                {analysis.profitability_assessment?.trim() || "Нет данных — дождитесь завершения анализа или загрузите документы."}
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "bill" && (
        <div className="card p-5 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-surface-900">Ведомость работ</h2>
              <p className="mt-1 text-sm text-surface-500">
                Редактируйте таблицу и сохраните. Из ИИ: при необходимости — задачи по строкам или сметчику с
                файлом ведомости.
                {analysis.bill_of_works_confidence && (
                  <span className="ml-1 font-medium text-surface-700">
                    Уверенность: {analysis.bill_of_works_confidence}
                  </span>
                )}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2 text-sm"
                disabled={billSaving || bulkTasksBusy}
                onClick={() => handleSaveBillOfWorks().catch(() => {})}
              >
                {billSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Сохранить
              </button>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2 text-sm"
                disabled={bulkTasksBusy || billSaving || billRows.filter((r) => (r.name ?? "").trim()).length === 0}
                onClick={() => setBulkTasksModalOpen(true)}
              >
                <ListChecks className="h-4 w-4" />
                Задачи по строкам
              </button>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2 text-sm"
                disabled={
                  smetaBusy ||
                  billSaving ||
                  billRows.filter((r) => (r.name ?? "").trim()).length === 0
                }
                title="В расчёт идёт ведомость, сохранённая на сервере (нажмите «Сохранить» при правках)."
                onClick={() => handleCalculateSmeta().catch(() => {})}
              >
                {smetaBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Calculator className="h-4 w-4" />}
                Рассчитать смету
              </button>
              <button
                type="button"
                className="btn-primary inline-flex items-center gap-2 text-sm"
                disabled={estimatorBusy}
                onClick={() => openEstimatorModal()}
              >
                {estimatorBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Задача сметчику
              </button>
            </div>
          </div>
          {analysis.bill_of_works_manual_edit_at && (
            <p className="text-xs text-surface-500">
              Последнее сохранение вручную: {formatDateTime(analysis.bill_of_works_manual_edit_at)}
            </p>
          )}
          <div>
            <label className="text-xs font-medium text-surface-500">Примечания к ведомости</label>
            <textarea
              className="mt-1 w-full rounded-lg border border-surface-200 px-3 py-2 text-sm"
              rows={2}
              value={billNotesEdit}
              onChange={(e) => setBillNotesEdit(e.target.value)}
              placeholder="Комментарий для сметчика или себя…"
            />
          </div>
          {billRows.length === 0 ? (
            <div className="space-y-3">
              <p className="text-sm text-surface-500">
                Позиции не извлечены. Загрузите ведомость в «Документы», повторите анализ или добавьте строки вручную.
              </p>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2 text-sm"
                onClick={() => setBillRows([emptyBillRow()])}
              >
                <Plus className="h-4 w-4" />
                Добавить строку
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="overflow-x-auto rounded-lg border border-surface-100">
                <table className="min-w-full divide-y divide-surface-100 text-sm">
                  <thead className="bg-surface-50">
                    <tr>
                      <th className="px-2 py-2 text-left font-medium text-surface-600">№</th>
                      <th className="px-2 py-2 text-left font-medium text-surface-600">Наименование</th>
                      <th className="px-2 py-2 text-left font-medium text-surface-600">Ед.</th>
                      <th className="px-2 py-2 text-left font-medium text-surface-600">Кол-во</th>
                      <th className="px-2 py-2 text-left font-medium text-surface-600">Примечание</th>
                      <th className="w-10 px-1 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-50">
                    {billRows.map((row, idx) => (
                      <tr key={idx} className="hover:bg-surface-50/80">
                        <td className="p-1">
                          <input
                            className="w-full min-w-[3rem] rounded border border-transparent bg-transparent px-1 py-1 text-sm hover:border-surface-200 focus:border-primary-400"
                            value={row.position ?? ""}
                            onChange={(e) => {
                              const v = e.target.value;
                              setBillRows((prev) =>
                                prev.map((r, i) => (i === idx ? { ...r, position: v } : r)),
                              );
                            }}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            className="w-full min-w-[12rem] rounded border border-transparent bg-transparent px-1 py-1 text-sm hover:border-surface-200 focus:border-primary-400"
                            value={row.name ?? ""}
                            onChange={(e) => {
                              const v = e.target.value;
                              setBillRows((prev) =>
                                prev.map((r, i) => (i === idx ? { ...r, name: v } : r)),
                              );
                            }}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            className="w-full min-w-[4rem] rounded border border-transparent bg-transparent px-1 py-1 text-sm hover:border-surface-200 focus:border-primary-400"
                            value={row.unit ?? ""}
                            onChange={(e) => {
                              const v = e.target.value;
                              setBillRows((prev) =>
                                prev.map((r, i) => (i === idx ? { ...r, unit: v } : r)),
                              );
                            }}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            className="w-full min-w-[4rem] rounded border border-transparent bg-transparent px-1 py-1 text-sm hover:border-surface-200 focus:border-primary-400"
                            value={row.quantity ?? ""}
                            onChange={(e) => {
                              const v = e.target.value;
                              setBillRows((prev) =>
                                prev.map((r, i) => (i === idx ? { ...r, quantity: v } : r)),
                              );
                            }}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            className="w-full min-w-[8rem] rounded border border-transparent bg-transparent px-1 py-1 text-sm hover:border-surface-200 focus:border-primary-400"
                            value={row.remarks ?? ""}
                            onChange={(e) => {
                              const v = e.target.value;
                              setBillRows((prev) =>
                                prev.map((r, i) => (i === idx ? { ...r, remarks: v } : r)),
                              );
                            }}
                          />
                        </td>
                        <td className="p-1 text-center">
                          <button
                            type="button"
                            className="rounded p-1 text-surface-400 hover:bg-red-50 hover:text-red-600"
                            title="Удалить строку"
                            onClick={() => setBillRows((prev) => prev.filter((_, i) => i !== idx))}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2 text-sm"
                onClick={() => setBillRows((prev) => [...prev, emptyBillRow()])}
              >
                <Plus className="h-4 w-4" />
                Строка
              </button>
            </div>
          )}

          <div className="border-t border-surface-100 pt-4 space-y-3">
            <h3 className="text-sm font-semibold text-surface-900">Индикативный сметный расчёт</h3>
            <p className="text-xs text-surface-500">
              Очередь воркера (как анализ документов). Опирается на ведомость на сервере и опциональный контекст ФГИС
              ЦС из настроек бэкенда; цифры ориентировочные.
            </p>
            {(smeta.status === "running" || smeta.status === "pending") && (
              <p className="flex items-center gap-2 text-sm text-surface-600">
                <Loader2 className="h-4 w-4 animate-spin" />
                Расчёт выполняется…
              </p>
            )}
            {smeta.status === "failed" && smeta.error && (
              <p className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{smeta.error}</p>
            )}
            {smeta.disclaimer_ru?.trim() && (
              <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-950">{smeta.disclaimer_ru}</p>
            )}
            {(smeta.estimated_total_cost_rub != null ||
              smeta.suggested_minimum_bid_rub != null ||
              smeta.estimated_direct_cost_rub != null) && (
              <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                {smeta.estimated_direct_cost_rub != null && (
                  <div>
                    <dt className="text-surface-500">Прямые затраты (оценка)</dt>
                    <dd className="font-medium">{formatMoney(smeta.estimated_direct_cost_rub)}</dd>
                  </div>
                )}
                {smeta.estimated_total_cost_rub != null && (
                  <div>
                    <dt className="text-surface-500">Себестоимость (оценка)</dt>
                    <dd className="font-medium">{formatMoney(smeta.estimated_total_cost_rub)}</dd>
                  </div>
                )}
                {smeta.suggested_minimum_bid_rub != null && (
                  <div>
                    <dt className="text-surface-500">Нижняя граница заявки / торгов</dt>
                    <dd className="font-medium text-amber-900">{formatMoney(smeta.suggested_minimum_bid_rub)}</dd>
                  </div>
                )}
                {smeta.suggested_target_margin_pct != null && (
                  <div>
                    <dt className="text-surface-500">Целевая маржа (оценка), %</dt>
                    <dd className="font-medium">{String(smeta.suggested_target_margin_pct)}</dd>
                  </div>
                )}
              </dl>
            )}
            {smeta.methodology_note_ru?.trim() && (
              <p className="text-xs text-surface-600">
                <span className="font-medium">Методика: </span>
                {smeta.methodology_note_ru}
              </p>
            )}
            {smeta.profitability_summary_ru?.trim() && (
              <div className="whitespace-pre-wrap rounded-lg bg-surface-50 p-3 text-sm text-surface-800">
                {smeta.profitability_summary_ru}
              </div>
            )}
            {smeta.trade_negotiation_floor_ru?.trim() && (
              <div>
                <div className="text-xs font-medium text-surface-500">Торги и дисконт</div>
                <p className="mt-1 whitespace-pre-wrap text-sm text-surface-800">{smeta.trade_negotiation_floor_ru}</p>
              </div>
            )}
            {Array.isArray(smeta.row_estimates) && smeta.row_estimates.length > 0 && (
              <SmetaRowEstimatesTable smeta={smeta} formatMoney={formatMoney} />
            )}
            {smeta.updated_at && smeta.status === "completed" && (
              <p className="text-xs text-surface-400">Обновлено: {formatDateTime(smeta.updated_at)}</p>
            )}
          </div>
        </div>
      )}

      {tab === "workflow" && (
      <div className="space-y-6 max-w-4xl">
          {mainChecklist && (
            <div className="card">
              <div className="border-b border-surface-100 p-4">
                <h2 className="flex items-center gap-2 font-semibold">
                  <CheckSquare className="h-4 w-4 text-primary-500" />
                  {mainChecklist.title}
                </h2>
              </div>
              <div className="divide-y divide-surface-50">
                {mainChecklist.items.map((item) => {
                  const highlight =
                    !item.is_completed &&
                    item.item_type === "check_2h" &&
                    hoursUntilTrade != null &&
                    hoursUntilTrade <= 2
                      ? "bg-red-50 border-red-200"
                      : !item.is_completed &&
                          item.item_type === "check_1d" &&
                          hoursUntilTrade != null &&
                          hoursUntilTrade <= 24 &&
                          hoursUntilTrade > 2
                        ? "bg-amber-50 border-amber-200"
                        : "";

                  let dueText: string | null = null;
                  if (tender.trade_start_at) {
                    const startMs = new Date(tender.trade_start_at).getTime();
                    if (item.item_type === "check_1d") {
                      dueText = `Должно быть сделано до: ${new Date(startMs - 24 * 60 * 60 * 1000).toLocaleString("ru-RU")}`;
                    } else if (item.item_type === "check_2h") {
                      dueText = `Должно быть сделано до: ${new Date(startMs - 2 * 60 * 60 * 1000).toLocaleString("ru-RU")}`;
                    }
                  }

                  return (
                    <div key={item.id} className={`p-4 ${highlight}`}>
                      <label className="flex cursor-pointer items-start gap-3">
                        <input
                          type="checkbox"
                          checked={item.is_completed}
                          onChange={() => handleToggleChecklist(item)}
                          className="mt-1 h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium">{item.title}</div>
                          {dueText && <div className="mt-1 text-xs text-surface-500">{dueText}</div>}

                          {item.item_type === "calculation" && (
                            <div className="mt-3">
                              <div className="text-xs font-medium text-surface-500">Задача на расчет</div>
                              <select
                                className="input mt-1 w-full"
                                value={item.calculation_task_id ?? ""}
                                onChange={(e) => {
                                  const v = e.target.value;
                                  handleLinkCalculationTask(item, v ? v : null).catch(() => {});
                                }}
                              >
                                <option value="">Не связана</option>
                                {tasksForCalculation.map((t) => (
                                  <option key={t.id} value={t.id}>
                                    {t.title}
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}
                        </div>
                      </label>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="card">
            <div className="border-b border-surface-100 p-4">
              <h2 className="flex items-center gap-2 font-semibold">
                <Package className="h-4 w-4 text-primary-500" /> Привязанные задачи
              </h2>
            </div>
            <div className="p-4">
              {tender.tasks.length === 0 ? (
                <p className="text-sm text-surface-400">Задач пока нет</p>
              ) : (
                <div className="space-y-2">
                  {tender.tasks.map((t) => (
                    <div key={t.id} className="flex items-center justify-between rounded-lg border border-surface-100 px-3 py-2">
                      <Link href={`/tasks/${t.id}`} className="text-sm font-medium text-surface-700 hover:underline">
                        {t.title}
                      </Link>
                      <span className="badge bg-surface-100 text-surface-600">{t.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
      </div>
      )}

      {tab === "files" && (
          <div className="card">
            <div className="border-b border-surface-100 p-4">
              <h2 className="flex items-center gap-2 font-semibold">
                <Paperclip className="h-4 w-4 text-primary-500" /> Документы
                <span className="text-sm font-normal text-surface-400">{tender.documents.length}</span>
              </h2>
            </div>

            {tender.documents.length > 0 && (
              <div className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-2">
                {tender.documents.map((doc) => (
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
                        } catch {
                          // silent
                        }
                      }}
                      className="rounded p-1.5 text-surface-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
                      title="Скачать"
                    >
                      <Paperclip className="h-4 w-4" />
                    </button>
                    <button
                      onClick={async () => {
                        if (!confirm("Удалить документ?")) return;
                        setDeleteError(null);
                        try {
                          await deleteDocument(doc.id);
                          await refreshAfterChecklistAction();
                        } catch (e) {
                          setDeleteError(
                            e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка удаления",
                          );
                        }
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

            {deleteError && (
              <div className="px-4 pb-4">
                <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{deleteError}</div>
              </div>
            )}

            <div className="border-t border-surface-100 p-4">
              <FileUpload
                accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.zip"
                maxFiles={5}
                onFilesAdded={async (entries: FileEntry[]) => {
                  setDocumentsBusy(true);
                  setDeleteError(null);
                  try {
                    for (const entry of entries) {
                      await uploadDocument(entry.file, undefined, "other", undefined, id);
                    }
                    await refreshAfterChecklistAction();
                  } catch (e) {
                    setDeleteError(
                      e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось загрузить файл",
                    );
                  } finally {
                    setDocumentsBusy(false);
                  }
                }}
              />
            </div>
          </div>
      )}

      {tab === "comments" && (
          <div className="card">
            <div className="border-b border-surface-100 p-4">
              <h2 className="flex items-center gap-2 font-semibold">
                <MessageSquare className="h-4 w-4 text-primary-500" /> Комментарии
                <span className="text-sm font-normal text-surface-400">{(tender.comments ?? []).length}</span>
              </h2>
            </div>

            <div className="divide-y divide-surface-50">
              {(tender.comments ?? []).map((comment) => (
                <div key={comment.id} className="p-4">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-100 text-xs font-medium text-primary-700">
                      {(comment.author_name ?? "?").charAt(0)}
                    </div>
                    <span className="text-sm font-medium">{comment.author_name ?? "Неизвестный"}</span>
                    <span className="text-xs text-surface-400">
                      {new Date(comment.created_at).toLocaleString("ru-RU")}
                    </span>
                  </div>

                  {comment.body ? (
                    <p className="mt-2 text-sm text-surface-600 pl-9">{comment.body}</p>
                  ) : null}

                  {Array.isArray(comment.attachments) && comment.attachments.length > 0 ? (
                    <div className="mt-2 space-y-2 pl-9">
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
                                <div key={docId} className="rounded-lg border border-surface-100 p-3 text-xs text-surface-500">
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
                                <div key={docId} className="rounded-lg border border-surface-100 p-3 text-xs text-surface-500">
                                  {filename} (loading...)
                                </div>
                              );
                            }

                            return (
                              <div key={docId} className="rounded-lg border border-surface-100 bg-white/40 p-3">
                                <p className="mb-1 truncate text-xs text-surface-600">{filename}</p>
                                <audio controls src={downloadUrl} className="w-full" />
                              </div>
                            );
                          }

                          return (
                            <div key={docId} className="flex items-center justify-between rounded-lg border border-surface-100 bg-white/40 p-3">
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
                                    // silent
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
              ))}

              {(tender.comments ?? []).length === 0 && (
                <p className="p-6 text-center text-sm text-surface-400">Комментариев пока нет</p>
              )}
            </div>

            <div className="border-t border-surface-100 p-4">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAddTenderComment().catch(() => {});
                }}
                className="space-y-2"
              >
                <div className="flex items-center gap-2">
                  <input
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
                    {submittingComment ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  </button>
                </div>

                {commentMediaError && <p className="text-xs text-red-500">{commentMediaError}</p>}

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
      )}
    </div>

    <Modal
      open={estimatorModalOpen}
      onClose={() => {
        if (!estimatorBusy) setEstimatorModalOpen(false);
      }}
      title="Задача сметчику"
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className="btn-secondary text-sm"
            disabled={estimatorBusy}
            onClick={() => setEstimatorModalOpen(false)}
          >
            Отмена
          </button>
          <button
            type="button"
            className="btn-primary inline-flex items-center gap-2 text-sm"
            disabled={estimatorBusy}
            onClick={() => handleSubmitEstimatorModal().catch(() => {})}
          >
            {estimatorBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Создать
          </button>
        </div>
      }
    >
      <div className="space-y-3 text-sm text-surface-800">
        <div>
          <label className="text-xs font-medium text-surface-600">Исполнитель</label>
          <select
            className="mt-1 w-full rounded-lg border border-surface-200 px-3 py-2"
            value={estAssignee}
            onChange={(e) => setEstAssignee(e.target.value)}
            disabled={estimatorUsersLoading}
          >
            <option value="">— не назначен —</option>
            {estimatorUsers.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name || u.email}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-surface-600">Описание</label>
          <textarea
            className="mt-1 w-full rounded-lg border border-surface-200 px-3 py-2"
            rows={4}
            value={estDescription}
            onChange={(e) => setEstDescription(e.target.value)}
            placeholder="Дополнительно для сметчика…"
          />
        </div>
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="checkbox"
            className="mt-1"
            checked={estAttachCsv}
            onChange={(e) => setEstAttachCsv(e.target.checked)}
          />
          <span>
            Прикрепить ведомость файлом (CSV из текущей таблицы; при пустой таблице файл не создаётся)
          </span>
        </label>
      </div>
    </Modal>

    <Modal
      open={bulkTasksModalOpen}
      onClose={() => {
        if (!bulkTasksBusy) setBulkTasksModalOpen(false);
      }}
      title="Задачи по строкам ведомости"
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className="btn-secondary text-sm"
            disabled={bulkTasksBusy}
            onClick={() => setBulkTasksModalOpen(false)}
          >
            Отмена
          </button>
          <button
            type="button"
            className="btn-primary inline-flex items-center gap-2 text-sm"
            disabled={bulkTasksBusy || billSaving}
            onClick={() => handleBulkTasksFromBill().catch(() => {})}
          >
            {bulkTasksBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Создать задачи
          </button>
        </div>
      }
    >
      <p className="text-sm text-surface-600">
        Для каждой строки с непустым наименованием будет создана отдельная задача, привязанная к этому тендеру.
        Перед созданием ведомость будет сохранена на сервер.
      </p>
      <p className="mt-2 text-sm font-medium text-surface-800">
        Строк к задачам: {billRows.filter((r) => (r.name ?? "").trim().length > 0).length}
      </p>
      <div className="mt-3">
        <label className="text-xs font-medium text-surface-600">Исполнитель (по желанию)</label>
        <select
          className="mt-1 w-full rounded-lg border border-surface-200 px-3 py-2 text-sm"
          value={bulkAssignee}
          onChange={(e) => setBulkAssignee(e.target.value)}
          disabled={estimatorUsersLoading}
        >
          <option value="">— не назначен —</option>
          {estimatorUsers.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name || u.email}
            </option>
          ))}
        </select>
      </div>
    </Modal>

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
    </>
  );
}


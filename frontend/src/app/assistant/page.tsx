"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, CheckCircle2, FileSpreadsheet, Mic, Paperclip, Send, Sparkles, X } from "lucide-react";

import {
  fetchAiAssistantMessages,
  fetchAiAssistantStatus,
  postAiAssistantChat,
  importExcelUnified,
  ApiError,
  type AiAssistantStatus,
  type AiUploadContext,
  type ExcelUnifiedImportResponse,
} from "@/lib/api";
import { useAiAssistantStore } from "@/stores/aiAssistant";

function kindLabelRu(kind: string): string {
  const k = kind.toLowerCase();
  if (k === "image") return "изображение (vision)";
  if (k === "pdf") return "PDF";
  if (k === "docx") return "Word";
  if (k === "xlsx") return "Excel";
  if (k === "csv") return "CSV";
  if (k === "doc_legacy") return "устаревший формат";
  return kind;
}

function getSpeechRecognitionCtor(): (new () => SpeechRecognition) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognition;
    webkitSpeechRecognition?: new () => SpeechRecognition;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export default function AssistantPage() {
  const messages = useAiAssistantStore((s) => s.messages);
  const setFromServer = useAiAssistantStore((s) => s.setFromServer);
  const inputDraft = useAiAssistantStore((s) => s.inputDraft);
  const setInputDraft = useAiAssistantStore((s) => s.setInputDraft);

  const [status, setStatus] = useState<AiAssistantStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [uploadAck, setUploadAck] = useState<AiUploadContext | null>(null);
  const [excelImportBusy, setExcelImportBusy] = useState(false);
  const [excelImportResult, setExcelImportResult] = useState<ExcelUnifiedImportResponse | null>(null);
  const [excelImportError, setExcelImportError] = useState<string | null>(null);
  const excelInputRef = useRef<HTMLInputElement | null>(null);
  const attachmentsRef = useRef<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const recRef = useRef<SpeechRecognition | null>(null);
  const listEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAiAssistantStatus()
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch((e: unknown) => {
        if (!cancelled)
          setStatusError(e instanceof Error ? e.message : "Status failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setHistoryError(null);
    fetchAiAssistantMessages()
      .then((rows) => {
        if (!cancelled) {
          setFromServer(
            rows.map((r) => ({
              id: r.id,
              role: r.role,
              content: r.content,
              created_at: r.created_at,
            })),
          );
        }
      })
      .catch((e: unknown) => {
        if (!cancelled)
          setHistoryError(
            e instanceof Error ? e.message : "Failed to load chat history",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [setFromServer]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Keep an imperative ref for selected files to avoid race conditions
  // when user attaches a file and immediately hits "Send".
  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

  const send = useCallback(async () => {
    const text = useAiAssistantStore.getState().inputDraft.trim();
    const files = attachmentsRef.current;
    if ((!text && files.length === 0) || busy) return;
    setError(null);
    setBusy(true);

    const priorSnapshot = useAiAssistantStore.getState().messages;

    const fileLine =
      files.length > 0
        ? `[${files.length} файл(ов): ${files.map((f) => f.name).join(", ")}]`
        : "";
    const userLine = text ? (fileLine ? `${text}\n\n${fileLine}` : text) : fileLine;

    setFromServer([
      ...priorSnapshot,
      { role: "user", content: userLine, id: `local-${Date.now()}` },
    ]);
    setInputDraft("");

    try {
      const res = await postAiAssistantChat({ message: text, files: files.length ? files : undefined });
      setFromServer(
        res.messages.map((r) => ({
          id: r.id,
          role: r.role,
          content: r.content,
          created_at: r.created_at,
        })),
      );
      if (files.length > 0) {
        setUploadAck(res.upload_context ?? null);
      } else {
        setUploadAck(null);
      }
      setAttachments([]);
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        setError(
          e.code
            ? `${e.message} (HTTP ${e.status}, code=${e.code})`
            : `${e.message} (HTTP ${e.status})`,
        );
      } else {
        setError(e instanceof Error ? e.message : "Request failed");
      }
      setFromServer(priorSnapshot);
      setInputDraft(text);
      setAttachments(files);
    } finally {
      setBusy(false);
    }
  }, [busy, setFromServer, setInputDraft]);

  const toggleVoice = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setError("Speech recognition is not supported in this browser.");
      return;
    }
    if (listening && recRef.current) {
      recRef.current.stop();
      recRef.current = null;
      setListening(false);
      return;
    }
    const rec = new Ctor();
    rec.lang = "ru-RU";
    rec.continuous = false;
    rec.interimResults = false;
    rec.onresult = (ev: SpeechRecognitionEvent) => {
      const t = ev.results[0]?.[0]?.transcript?.trim();
      if (t) {
        const prev = useAiAssistantStore.getState().inputDraft;
        setInputDraft(prev ? `${prev} ${t}` : t);
      }
      setListening(false);
      recRef.current = null;
    };
    rec.onerror = () => {
      setListening(false);
      recRef.current = null;
    };
    rec.onend = () => {
      setListening(false);
      recRef.current = null;
    };
    recRef.current = rec;
    rec.start();
    setListening(true);
  }, [listening, setInputDraft]);

  const disabled = !status?.enabled;

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-4 p-4 md:p-8">
      <div className="flex items-start gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary-600 text-white shadow-sm">
          <Sparkles className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-surface-900">
            AI-ассистент CRM
          </h1>
          <p className="mt-1 text-sm text-surface-600">
            Текст, голос или вложения: PDF, Word (.docx), Excel (.xlsx), CSV и изображения сканов
            — ассистент разберёт ТЗ или ведомость работ и создаст задачи через CRM (в т.ч.{" "}
            <code className="rounded bg-surface-100 px-1">bulk_create_tasks</code>). История хранится
            на сервере до выхода.
          </p>
          {status && (
            <p className="mt-2 text-xs text-surface-500">
              Статус:{" "}
              {status.enabled ? (
                <>
                  включено · модель{" "}
                  <code className="rounded bg-surface-100 px-1">{status.model}</code>
                </>
              ) : (
                <span className="text-amber-700">
                  выключено — задайте{" "}
                  <code className="rounded bg-surface-100 px-1">OPENAI_API_KEY</code>{" "}
                  на бэкенде
                </span>
              )}
            </p>
          )}
          {statusError && (
            <p className="mt-1 text-xs text-red-600">{statusError}</p>
          )}
          {historyError && (
            <p className="mt-1 text-xs text-amber-700">{historyError}</p>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-surface-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <FileSpreadsheet className="h-5 w-5 text-primary-600" aria-hidden />
          <h2 className="text-sm font-semibold text-surface-900">Импорт Excel в CRM</h2>
        </div>
        <p className="mt-1 text-xs text-surface-600">
          Файлы вроде «База клиентов»: листы с колонками наименование / контакты / оборудование попадают в{" "}
          <strong>клиентов</strong>. Листы с артикулом и количеством — в{" "}
          <strong>склад</strong>. Можно также попросить ассистента вызвать инструмент{" "}
          <code className="rounded bg-surface-100 px-1">import_excel_workbook_base64</code> с подтверждением{" "}
          <code className="rounded bg-surface-100 px-1">__confirm: &quot;yes&quot;</code>.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            ref={excelInputRef}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={async (e) => {
              const f = e.currentTarget.files?.[0];
              e.currentTarget.value = "";
              if (!f) return;
              setExcelImportError(null);
              setExcelImportResult(null);
              setExcelImportBusy(true);
              try {
                const r = await importExcelUnified(f, false);
                setExcelImportResult(r);
              } catch (err) {
                setExcelImportError(
                  err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Ошибка импорта",
                );
              } finally {
                setExcelImportBusy(false);
              }
            }}
          />
          <button
            type="button"
            disabled={excelImportBusy || disabled}
            onClick={() => excelInputRef.current?.click()}
            className="btn-secondary btn-sm inline-flex items-center gap-1.5"
          >
            <FileSpreadsheet className="h-4 w-4" />
            {excelImportBusy ? "Импорт…" : "Выбрать .xlsx"}
          </button>
        </div>
        {excelImportError && (
          <p className="mt-2 text-xs text-red-600">{excelImportError}</p>
        )}
        {excelImportResult && (
          <div className="mt-2 rounded-lg border border-emerald-100 bg-emerald-50/80 px-3 py-2 text-xs text-emerald-950">
            <p>
              Клиентов создано: <strong>{excelImportResult.clients_created}</strong>, пропущено:{" "}
              {excelImportResult.clients_skipped}
              {" "}
              (пусто: {excelImportResult.clients_skipped_empty ?? 0}, дубликат:{" "}
              {excelImportResult.clients_skipped_duplicate ?? 0}, ошибка: {excelImportResult.clients_skipped_error ?? 0}
              ). Склад: +{excelImportResult.warehouse_created} новых, {excelImportResult.warehouse_updated} обновлено.
            </p>
            {excelImportResult.sheets.length > 0 && (
              <ul className="mt-1 list-inside list-disc text-emerald-900/90">
                {excelImportResult.sheets.map((s) => (
                  <li key={s.sheet_name}>
                    {s.sheet_name}: {s.kind}
                    {s.message ? ` — ${s.message}` : ""}
                  </li>
                ))}
              </ul>
            )}
            {excelImportResult.errors.length > 0 && (
              <ul className="mt-1 list-inside list-disc text-amber-900">
                {excelImportResult.errors.slice(0, 8).map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="flex min-h-[320px] flex-1 flex-col rounded-2xl border border-surface-200 bg-white shadow-sm">
        <div className="border-b border-surface-100 px-4 py-2 text-xs text-surface-500">
          <Bot className="mr-1 inline h-3.5 w-3.5" />
          Диалог
        </div>
        {uploadAck && (
          <div className="border-b border-emerald-200 bg-emerald-50/90 px-4 py-3 text-sm text-emerald-950">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2 font-medium">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-700" aria-hidden />
                <span>
                  {uploadAck.merged_into_model
                    ? "Вложения обработаны и переданы в контекст модели"
                    : "Результат обработки вложений"}
                </span>
              </div>
              <button
                type="button"
                className="shrink-0 rounded p-1 text-emerald-800 hover:bg-emerald-100"
                onClick={() => setUploadAck(null)}
                aria-label="Скрыть"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-1 text-xs text-emerald-900/80">
              Текст из документов:{" "}
              {uploadAck.total_document_text_chars != null
                ? `${uploadAck.total_document_text_chars.toLocaleString("ru-RU")} симв.`
                : "—"}
              {uploadAck.images_for_vision > 0
                ? ` · изображений для vision: ${uploadAck.images_for_vision}`
                : ""}
            </p>
            <ul className="mt-2 space-y-1 text-xs">
              {uploadAck.files.map((f, idx) => (
                <li key={`${f.name}-${idx}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="font-medium text-emerald-950">{f.name}</span>
                  <span className="text-emerald-800/90">
                    ({kindLabelRu(f.kind)})
                    {f.included_in_context ? (
                      <span className="ml-1 text-emerald-700">· в контексте</span>
                    ) : (
                      <span className="ml-1 text-amber-800">· не в контексте</span>
                    )}
                    {f.text_chars != null && f.text_chars > 0
                      ? ` · ${f.text_chars.toLocaleString("ru-RU")} симв. текста`
                      : ""}
                    {f.note ? ` · ${f.note}` : ""}
                  </span>
                </li>
              ))}
            </ul>
            {uploadAck.warnings.length > 0 && (
              <ul className="mt-2 list-inside list-disc text-xs text-amber-900">
                {uploadAck.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && (
            <p className="text-sm text-surface-500">
              Например: «Покажи последние задачи в работе», прикрепите таблицу или скан и напишите:
              «создай задачи по ведомости».
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={m.id ?? `msg-${i}-${m.role}`}
              className={
                m.role === "user"
                  ? "ml-auto max-w-[85%] rounded-2xl bg-primary-600 px-3 py-2 text-sm text-white"
                  : "mr-auto max-w-[85%] rounded-2xl bg-surface-100 px-3 py-2 text-sm text-surface-900 whitespace-pre-wrap"
              }
            >
              {m.content}
            </div>
          ))}
          <div ref={listEndRef} />
        </div>
        {error && (
          <div className="border-t border-red-100 bg-red-50 px-4 py-2 text-sm text-red-800">
            {error}
          </div>
        )}
        <div className="flex flex-col gap-2 border-t border-surface-100 p-3">
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {attachments.map((f, i) => (
                <span
                  key={`${f.name}-${i}`}
                  className="inline-flex max-w-full items-center gap-1 rounded-lg bg-surface-100 px-2 py-1 text-xs text-surface-700"
                >
                  <span className="truncate">{f.name}</span>
                  <button
                    type="button"
                    className="shrink-0 rounded p-0.5 hover:bg-surface-200"
                    onClick={() => setAttachments((prev) => prev.filter((_, j) => j !== i))}
                    aria-label="Убрать файл"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              multiple
              accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.tsv,image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp"
              onChange={(e) => {
                const list = e.currentTarget.files;
                if (!list?.length) return;
                setError(null);
                const prev = attachmentsRef.current;
                const next: File[] = [...prev];
                for (let i = 0; i < list.length; i += 1) {
                  const f = list[i];
                  if (next.length >= 12) break;
                  const name = (f.name || "").toLowerCase();
                  const ok =
                    name.endsWith(".pdf") ||
                    name.endsWith(".docx") ||
                    name.endsWith(".xlsx") ||
                    name.endsWith(".csv") ||
                    name.endsWith(".jpg") ||
                    name.endsWith(".jpeg") ||
                    name.endsWith(".png") ||
                    name.endsWith(".webp") ||
                    name.endsWith(".gif");
                  if (!ok) {
                    setError(
                      `Файл «${f.name}» не поддерживается. Используйте PDF, DOCX, XLSX, CSV или изображение (PNG/JPEG/WebP/GIF).`,
                    );
                    continue;
                  }
                  if (f.size > 12 * 1024 * 1024) {
                    setError(`Файл «${f.name}» больше 12 МБ`);
                    continue;
                  }
                  next.push(f);
                }
                attachmentsRef.current = next;
                setAttachments(next);
                e.currentTarget.value = "";
              }}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || busy}
              className="shrink-0 rounded-xl border border-surface-200 p-2 text-surface-700 hover:bg-surface-50 disabled:opacity-50"
              title="Прикрепить PDF, Word, Excel, CSV или изображение"
            >
              <Paperclip className="h-5 w-5" />
            </button>
            <button
              type="button"
              onClick={toggleVoice}
              disabled={disabled || busy}
              className="shrink-0 rounded-xl border border-surface-200 p-2 text-surface-700 hover:bg-surface-50 disabled:opacity-50"
              title="Голосовой ввод"
            >
              <Mic className={`h-5 w-5 ${listening ? "text-red-600" : ""}`} />
            </button>
            <input
              className="min-w-0 flex-1 rounded-xl border border-surface-200 px-3 py-2 text-sm outline-none focus:border-primary-500"
              placeholder={disabled ? "Ассистент недоступен" : "Сообщение… (опционально, если есть файлы)"}
              value={inputDraft}
              disabled={disabled || busy}
              onChange={(e) => setInputDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <button
              type="button"
              onClick={() => void send()}
              disabled={
                disabled ||
                busy ||
                (!inputDraft.trim() && attachments.length === 0)
              }
              className="shrink-0 rounded-xl bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
            >
              {busy ? "…" : <Send className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

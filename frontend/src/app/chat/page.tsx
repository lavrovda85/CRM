"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Image as ImageIcon, Mic, Paperclip, Send, StopCircle, X } from "lucide-react";

import type { ChatAttachmentResponse, ChatMessageResponse, ChatRoomResponse } from "@/types";
import {
  createChatRoom,
  fetchChatMessages,
  fetchChatRooms,
  sendChatMessage,
  uploadChatMessageAttachment,
} from "@/lib/api";

function formatTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

export default function ChatPage() {
  const PAGE_LIMIT = 100;
  const POLL_MS = 3000;
  const POLL_AFTER_BUFFER_MS = 10000;

  const [rooms, setRooms] = useState<ChatRoomResponse[]>([]);
  const [roomsBusy, setRoomsBusy] = useState(false);
  const [roomsError, setRoomsError] = useState<string | null>(null);
  const [roomCode, setRoomCode] = useState("company");

  const [createRoomOpen, setCreateRoomOpen] = useState(false);
  const [newRoomName, setNewRoomName] = useState("");
  const [createRoomBusy, setCreateRoomBusy] = useState(false);
  const [createRoomError, setCreateRoomError] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [recording, setRecording] = useState(false);
  const [mediaRecorderError, setMediaRecorderError] = useState<string | null>(null);

  const [imagePreview, setImagePreview] = useState<{ src: string; alt: string } | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const voiceChunksRef = useRef<BlobPart[]>([]);

  const selectedRoom = useMemo(() => rooms.find((r) => r.code === roomCode) ?? null, [rooms, roomCode]);

  const lastCreatedAt = useMemo(() => {
    if (!messages.length) return null;
    return messages[messages.length - 1].created_at;
  }, [messages]);

  const load = useCallback(
    async (opts?: { after?: string | null; append?: boolean }) => {
      setError(null);
      const after = opts?.after ?? null;

      try {
        const res = await fetchChatMessages({
          room: roomCode,
          after: after || undefined,
          limit: PAGE_LIMIT,
          offset: 0,
        });

        if (opts?.append) {
          setMessages((prev) => {
            const existing = new Set(prev.map((m) => m.id));
            const merged = [...prev];
            for (const item of res.items) {
              if (!existing.has(item.id)) merged.push(item);
            }
            return merged;
          });
        } else {
          setMessages(res.items);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load chat");
      } finally {
        setLoading(false);
      }
    },
    [roomCode],
  );

  useEffect(() => {
    // Initial rooms fetch (and then initial load) happens below.
  }, []);

  useEffect(() => {
    let cancelled = false;
    setRoomsBusy(true);
    setRoomsError(null);
    fetchChatRooms()
      .then((r) => {
        if (cancelled) return;
        setRooms(r);
        const hasCompany = r.some((x) => x.code === "company");
        if (!hasCompany && r.length > 0) {
          setRoomCode(r[0].code);
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setRoomsError(e instanceof Error ? e.message : "Failed to load chat rooms");
      })
      .finally(() => {
        if (cancelled) return;
        setRoomsBusy(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setMessages([]);
    setImagePreview(null);
    setPendingFiles([]);
    load({ after: null, append: false }).catch(() => {});
  }, [roomCode, load]);

  useEffect(() => {
    const t = setInterval(() => {
      if (!lastCreatedAt) return;
      // Poll for new messages (and re-load the last ~10s window so that
      // attachments uploaded after message creation become visible).
      const afterTs = new Date(lastCreatedAt).getTime() - POLL_AFTER_BUFFER_MS;
      const afterIso = new Date(afterTs).toISOString();
      load({ after: afterIso, append: true }).catch(() => {});
    }, POLL_MS);
    return () => clearInterval(t);
  }, [lastCreatedAt, load]);

  useEffect(() => {
    if (!imagePreview) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setImagePreview(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [imagePreview]);

  async function handleSend() {
    if (sending) return;
    const trimmed = body.trim();
    if (!trimmed && pendingFiles.length === 0) return;

    setSending(true);
    setError(null);
    try {
      const created = await sendChatMessage({ room: roomCode, body: trimmed });

      // Upload attachments (files / voice) after message creation.
      const files = [...pendingFiles];
      setPendingFiles([]);

      for (const f of files) {
        await uploadChatMessageAttachment(created.id, f);
      }

      // Refresh to ensure attachments are shown.
      await load({ after: null, append: false });
      setBody("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }

  function handleFilesAdded(files: FileList | null) {
    if (!files || files.length === 0) return;
    setMediaRecorderError(null);
    const arr = Array.from(files);
    setPendingFiles((prev) => [...prev, ...arr].slice(0, 10));
  }

  function removePendingFile(idx: number) {
    setPendingFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  async function startVoiceRecording() {
    setMediaRecorderError(null);
    if (recording) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const supportedType =
        MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
            ? "audio/webm"
            : "";

      voiceChunksRef.current = [];
      mediaStreamRef.current = stream;

      const recorder = new MediaRecorder(
        stream,
        supportedType ? { mimeType: supportedType } : undefined,
      );
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) voiceChunksRef.current.push(ev.data);
      };

      recorder.onstop = () => {
        const chunks = voiceChunksRef.current;
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        const file = new File([blob], `voice-${Date.now()}.webm`, { type: blob.type || "audio/webm" });
        setPendingFiles((prev) => [...prev, file].slice(0, 10));

        mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
        mediaStreamRef.current = null;
        mediaRecorderRef.current = null;
        voiceChunksRef.current = [];
      };

      recorder.start();
      setRecording(true);
    } catch (e) {
      setMediaRecorderError(e instanceof Error ? e.message : "Microphone access failed");
    }
  }

  function stopVoiceRecording() {
    if (!recording) return;
    setRecording(false);
    mediaRecorderRef.current?.stop();
  }

  function renderAttachment(a: ChatAttachmentResponse) {
    if (a.mime_type.startsWith("audio/")) {
      return (
        <div key={a.id} className="rounded-lg border border-surface-100 p-3">
          <div className="text-xs text-surface-500">{a.filename}</div>
          <audio className="mt-2 w-full" controls src={a.download_url} />
        </div>
      );
    }

    const filename = (a.filename ?? "").trim().toLowerCase();
    const isImage =
      a.mime_type.startsWith("image/") ||
      [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"].some((ext) => filename.endsWith(ext));

    if (isImage) {
      return (
        <div key={a.id} className="rounded-xl border border-surface-100 p-2 bg-white/40">
          <div className="flex items-center gap-2 px-1">
            <ImageIcon className="h-4 w-4 text-surface-400" />
            <div className="min-w-0 text-xs text-surface-500 truncate">{a.filename}</div>
          </div>
          <img
            className="mt-2 w-full max-h-[320px] max-w-full cursor-zoom-in rounded-lg object-contain bg-white/20"
            src={a.download_url}
            alt={a.filename}
            onClick={() => setImagePreview({ src: a.download_url, alt: a.filename })}
          />
        </div>
      );
    }

    return (
      <div key={a.id} className="rounded-lg border border-surface-100 p-3">
        <div className="text-xs text-surface-500">Файл</div>
        <a
          href={a.download_url}
          target="_blank"
          rel="noreferrer"
          className="mt-1 block text-sm font-medium text-primary-600 hover:underline truncate"
        >
          {a.filename}
        </a>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 lg:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{selectedRoom ? selectedRoom.name : "Чат"}</h1>
          <p className="text-sm text-surface-500">Сообщения между сотрудниками</p>
        </div>

        <div className="flex items-center gap-2">
          {roomsBusy ? (
            <div className="text-xs text-surface-400">Загрузка групп...</div>
          ) : (
            <select
              className="input"
              value={roomCode}
              onChange={(e) => setRoomCode(e.target.value)}
            >
              {rooms.map((r) => (
                <option key={r.code} value={r.code}>
                  {r.name}
                </option>
              ))}
            </select>
          )}

          <button
            type="button"
            className="btn-ghost"
            onClick={() => {
              setCreateRoomError(null);
              setNewRoomName("");
              setCreateRoomOpen(true);
            }}
            disabled={roomsBusy}
          >
            Создать группу
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {createRoomOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center"
          onClick={() => setCreateRoomOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-t-2xl bg-white p-6 shadow-2xl sm:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">Создание группы</h2>
              <button onClick={() => setCreateRoomOpen(false)} className="btn-ghost p-1.5" type="button">
                <X className="h-5 w-5" />
              </button>
            </div>

            {createRoomError && (
              <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">
                {createRoomError}
              </div>
            )}

            <div className="space-y-2">
              <label className="block text-sm font-medium text-surface-700">Направление *</label>
              <input
                className="input w-full"
                value={newRoomName}
                onChange={(e) => setNewRoomName(e.target.value)}
                placeholder="Например: Сервис, Монтаж, Ремонт..."
              />
            </div>

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={() => setCreateRoomOpen(false)}
                className="btn-secondary flex-1"
              >
                Отмена
              </button>
              <button
                type="button"
                className="btn-primary flex-1"
                disabled={createRoomBusy || !newRoomName.trim()}
                onClick={async () => {
                  try {
                    setCreateRoomError(null);
                    setCreateRoomBusy(true);
                    const created = await createChatRoom({ name: newRoomName.trim() });
                    setCreateRoomOpen(false);
                    // Refresh list and select new room.
                    const r = await fetchChatRooms();
                    setRooms(r);
                    setRoomCode(created.code);
                  } catch (e) {
                    setCreateRoomError(
                      e instanceof Error ? e.message : "Ошибка создания группы",
                    );
                  } finally {
                    setCreateRoomBusy(false);
                  }
                }}
              >
                {createRoomBusy ? "Создание..." : "Создать"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="card flex flex-col overflow-hidden">
        <div className="flex-1 space-y-3 overflow-y-auto p-4" style={{ maxHeight: "55vh" }}>
          {loading ? (
            <div className="text-sm text-surface-500">Загрузка...</div>
          ) : messages.length === 0 ? (
            <div className="text-sm text-surface-500">Пока сообщений нет</div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className="flex gap-3">
                <div className="mt-0.5 h-8 w-8 shrink-0 rounded-full bg-surface-100" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <div className="truncate text-sm font-medium text-surface-900">
                      {m.sender_name || "Сотрудник"}
                    </div>
                    <div className="text-xs text-surface-400">{formatTime(m.created_at)}</div>
                  </div>
                  {m.body ? (
                    <div className="mt-1 whitespace-pre-wrap break-words text-sm text-surface-700">{m.body}</div>
                  ) : null}

                  {m.attachments?.length ? (
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      {m.attachments.map((a) => renderAttachment(a))}
                    </div>
                  ) : null}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="border-t border-surface-100 p-4">
          <div className="space-y-3">
            <div className="flex gap-2">
              <textarea
                className="input min-h-[44px] flex-1 resize-none"
                placeholder="Написать сообщение..."
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
              <button
                type="button"
                className="btn-primary"
                onClick={() => handleSend().catch(() => {})}
                disabled={sending || (!body.trim() && pendingFiles.length === 0)}
              >
                <Send className="h-4 w-4" />
                {sending ? "Отправка..." : "Отправить"}
              </button>
            </div>

            <div className="flex flex-wrap gap-2 items-center">
              <label className="btn-ghost cursor-pointer" title="Прикрепить файл">
                <input
                  type="file"
                  multiple
                  className="hidden"
                  accept="audio/*,image/*,application/pdf,.doc,.docx,.xls,.xlsx,.zip,.rar"
                  onChange={(e) => handleFilesAdded(e.target.files)}
                />
                <Paperclip className="h-4 w-4" />
              </label>

              <button
                type="button"
                onClick={() => (recording ? stopVoiceRecording() : startVoiceRecording())}
                className="btn-secondary inline-flex items-center gap-2"
                disabled={sending}
                title={recording ? "Остановить голос" : "Записать голос"}
              >
                {recording ? (
                  <StopCircle className="h-4 w-4" />
                ) : (
                  <Mic className="h-4 w-4" />
                )}
              </button>
            </div>

            {mediaRecorderError && (
              <div className="text-sm text-red-700 bg-red-50 rounded-lg p-3" role="alert">
                {mediaRecorderError}
              </div>
            )}

            {pendingFiles.length ? (
              <div className="space-y-2">
                <div className="text-xs text-surface-500">Подготовлено для отправки</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {pendingFiles.map((f, idx) => (
                    <div key={`${f.name}-${idx}`} className="rounded-lg border border-surface-100 p-3 flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-xs text-surface-500 truncate">{f.name}</div>
                      </div>
                      <button
                        type="button"
                        className="rounded p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
                        onClick={() => removePendingFile(idx)}
                        disabled={sending}
                        title="Убрать"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="text-[12px] text-surface-400">
              Можно отправлять текст, файлы и голосовые сообщения. Вложения появятся в чате после отправки.
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
    </div>
  );
}


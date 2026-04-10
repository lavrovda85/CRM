"use client";

import { useMemo, useState, useCallback, useRef, useEffect, type DragEvent, type TouchEvent, type CSSProperties } from "react";
import Link from "next/link";
import { Check, GripVertical } from "lucide-react";
import type { TaskResponse } from "@/types";
import type { UserListItem } from "@/lib/api";
import { formatEnumLabel } from "@/lib/utils";
import {
  columnKeyOfTask,
  getTaskDayInterval,
  isTerminalTaskStatus,
  type TaskDayInterval,
  type TimelineDateField,
} from "@/lib/timelineTaskIntervals";

const DUE_SOON_MINUTES = Math.max(
  1,
  Number.parseInt(process.env.NEXT_PUBLIC_TASK_DUE_SOON_MINUTES ?? "180", 10) || 180,
);

const SLOT_PX = 72;                 // Hour row height — NEVER expands
const TIMELINE_COLUMN_WIDTH_PX = 170;
const TIMELINE_CARD_HEIGHT_PX = 52; // Height of a card when it is the only one in the slot
const CASCADE_MIN_H = 14;           // Min visible height of each card in cascade
const CASCADE_INDENT_PX = 0;        // No horizontal shift — cards are flush left
const CASCADE_MAX_VISIBLE = 5;      // Cards shown before "+N more" overflow badge

export type TimelineGroupBy = "assignee" | "type" | "priority" | "status";
export type { TimelineDateField };

export interface TimelineHoursBoardProps {
  tasks: TaskResponse[];
  assignees?: UserListItem[];
  visibleAssigneeIds?: string[] | null;
  groupBy: TimelineGroupBy;
  dateField: TimelineDateField;
  selectedDate: string;
  hourStart: number;
  hourEndExclusive: number;
  priorityColor: Record<string, string>;
  priorityLabel: Record<string, string>;
  statusLabel: Record<string, string>;
  onTaskMove?: (
    taskId: string,
    destination: { toRowKey: string; toDayKey: string; toHour: number },
  ) => Promise<void> | void;
  onQuickComplete?: (taskId: string) => Promise<void> | void;
  onSlotClick?: (slot: { rowKey: string; dayKey: string; hour: number }) => void;
}

function avatarUrl(seed: string): string {
  const base = process.env.NEXT_PUBLIC_AVATAR_SERVICE_BASE_URL ?? "https://api.dicebear.com/9.x/thumbs/svg";
  return `${base}?seed=${encodeURIComponent(seed)}`;
}

function fmtHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}

function priorityRank(p: string): number {
  if (p === "critical") return 4;
  if (p === "high") return 3;
  if (p === "medium") return 2;
  if (p === "low") return 1;
  return 0;
}

function statusMarkerColor(status: string): string {
  if (status === "done" || status === "completed" || status === "closed") return "#22c55e";
  if (status === "in_progress") return "#3b82f6";
  if (status === "testing" || status === "photo_report") return "#f59e0b";
  if (status === "act_signing") return "#f97316";
  if (status === "dispatched") return "#06b6d4";
  return "#94a3b8";
}

function dueUrgency(dueIso: string | null | undefined, status: string): "overdue" | "soon" | "none" {
  if (!dueIso || isTerminalTaskStatus(status)) return "none";
  const due = new Date(dueIso).getTime();
  if (Number.isNaN(due)) return "none";
  const now = Date.now();
  if (due < now) return "overdue";
  return due - now <= DUE_SOON_MINUTES * 60_000 ? "soon" : "none";
}

type TaskWithIv = { task: TaskResponse; iv: TaskDayInterval; colKey: string };

function startHourOf(iv: TaskDayInterval, hourStart: number, hourEndExclusive: number): number {
  return Math.min(hourEndExclusive - 1, Math.max(hourStart, iv.start.getHours()));
}

export function TimelineHoursBoard({
  tasks,
  assignees,
  visibleAssigneeIds = null,
  groupBy,
  dateField,
  selectedDate,
  hourStart,
  hourEndExclusive,
  priorityColor,
  priorityLabel,
  statusLabel,
  onTaskMove,
  onQuickComplete,
  onSlotClick,
}: TimelineHoursBoardProps) {
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);

  // ─── Touch drag state ──────────────────────────────────────────────────────
  const touchDragId   = useRef<string | null>(null);
  const touchGhost    = useRef<HTMLDivElement | null>(null);
  const touchOffsetX  = useRef(0);
  const touchOffsetY  = useRef(0);

  /** Build a lightweight ghost element that follows the finger */
  const createTouchGhost = useCallback((label: string, x: number, y: number) => {
    const el = document.createElement("div");
    el.textContent = label;
    Object.assign(el.style, {
      position:        "fixed",
      top:             `${y}px`,
      left:            `${x}px`,
      zIndex:          "9999",
      pointerEvents:   "none",
      background:      "rgba(56,189,248,0.9)",
      color:           "#fff",
      padding:         "4px 10px",
      borderRadius:    "8px",
      fontSize:        "13px",
      fontWeight:      "600",
      maxWidth:        "180px",
      overflow:        "hidden",
      textOverflow:    "ellipsis",
      whiteSpace:      "nowrap",
      boxShadow:       "0 4px 16px rgba(0,0,0,0.18)",
      transform:       "translate(-50%,-120%)",
    });
    document.body.appendChild(el);
    touchGhost.current = el;
  }, []);

  const removeTouchGhost = useCallback(() => {
    touchGhost.current?.remove();
    touchGhost.current = null;
  }, []);

  /** Resolve which cell div is under a touch point */
  const getCellIdUnderTouch = useCallback((cx: number, cy: number): string | null => {
    const el = document.elementFromPoint(cx, cy);
    const cell = el?.closest("[data-cell-id]") as HTMLElement | null;
    return cell?.dataset.cellId ?? null;
  }, []);

  const handleTouchStart = useCallback(
    (e: TouchEvent, taskId: string, label: string) => {
      const t = e.touches[0];
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      touchOffsetX.current = t.clientX - rect.left;
      touchOffsetY.current = t.clientY - rect.top;
      touchDragId.current  = taskId;
      setDraggedTaskId(taskId);
      createTouchGhost(label, t.clientX, t.clientY);
    },
    [createTouchGhost],
  );

  const handleTouchMove = useCallback(
    (e: TouchEvent) => {
      if (!touchDragId.current) return;
      e.preventDefault();
      const t = e.touches[0];
      if (touchGhost.current) {
        touchGhost.current.style.top  = `${t.clientY}px`;
        touchGhost.current.style.left = `${t.clientX}px`;
      }
      const cellId = getCellIdUnderTouch(t.clientX, t.clientY);
      setDropTargetId(cellId);
    },
    [getCellIdUnderTouch],
  );

  const handleTouchEnd = useCallback(
    (e: TouchEvent) => {
      const id = touchDragId.current;
      if (!id) return;
      const t = e.changedTouches[0];
      const cellId = getCellIdUnderTouch(t.clientX, t.clientY);
      if (cellId) {
        const [toRowKey, toDayKey, hourStr] = cellId.split("||");
        const toHour = parseInt(hourStr, 10);
        if (!isNaN(toHour)) {
          onTaskMove?.(id, { toRowKey, toDayKey, toHour });
        }
      }
      touchDragId.current = null;
      removeTouchGhost();
      setDraggedTaskId(null);
      setDropTargetId(null);
    },
    [getCellIdUnderTouch, onTaskMove, removeTouchGhost],
  );

  // Attach passive:false touch-move listener to the container to allow preventDefault
  const containerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onMove = (e: globalThis.TouchEvent) => {
      if (touchDragId.current) e.preventDefault();
    };
    el.addEventListener("touchmove", onMove, { passive: false });
    return () => el.removeEventListener("touchmove", onMove);
  }, []);

  const { hourList, columnKeys, columnLabels, tasksByStartHourByColumn } = useMemo(() => {
    const hours: number[] = [];
    for (let h = hourStart; h < hourEndExclusive; h += 1) hours.push(h);

    const assigneeFilterExplicit = groupBy === "assignee" && Array.isArray(visibleAssigneeIds);
    const assigneeAllowed = assigneeFilterExplicit ? new Set(visibleAssigneeIds) : null;

    function columnKeyOf(t: TaskResponse): string {
      return columnKeyOfTask(t, groupBy);
    }

    const columnKeysSet = new Set<string>();
    const columnLabelsLocal: Record<string, string> = {};

    if (groupBy === "assignee" && assignees && assignees.length > 0) {
      columnKeysSet.add("none");
      columnLabelsLocal.none = "Без исполнителя";
      for (const u of assignees) {
        if (assigneeAllowed !== null && !assigneeAllowed.has(String(u.id))) continue;
        columnKeysSet.add(String(u.id));
        columnLabelsLocal[String(u.id)] = u.full_name;
      }
    }

    for (const t of tasks) {
      const ck = columnKeyOf(t);
      if (groupBy === "assignee" && assigneeAllowed !== null && ck !== "none" && !assigneeAllowed.has(ck)) {
        continue;
      }
      columnKeysSet.add(ck);
      if (groupBy === "assignee") {
        if (ck === "none") columnLabelsLocal[ck] = "Без исполнителя";
        else columnLabelsLocal[ck] = t.assignee?.full_name ?? columnLabelsLocal[ck] ?? "Исполнитель";
      }
      if (groupBy === "type") {
        if (ck === "none") columnLabelsLocal[ck] = "Без типа";
        else columnLabelsLocal[ck] = t.template?.category ?? t.template?.name ?? columnLabelsLocal[ck] ?? "Тип";
      }
      if (groupBy === "priority") columnLabelsLocal[ck] = priorityLabel[ck] ?? ck;
      if (groupBy === "status") columnLabelsLocal[ck] = statusLabel[ck] ?? ck;
    }

    let columnKeysLocal = Array.from(columnKeysSet.values());
    if (groupBy === "assignee") {
      const ordered: string[] = ["none"];
      if (assignees && assignees.length > 0) {
        for (const u of assignees) {
          if (assigneeAllowed !== null && !assigneeAllowed.has(String(u.id))) continue;
          ordered.push(String(u.id));
        }
      }
      const used = new Set(ordered);
      const extra = columnKeysLocal
        .filter((k) => !used.has(k))
        .sort((a, b) => (columnLabelsLocal[a] ?? a).localeCompare(columnLabelsLocal[b] ?? b, "ru-RU"));
      columnKeysLocal = [...ordered.filter((k) => columnKeysSet.has(k)), ...extra];
    } else if (groupBy === "priority") {
      const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, none: 999 };
      columnKeysLocal.sort((a, b) => (order[a] ?? 999) - (order[b] ?? 999));
    } else {
      columnKeysLocal.sort((a, b) =>
        (columnLabelsLocal[a] ?? a).localeCompare(columnLabelsLocal[b] ?? b, "ru-RU"),
      );
    }

    const tasksByStartHourByColumnLocal: Record<string, Record<number, TaskWithIv[]>> = {};
    for (const ck of columnKeysLocal) {
      tasksByStartHourByColumnLocal[ck] = {};
      for (const hour of hours) tasksByStartHourByColumnLocal[ck][hour] = [];
    }

    for (const t of tasks) {
      const colKey = columnKeyOf(t);
      if (groupBy === "assignee" && assigneeAllowed !== null && colKey !== "none" && !assigneeAllowed.has(colKey)) {
        continue;
      }
      const iv = getTaskDayInterval(t, selectedDate, dateField, hourStart, hourEndExclusive);
      if (!iv) continue;
      const sh = startHourOf(iv, hourStart, hourEndExclusive);
      tasksByStartHourByColumnLocal[colKey]?.[sh]?.push({ task: t, iv, colKey });
    }

    for (const colKey of columnKeysLocal) {
      for (const hour of hours) {
        tasksByStartHourByColumnLocal[colKey][hour].sort((a, b) => {
          const dp = priorityRank(b.task.priority) - priorityRank(a.task.priority);
          if (dp !== 0) return dp;
          return a.iv.start.getTime() - b.iv.start.getTime();
        });
      }
    }

    return {
      hourList: hours,
      columnKeys: columnKeysLocal,
      columnLabels: columnLabelsLocal,
      tasksByStartHourByColumn: tasksByStartHourByColumnLocal,
    };
  }, [tasks, groupBy, dateField, selectedDate, hourStart, hourEndExclusive, priorityLabel, statusLabel, assignees, visibleAssigneeIds]);

  const effectiveColumns = columnKeys.length > 0 ? columnKeys : ["none"];

  // Row height is always fixed — tasks cascade within the slot, never expand the row.
  const hourRowHeight = useMemo(() => {
    const out: Record<number, number> = {};
    for (const h of hourList) out[h] = SLOT_PX;
    return out;
  }, [hourList]);

  const assigneeAvatarById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const u of assignees ?? []) {
      if (u.avatar_url) map[String(u.id)] = String(u.avatar_url);
    }
    return map;
  }, [assignees]);

  const onDragStart = useCallback((e: DragEvent<HTMLDivElement>, taskId: string) => {
    e.dataTransfer.setData("text/plain", taskId);
    e.dataTransfer.effectAllowed = "move";
    setDraggedTaskId(taskId);
  }, []);

  const onDragEnd = useCallback(() => {
    setDraggedTaskId(null);
    setDropTargetId(null);
  }, []);

  const onCellDragOver = useCallback((e: DragEvent<HTMLDivElement>, cellId: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDropTargetId(cellId);
  }, []);

  const onCellDragLeave = useCallback(() => {
    setDropTargetId(null);
  }, []);

  const onCellDrop = useCallback(
    (e: DragEvent<HTMLDivElement>, cellId: string) => {
      e.preventDefault();
      const taskId = e.dataTransfer.getData("text/plain");
      setDraggedTaskId(null);
      setDropTargetId(null);
      if (!taskId) return;
      const parts = cellId.split("__");
      if (parts.length !== 3) return;
      const [toRowKey, toDayKey, toHourRaw] = parts;
      const toHour = Number(toHourRaw);
      if (!Number.isFinite(toHour)) return;
      onTaskMove?.(taskId, { toRowKey, toDayKey, toHour });
    },
    [onTaskMove],
  );

  return (
    <div className="card w-full max-w-full overflow-hidden" ref={containerRef}>
      <div className="w-full overflow-x-auto overflow-y-hidden overscroll-x-contain touch-pan-x">
        <div
          className="min-w-[860px]"
          style={{
            display: "grid",
            gridTemplateColumns: `58px repeat(${Math.max(effectiveColumns.length, 1)}, ${TIMELINE_COLUMN_WIDTH_PX}px)`,
          }}
        >
          {/* Column headers */}
          <div className="sticky left-0 z-20 border-b border-surface-100 bg-white px-1 py-1" />
          {effectiveColumns.map((colKey) => {
            const label = columnLabels[colKey] ?? "—";
            const seed = colKey === "none" ? "unassigned" : colKey;
            const realAvatar = colKey === "none" ? "" : assigneeAvatarById[colKey];
            return (
              <div key={`chip-${colKey}`} className="border-b border-surface-100 bg-white px-1 py-1">
                <div className="flex flex-col items-center gap-1">
                  <div className="h-8 w-8 overflow-hidden rounded-full border border-surface-200 bg-surface-100">
                    {colKey === "none" ? (
                      <div className="flex h-full w-full items-center justify-center text-xs font-semibold text-surface-500">?</div>
                    ) : (
                      <img src={realAvatar || avatarUrl(seed)} alt={label} className="h-full w-full object-cover" loading="lazy" />
                    )}
                  </div>
                  <div className="w-full truncate text-center text-[10px] font-medium text-surface-700">{label}</div>
                </div>
              </div>
            );
          })}

          {/* Sub-header row */}
          <div className="sticky left-0 z-20 border-b border-surface-100 bg-white px-1.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-surface-500">
            Время
          </div>
          {effectiveColumns.map((colKey) => (
            <div key={`head-${colKey}`} className="z-10 border-b border-surface-100 bg-white py-1 text-center text-[10px] font-semibold text-surface-400">·</div>
          ))}

          {/* Hour rows */}
          {hourList.map((h) => {
            const rowH = hourRowHeight[h] ?? SLOT_PX;
            return (
              <div key={`hour-row-${h}`} style={{ display: "contents" }}>
                <div
                  className="sticky left-0 z-10 border-b border-surface-50 bg-white px-1.5 py-1 text-[10px] font-medium text-surface-600"
                  style={{ height: rowH }}
                >
                  {fmtHour(h)}
                </div>

                {effectiveColumns.map((colKey) => {
                  const cellItems = tasksByStartHourByColumn[colKey]?.[h] ?? [];
                  const cellId = `${colKey}__${selectedDate}__${h}`;
                  const isDropTarget = dropTargetId === cellId;

                  // Cascade layout calculations:
                  //  • rowH is always SLOT_PX (fixed)
                  //  • visibleItems: first CASCADE_MAX_VISIBLE tasks
                  //  • cardH: full height for solo card, distributed height for cascade
                  //  • step: vertical distance between consecutive card tops, so every card
                  //    is reachable (title visible) and the last one's bottom ≤ rowH
                  const visibleItems = cellItems.slice(0, CASCADE_MAX_VISIBLE);
                  const overflowCount = cellItems.length - visibleItems.length;
                  const n = visibleItems.length;
                  const isSolo = n === 1 && overflowCount === 0;

                  const cardH = isSolo
                    ? TIMELINE_CARD_HEIGHT_PX
                    : Math.max(CASCADE_MIN_H, Math.floor((rowH - 8) / n));

                  // Distribute tops so all n cards fit: first at y=4, last at y= rowH-4-cardH
                  const step = n <= 1 ? 0 : (rowH - 8 - cardH) / (n - 1);

                  const handleCellClick = () => {
                    onSlotClick?.({ rowKey: colKey, dayKey: selectedDate, hour: h });
                  };

                  // Touch-compatible cell id uses "||" so it never collides with colKey characters
                  const touchCellId = `${colKey}||${selectedDate}||${h}`;

                  return (
                    <div
                      key={`cell-${colKey}-${h}`}
                      data-cell-id={touchCellId}
                      onDragOver={(e) => onCellDragOver(e, cellId)}
                      onDragLeave={onCellDragLeave}
                      onDrop={(e) => onCellDrop(e, cellId)}
                      onClick={handleCellClick}
                      className="group relative cursor-pointer border-b border-surface-50 hover:bg-primary-50/40"
                      style={{
                        height: rowH,
                        overflow: "hidden",
                        background: isDropTarget ? "rgba(56,189,248,0.12)" : undefined,
                        outline: isDropTarget ? "2px solid rgba(56,189,248,0.5)" : undefined,
                        outlineOffset: "-2px",
                      }}
                    >
                      {/* "+" hint on hover when cell is empty */}
                      {cellItems.length === 0 && (
                        <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-lg font-light text-primary-300 opacity-0 transition-opacity group-hover:opacity-100 select-none">
                          +
                        </span>
                      )}
                      {visibleItems.map((item, idx) => {
                        const t = item.task;
                        const isDragging = draggedTaskId === t.id;

                        // Cascade: cards step down, all flush left, same width
                        const topPx  = 4 + idx * step;
                        const leftPx = 4;
                        const widthPx = Math.max(40, TIMELINE_COLUMN_WIDTH_PX - 8);

                        const pColor = priorityColor[t.priority] ?? "#94a3b8";
                        const urgency = dueUrgency(t.due_date, t.status);
                        const urgencyTopColor = urgency === "overdue" ? "#ef4444" : urgency === "soon" ? "#f59e0b" : pColor;
                        const cardBorderColor =
                          urgency === "overdue" ? "#fca5a5" : urgency === "soon" ? "#fcd34d" : `${statusMarkerColor(t.status)}66`;
                        const cardBgColor =
                          urgency === "overdue"
                            ? "rgba(254,242,242,0.97)"
                            : urgency === "soon"
                              ? "rgba(255,251,235,0.97)"
                              : "rgba(255,255,255,0.95)";
                        const done = isTerminalTaskStatus(t.status);

                        const cardStyle: CSSProperties = {
                          position: "absolute",
                          left: leftPx,
                          top: topPx,
                          width: widthPx,
                          height: cardH,
                          zIndex: 10 + idx,
                          boxSizing: "border-box",
                          borderColor: cardBorderColor,
                          backgroundColor: cardBgColor,
                          boxShadow: `0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px ${cardBorderColor}55 inset`,
                          opacity: isDragging ? 0.35 : 1,
                          transition: "opacity 150ms ease, z-index 0ms",
                        };

                        return (
                          <div
                            key={t.id}
                            draggable
                            onDragStart={(e) => onDragStart(e, t.id)}
                            onDragEnd={onDragEnd}
                            onTouchStart={(e: TouchEvent<HTMLDivElement>) => handleTouchStart(e, t.id, t.title)}
                            onTouchMove={(e: TouchEvent<HTMLDivElement>) => handleTouchMove(e)}
                            onTouchEnd={(e: TouchEvent<HTMLDivElement>) => handleTouchEnd(e)}
                            onClick={(e) => e.stopPropagation()}
                            onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.zIndex = String(50 + idx); }}
                            onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.zIndex = String(10 + idx); }}
                            className="cursor-grab rounded-md border border-surface-200 active:cursor-grabbing"
                            style={cardStyle}
                          >
                            {isSolo ? (
                              // ── Full card (single task in slot) ──────────────────
                              <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-md">
                                <div className="h-1 w-full shrink-0 rounded-t-md" style={{ backgroundColor: urgencyTopColor }} />
                                <div className="flex min-h-0 flex-1 items-start gap-0.5 px-1 py-0.5">
                                  <GripVertical className="mt-0.5 h-3 w-3 shrink-0 text-surface-400" />
                                  <Link
                                    href={`/tasks/${t.id}`}
                                    className="min-w-0 flex-1"
                                    onClick={(e) => e.stopPropagation()}
                                    draggable={false}
                                  >
                                    <div className="flex items-center gap-1">
                                      <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: statusMarkerColor(t.status) }} />
                                      <div className={`truncate text-[10px] font-medium leading-tight ${done ? "text-surface-500 line-through decoration-surface-400/90 decoration-2" : "text-surface-900"}`}>
                                        {t.title}
                                      </div>
                                    </div>
                                    <div className="line-clamp-2 text-[9px] text-surface-500">
                                      {formatEnumLabel(t.status, statusLabel)}
                                      {urgency === "overdue" ? " • просрочена" : urgency === "soon" ? " • скоро срок" : ""}
                                    </div>
                                  </Link>
                                  {!done && (
                                    <button
                                      type="button"
                                      onClick={(e) => { e.stopPropagation(); void onQuickComplete?.(t.id); }}
                                      className="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                                      title="Завершить задачу"
                                    >
                                      <Check className="h-2.5 w-2.5" />
                                    </button>
                                  )}
                                </div>
                              </div>
                            ) : (
                              // ── Compact cascade card ──────────────────────────────
                              <div className="flex h-full items-center overflow-hidden rounded-md">
                                {/* Priority stripe on the left */}
                                <div className="h-full w-[3px] shrink-0 rounded-l-md" style={{ backgroundColor: urgencyTopColor }} />
                                <div className="flex min-w-0 flex-1 items-center gap-1 px-1">
                                  <GripVertical className="h-2.5 w-2.5 shrink-0 text-surface-300" />
                                  <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: statusMarkerColor(t.status) }} />
                                  <Link
                                    href={`/tasks/${t.id}`}
                                    className="min-w-0 flex-1 truncate"
                                    onClick={(e) => e.stopPropagation()}
                                    draggable={false}
                                  >
                                    <span className={`truncate text-[9px] font-medium leading-none ${done ? "text-surface-400 line-through decoration-surface-400/80" : "text-surface-800"}`}>
                                      {t.title}
                                    </span>
                                  </Link>
                                  {!done && (
                                    <button
                                      type="button"
                                      onClick={(e) => { e.stopPropagation(); void onQuickComplete?.(t.id); }}
                                      className="inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                                      title="Завершить задачу"
                                    >
                                      <Check className="h-2 w-2" />
                                    </button>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}

                      {/* Overflow badge: "+N more" */}
                      {overflowCount > 0 && (
                        <div
                          className="absolute right-1 rounded-full bg-surface-200 px-1.5 py-0.5 text-[8px] font-semibold text-surface-600"
                          style={{ bottom: 4, zIndex: 60 }}
                        >
                          +{overflowCount}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

"use client";

import { cn } from "@/lib/utils";
import {
  ArrowRightLeft,
  MessageSquare,
  FileUp,
  Clock,
  type LucideIcon,
} from "lucide-react";
import { formatDistanceToNow, parseISO } from "date-fns";
import { ru } from "date-fns/locale";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type ActivityType = "status_change" | "comment" | "document_upload" | "generic";

export interface ActivityEntry {
  id: string;
  type: ActivityType;
  /** Заголовок события. */
  title: string;
  /** Подробное описание (текст комментария, имя файла и т.д.). */
  description?: string;
  /** ISO timestamp. */
  timestamp: string;
  /** Автор действия. */
  actor?: string;
}

export interface ActivityTimelineProps {
  /** Массив записей активности в хронологическом порядке. */
  entries: ActivityEntry[];
  className?: string;
}

const ICON_MAP: Record<ActivityType, LucideIcon> = {
  status_change: ArrowRightLeft,
  comment: MessageSquare,
  document_upload: FileUp,
  generic: Clock,
};

const COLOR_MAP: Record<ActivityType, string> = {
  status_change: "bg-indigo-100 text-indigo-600",
  comment: "bg-sky-100 text-sky-600",
  document_upload: "bg-emerald-100 text-emerald-600",
  generic: "bg-surface-100 text-surface-500",
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Вертикальная лента активности (timeline) с иконками по типу события.
 *
 * Args:
 *     entries: Массив событий для отображения.
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент таймлайна.
 */
export function ActivityTimeline({ entries, className }: ActivityTimelineProps) {
  if (entries.length === 0) {
    return (
      <p className={cn("text-sm text-surface-400 py-6 text-center", className)}>
        Нет активности
      </p>
    );
  }

  return (
    <div className={cn("relative", className)}>
      {/* Vertical line */}
      <div className="absolute left-4 top-0 bottom-0 w-px bg-surface-200" aria-hidden="true" />

      <ul className="space-y-6">
        {entries.map((entry) => {
          const Icon = ICON_MAP[entry.type] ?? ICON_MAP.generic;
          const colorCls = COLOR_MAP[entry.type] ?? COLOR_MAP.generic;

          let relativeTime: string;
          try {
            relativeTime = formatDistanceToNow(parseISO(entry.timestamp), { addSuffix: true, locale: ru });
          } catch {
            relativeTime = entry.timestamp;
          }

          return (
            <li key={entry.id} className="relative pl-10">
              {/* Icon circle */}
              <div
                className={cn(
                  "absolute left-1.5 top-0 flex h-5 w-5 items-center justify-center rounded-full",
                  colorCls,
                )}
              >
                <Icon className="h-3 w-3" />
              </div>

              <div>
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <p className="text-sm font-medium text-surface-800">{entry.title}</p>
                  {entry.actor && (
                    <span className="text-xs text-surface-400">— {entry.actor}</span>
                  )}
                </div>

                {entry.description && (
                  <p className="mt-0.5 text-sm text-surface-500">{entry.description}</p>
                )}

                <time className="mt-1 block text-xs text-surface-400" dateTime={entry.timestamp}>
                  {relativeTime}
                </time>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default ActivityTimeline;

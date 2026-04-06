"use client";

import { cn } from "@/lib/utils";
import { Calendar, User } from "lucide-react";
import { isAfter, parseISO, format } from "date-fns";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type Priority = "low" | "medium" | "high" | "critical";

export interface TaskCardProps {
  /** Заголовок задачи. */
  title: string;
  /** Имя назначенного исполнителя. */
  assignee?: string;
  /** URL аватара исполнителя. */
  assigneeAvatar?: string;
  /** Приоритет задачи. */
  priority?: Priority;
  /** Дата дедлайна (ISO-строка). */
  dueDate?: string;
  /** Прогресс чеклиста: [выполнено, всего]. */
  checklist?: [number, number];
  /** Имя связанного клиента. */
  clientName?: string;
  /** Callback клика по карточке. */
  onClick?: () => void;
  className?: string;
}

const PRIORITY_COLORS: Record<Priority, string> = {
  low: "bg-blue-400",
  medium: "bg-amber-400",
  high: "bg-orange-500",
  critical: "bg-red-500",
};

const PRIORITY_LABELS: Record<Priority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Карточка задачи для канбан-доски с приоритетом, дедлайном и прогрессом чеклиста.
 *
 * Args:
 *     title: Заголовок задачи.
 *     assignee: Имя исполнителя.
 *     assigneeAvatar: URL аватара.
 *     priority: Приоритет (low, medium, high, critical).
 *     dueDate: ISO-строка дедлайна.
 *     checklist: Кортеж [completed, total] прогресса чеклиста.
 *     clientName: Имя связанного клиента.
 *     onClick: Callback при клике.
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент карточки задачи.
 */
export function TaskCard({
  title,
  assignee,
  assigneeAvatar,
  priority,
  dueDate,
  checklist,
  clientName,
  onClick,
  className,
}: TaskCardProps) {
  const isOverdue = dueDate ? isAfter(new Date(), parseISO(dueDate)) : false;
  const checkPercent =
    checklist && checklist[1] > 0 ? Math.round((checklist[0] / checklist[1]) * 100) : 0;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick?.()}
      className={cn(
        "rounded-lg border border-surface-200 bg-white p-3 shadow-sm",
        "hover:shadow-md hover:border-primary-200 transition-all cursor-pointer group",
        className,
      )}
    >
      {/* Title + priority */}
      <div className="flex items-start gap-2">
        {priority && (
          <span
            className={cn("mt-1.5 h-2 w-2 rounded-full shrink-0", PRIORITY_COLORS[priority])}
            title={PRIORITY_LABELS[priority]}
          />
        )}
        <p className="text-sm font-medium text-surface-800 group-hover:text-primary-700 line-clamp-2">
          {title}
        </p>
      </div>

      {/* Client */}
      {clientName && (
        <p className="mt-1.5 text-xs text-surface-400 truncate">{clientName}</p>
      )}

      {/* Checklist progress */}
      {checklist && checklist[1] > 0 && (
        <div className="mt-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-surface-400">
              {checklist[0]}/{checklist[1]}
            </span>
            <span className="text-[10px] text-surface-400">{checkPercent}%</span>
          </div>
          <div className="h-1 w-full rounded-full bg-surface-100">
            <div
              className={cn(
                "h-1 rounded-full transition-all",
                checkPercent === 100 ? "bg-emerald-500" : "bg-primary-500",
              )}
              style={{ width: `${checkPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Footer row */}
      <div className="mt-2.5 flex items-center justify-between">
        {/* Due date */}
        {dueDate ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 text-xs",
              isOverdue ? "text-red-600 font-medium" : "text-surface-400",
            )}
          >
            <Calendar className="h-3 w-3" />
            {format(parseISO(dueDate), "MMM d")}
          </span>
        ) : (
          <span />
        )}

        {/* Assignee */}
        {assignee && (
          <div className="flex items-center gap-1.5">
            {assigneeAvatar ? (
              <img
                src={assigneeAvatar}
                alt={assignee}
                className="h-5 w-5 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary-100 text-primary-600">
                <User className="h-3 w-3" />
              </div>
            )}
            <span className="text-xs text-surface-500 max-w-[80px] truncate">{assignee}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default TaskCard;

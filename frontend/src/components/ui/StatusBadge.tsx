"use client";

import { Badge, type BadgeVariant, type BadgeSize } from "@/components/ui/Badge";

export type StatusId =
  | "new"
  | "dispatched"
  | "in_progress"
  | "testing"
  | "photo_report"
  | "act_signing"
  | "done"
  | "cancelled";

interface StatusMeta {
  label: string;
  variant: BadgeVariant;
  dotColor: string;
}

const STATUS_MAP: Record<StatusId, StatusMeta> = {
  new: { label: "Новая", variant: "default", dotColor: "bg-surface-400" },
  dispatched: { label: "Назначена", variant: "info", dotColor: "bg-blue-500" },
  in_progress: { label: "В работе", variant: "info", dotColor: "bg-indigo-500" },
  testing: { label: "Согласование", variant: "warning", dotColor: "bg-amber-500" },
  photo_report: { label: "Согласование", variant: "warning", dotColor: "bg-amber-500" },
  act_signing: { label: "Подписание акта", variant: "warning", dotColor: "bg-orange-500" },
  done: { label: "Выполнено", variant: "success", dotColor: "bg-emerald-500" },
  cancelled: { label: "Отменена", variant: "danger", dotColor: "bg-red-500" },
};

export interface StatusBadgeProps {
  /** Идентификатор статуса. */
  status: StatusId;
  /** Размер бейджа. */
  size?: BadgeSize;
  className?: string;
}

/**
 * Бейдж статуса с предопределённой картой цветов и меток.
 *
 * Args:
 *     status: Идентификатор статуса (new, dispatched, in_progress и т.д.).
 *     size: Размер бейджа.
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент статусного бейджа.
 */
export function StatusBadge({ status, size = "sm", className }: StatusBadgeProps) {
  const meta = STATUS_MAP[status] ?? STATUS_MAP.new;

  return <Badge label={meta.label} variant={meta.variant} size={size} dot className={className} />;
}

export default StatusBadge;

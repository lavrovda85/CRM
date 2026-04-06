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
  new: { label: "New", variant: "default", dotColor: "bg-surface-400" },
  dispatched: { label: "Dispatched", variant: "info", dotColor: "bg-blue-500" },
  in_progress: { label: "In Progress", variant: "info", dotColor: "bg-indigo-500" },
  testing: { label: "Testing", variant: "warning", dotColor: "bg-amber-500" },
  photo_report: { label: "Photo Report", variant: "default", dotColor: "bg-purple-500" },
  act_signing: { label: "Act Signing", variant: "warning", dotColor: "bg-orange-500" },
  done: { label: "Done", variant: "success", dotColor: "bg-emerald-500" },
  cancelled: { label: "Cancelled", variant: "danger", dotColor: "bg-red-500" },
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

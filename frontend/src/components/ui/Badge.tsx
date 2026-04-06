"use client";

import { cn } from "@/lib/utils";

export type BadgeVariant = "default" | "success" | "warning" | "danger" | "info";
export type BadgeSize = "sm" | "md";

export interface BadgeProps {
  /** Текстовое содержимое бейджа. */
  label: string;
  /** Визуальный вариант. */
  variant?: BadgeVariant;
  /** Размер бейджа. */
  size?: BadgeSize;
  /** Показывать ли цветную точку-индикатор слева. */
  dot?: boolean;
  className?: string;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: "bg-surface-100 text-surface-600",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-700",
  danger: "bg-red-50 text-red-700",
  info: "bg-sky-50 text-sky-700",
};

const DOT_CLASSES: Record<BadgeVariant, string> = {
  default: "bg-surface-400",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
  info: "bg-sky-500",
};

const SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: "text-xs px-1.5 py-0.5",
  md: "text-sm px-2 py-0.5",
};

/**
 * Универсальный компонент бейджа с вариантами, размерами и точечным индикатором.
 *
 * Args:
 *     label: Текст бейджа.
 *     variant: Цветовой вариант (default, success, warning, danger, info).
 *     size: Размер — sm или md.
 *     dot: Если true, отображается цветная точка перед текстом.
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент бейджа.
 */
export function Badge({
  label,
  variant = "default",
  size = "sm",
  dot = false,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium whitespace-nowrap",
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      )}
    >
      {dot && (
        <span
          className={cn("h-1.5 w-1.5 rounded-full shrink-0", DOT_CLASSES[variant])}
          aria-hidden="true"
        />
      )}
      {label}
    </span>
  );
}

export default Badge;

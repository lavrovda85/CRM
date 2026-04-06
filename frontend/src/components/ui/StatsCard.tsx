"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, type LucideIcon } from "lucide-react";

export interface StatsCardProps {
  /** Иконка карточки (компонент lucide-react). */
  icon: LucideIcon;
  /** Заголовок метрики. */
  title: string;
  /** Значение метрики. */
  value: string | number;
  /** Процент изменения (положительный — рост, отрицательный — падение). */
  trend?: number;
  /** Цвет левой полосы-акцента (Tailwind border-color class). */
  accentColor?: string;
  className?: string;
}

/**
 * Карточка статистики для дашборда с иконкой, значением и трендом.
 *
 * Args:
 *     icon: Компонент иконки из lucide-react.
 *     title: Название метрики.
 *     value: Отображаемое значение.
 *     trend: Процент изменения — положительный для роста, отрицательный для падения.
 *     accentColor: Tailwind-класс цвета левой границы (напр. "border-primary-500").
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент карточки статистики.
 */
export function StatsCard({
  icon: Icon,
  title,
  value,
  trend,
  accentColor = "border-primary-500",
  className,
}: StatsCardProps) {
  const isPositive = trend !== undefined && trend >= 0;

  return (
    <div
      className={cn(
        "rounded-xl border border-surface-200 bg-white p-4 shadow-sm border-l-4",
        accentColor,
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-surface-500">{title}</p>
          <p className="text-2xl font-bold text-surface-900">{value}</p>
        </div>
        <div className="rounded-lg bg-surface-50 p-2">
          <Icon className="h-5 w-5 text-surface-500" />
        </div>
      </div>

      {trend !== undefined && (
        <div className="mt-3 flex items-center gap-1">
          {isPositive ? (
            <TrendingUp className="h-4 w-4 text-emerald-500" />
          ) : (
            <TrendingDown className="h-4 w-4 text-red-500" />
          )}
          <span
            className={cn(
              "text-sm font-medium",
              isPositive ? "text-emerald-600" : "text-red-600",
            )}
          >
            {isPositive ? "+" : ""}
            {trend}%
          </span>
          <span className="text-sm text-surface-400">к пред. периоду</span>
        </div>
      )}
    </div>
  );
}

export default StatsCard;

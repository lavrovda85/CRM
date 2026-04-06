import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Объединяет CSS-классы с помощью clsx и tailwind-merge.
 *
 * Args:
 *     inputs: Произвольное количество значений классов (строки, объекты, массивы).
 *
 * Returns:
 *     Объединённая строка CSS-классов без конфликтов Tailwind.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Map a backend enum/slug to a localized label; fall back to a humanized slug.
 *
 * Args:
 *     value: Raw status/key from API (may be missing).
 *     labels: Known value → display label.
 *
 * Returns:
 *     Display string, or em dash when value is empty.
 */
export function formatEnumLabel(
  value: string | null | undefined,
  labels: Record<string, string>,
): string {
  if (value == null || value === "") {
    return "—";
  }
  const mapped = labels[value];
  if (mapped) {
    return mapped;
  }
  return value.replace(/_/g, " ");
}

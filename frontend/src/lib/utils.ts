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

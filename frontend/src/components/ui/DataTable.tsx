"use client";

import { useState, useCallback, type ReactNode } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ColumnDef<T> {
  /** Уникальный ключ колонки. */
  key: string;
  /** Заголовок колонки. */
  header: string;
  /** Функция доступа к значению ячейки. */
  accessor: (row: T) => unknown;
  /** Кастомный рендер ячейки. */
  render?: (value: unknown, row: T) => ReactNode;
  /** Разрешена ли сортировка. */
  sortable?: boolean;
  /** CSS-класс для ячейки. */
  className?: string;
}

export interface DataTableProps<T> {
  /** Определения колонок. */
  columns: ColumnDef<T>[];
  /** Массив данных. */
  data: T[];
  /** Флаг загрузки (показывает скелетон). */
  loading?: boolean;
  /** Функция получения уникального ключа строки. */
  rowKey: (row: T) => string;
  /** Callback клика по строке. */
  onRowClick?: (row: T) => void;
  /** Текст для пустого состояния. */
  emptyMessage?: string;
  className?: string;
}

type SortDir = "asc" | "desc" | null;

/**
 * Универсальная таблица данных с сортировкой, скелетоном загрузки и адаптивной прокруткой.
 *
 * Args:
 *     columns: Массив определений колонок.
 *     data: Массив данных для отображения.
 *     loading: Если true, отображается скелетон.
 *     rowKey: Функция для получения уникального ключа строки.
 *     onRowClick: Callback при клике по строке.
 *     emptyMessage: Текст при отсутствии данных.
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент таблицы данных.
 */
export function DataTable<T>({
  columns,
  data,
  loading = false,
  rowKey,
  onRowClick,
  emptyMessage = "Нет данных",
  className,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortDir((prev) => (prev === "asc" ? "desc" : prev === "desc" ? null : "asc"));
        if (sortDir === "desc") setSortKey(null);
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey, sortDir],
  );

  const sortedData = (() => {
    if (!sortKey || !sortDir) return data;
    const col = columns.find((c) => c.key === sortKey);
    if (!col) return data;
    return [...data].sort((a, b) => {
      const va = col.accessor(a);
      const vb = col.accessor(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
  })();

  const SortIcon = ({ colKey }: { colKey: string }) => {
    if (sortKey !== colKey) return <ChevronsUpDown className="h-3.5 w-3.5 text-surface-300" />;
    return sortDir === "asc" ? (
      <ChevronUp className="h-3.5 w-3.5 text-primary-500" />
    ) : (
      <ChevronDown className="h-3.5 w-3.5 text-primary-500" />
    );
  };

  return (
    <div className={cn("overflow-x-auto rounded-xl border border-surface-200 bg-white", className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-surface-100 bg-surface-50">
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-4 py-3 text-left font-medium text-surface-500 whitespace-nowrap",
                  col.sortable && "cursor-pointer select-none hover:text-surface-700",
                  col.className,
                )}
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sortable && <SortIcon colKey={col.key} />}
                </span>
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {loading &&
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={`skel-${i}`} className="border-b border-surface-50">
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3">
                    <div className="h-4 w-3/4 animate-pulse rounded bg-surface-100" />
                  </td>
                ))}
              </tr>
            ))}

          {!loading && sortedData.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-12 text-center">
                <Inbox className="mx-auto h-10 w-10 text-surface-300" />
                <p className="mt-2 text-surface-400">{emptyMessage}</p>
              </td>
            </tr>
          )}

          {!loading &&
            sortedData.map((row) => (
              <tr
                key={rowKey(row)}
                className={cn(
                  "border-b border-surface-50 transition-colors",
                  onRowClick && "cursor-pointer hover:bg-surface-50",
                )}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((col) => {
                  const val = col.accessor(row);
                  return (
                    <td key={col.key} className={cn("px-4 py-3 text-surface-700", col.className)}>
                      {col.render ? col.render(val, row) : (val as ReactNode)}
                    </td>
                  );
                })}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;

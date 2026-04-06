"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Package,
  AlertTriangle,
  ArrowDownUp,
  Plus,
  Search,
  History,
  ArrowUpCircle,
  ArrowDownCircle,
  Download,
  Upload,
} from "lucide-react";
import { useMemo } from "react";
import {
  fetchWarehouseItems,
  fetchWarehouseMovements,
  createWarehouseItem,
  downloadWarehouseItemsExcel,
  importWarehouseItemsExcel,
} from "@/lib/api";
import type { WarehouseItemResponse, WarehouseMovementResponse } from "@/types";
import { Modal } from "@/components/ui/Modal";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

type Tab = "items" | "movements";

export default function WarehousePage() {
  const [tab, setTab] = useState<Tab>("items");
  const [items, setItems] = useState<WarehouseItemResponse[]>([]);
  const [movements, setMovements] = useState<WarehouseMovementResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const [addOpen, setAddOpen] = useState(false);
  const [addBusy, setAddBusy] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [addForm, setAddForm] = useState({
    name: "",
    sku: "",
    category: "materials",
    unit: "pcs",
    quantity: "0",
    min_quantity: "0",
    price: "0",
    description: "",
    location: "",
  });

  const [importOpen, setImportOpen] = useState(false);
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);

  const categoryOptions = useMemo(
    () => [
      { value: "materials", label: "Материалы" },
      { value: "tools", label: "Инструмент" },
      { value: "consumables", label: "Расходники" },
      { value: "equipment", label: "Оборудование" },
    ],
    [],
  );

  const unitOptions = useMemo(
    () => [
      { value: "pcs", label: "шт" },
      { value: "m", label: "м" },
      { value: "kg", label: "кг" },
      { value: "l", label: "л" },
    ],
    [],
  );

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchWarehouseItems({ limit: 100 });
      setItems(res.items);
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMovements = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchWarehouseMovements({ limit: 50 });
      setMovements(res.items);
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === "items") loadItems();
    else loadMovements();
  }, [tab, loadItems, loadMovements]);

  const filteredItems = items.filter(
    (i) =>
      !search ||
      i.name.toLowerCase().includes(search.toLowerCase()) ||
      i.sku.toLowerCase().includes(search.toLowerCase()),
  );

  const movementTypeLabel: Record<string, string> = {
    intake: "Приход",
    return: "Возврат",
    consumption: "Расход",
    write_off: "Списание",
    transfer: "Перемещение",
  };

  const movementTypeIcon: Record<string, React.ReactNode> = {
    intake: <ArrowDownCircle className="h-4 w-4 text-green-500" />,
    return: <ArrowDownCircle className="h-4 w-4 text-green-500" />,
    consumption: <ArrowUpCircle className="h-4 w-4 text-red-500" />,
    write_off: <ArrowUpCircle className="h-4 w-4 text-red-500" />,
    transfer: <ArrowDownUp className="h-4 w-4 text-blue-500" />,
  };

  return (
    <>
    <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Склад</h1>
        <div className="flex items-center gap-2">
          <button className="btn-secondary gap-1.5">
            <ArrowDownUp className="h-4 w-4" /> Записать движение
          </button>
          <button
            type="button"
            className="btn-secondary gap-1.5"
            onClick={() => {
              downloadWarehouseItemsExcel().catch(() => {});
            }}
            title="Скачать Excel с текущими позициями"
          >
            <Download className="h-4 w-4" /> Экспорт Excel
          </button>
          <button
            type="button"
            className="btn-secondary gap-1.5"
            onClick={() => {
              setImportError(null);
              setImportResult(null);
              setImportFile(null);
              setImportOpen(true);
            }}
            title="Загрузить Excel/файл из 1С"
          >
            <Upload className="h-4 w-4" /> Импорт Excel/1С
          </button>
          <button
            type="button"
            className="btn-primary gap-1.5"
            onClick={() => {
              setAddError(null);
              setAddForm({
                name: "",
                sku: "",
                category: "materials",
                unit: "pcs",
                quantity: "0",
                min_quantity: "0",
                price: "0",
                description: "",
                location: "",
              });
              setAddOpen(true);
            }}
          >
            <Plus className="h-4 w-4" /> Добавить позицию
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-surface-200 bg-white p-1 w-fit">
        <button
          onClick={() => setTab("items")}
          className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            tab === "items" ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900"
          }`}
        >
          <Package className="mr-1.5 inline h-4 w-4" /> Позиции
        </button>
        <button
          onClick={() => setTab("movements")}
          className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            tab === "movements" ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900"
          }`}
        >
          <History className="mr-1.5 inline h-4 w-4" /> Движение
        </button>
      </div>

      {/* Items Tab */}
      {tab === "items" && (
        <>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
            <input
              type="text"
              placeholder="Поиск по названию или артикулу..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-10"
            />
          </div>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14" />
              ))}
            </div>
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-100 text-left text-surface-500">
                      <th className="px-4 py-3 font-medium">Название</th>
                      <th className="px-4 py-3 font-medium">Артикул</th>
                      <th className="px-4 py-3 font-medium text-right">Кол-во</th>
                      <th className="hidden px-4 py-3 font-medium text-right md:table-cell">Резерв</th>
                      <th className="hidden px-4 py-3 font-medium text-right md:table-cell">Доступно</th>
                      <th className="hidden px-4 py-3 font-medium text-right lg:table-cell">Мин. остаток</th>
                      <th className="hidden px-4 py-3 font-medium text-right lg:table-cell">Цена</th>
                      <th className="hidden px-4 py-3 font-medium text-right xl:table-cell">Стоимость</th>
                      <th className="hidden px-4 py-3 font-medium text-right xl:table-cell">Амортизация</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-50">
                    {filteredItems.map((item) => {
                      const available = Number(item.quantity) - Number(item.reserved_quantity);
                      const isLow = Number(item.quantity) <= Number(item.min_quantity);
                      return (
                        <tr
                          key={item.id}
                          className={`transition-colors ${isLow ? "bg-red-50/50" : "hover:bg-surface-50"}`}
                        >
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              {isLow && <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" />}
                              <span className={`font-medium ${isLow ? "text-red-700" : ""}`}>{item.name}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-surface-500 font-mono text-xs">{item.sku}</td>
                          <td className={`px-4 py-3 text-right font-medium ${isLow ? "text-red-600" : ""}`}>
                            {Number(item.quantity)}
                          </td>
                          <td className="hidden px-4 py-3 text-right text-surface-500 md:table-cell">
                            {Number(item.reserved_quantity)}
                          </td>
                          <td className="hidden px-4 py-3 text-right md:table-cell">
                            <span className={available <= 0 ? "text-red-600 font-medium" : "text-surface-600"}>
                              {available}
                            </span>
                          </td>
                          <td className="hidden px-4 py-3 text-right text-surface-500 lg:table-cell">
                            {Number(item.min_quantity)}
                          </td>
                          <td className="hidden px-4 py-3 text-right text-surface-600 lg:table-cell">
                            ₽{Number(item.price).toLocaleString("ru-RU")}
                          </td>
                          <td className="hidden px-4 py-3 text-right text-surface-700 xl:table-cell">
                            ₽{Number(item.cost_total ?? 0).toLocaleString("ru-RU")}
                          </td>
                          <td className="hidden px-4 py-3 text-right text-surface-500 xl:table-cell">
                            ₽{Number(item.depreciation_total ?? 0).toLocaleString("ru-RU")}
                          </td>
                        </tr>
                      );
                    })}
                    {filteredItems.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-surface-400">
                          {search ? "Ничего не найдено" : "Нет складских позиций"}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* Movements Tab */}
      {tab === "movements" && (
        <>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14" />
              ))}
            </div>
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-100 text-left text-surface-500">
                      <th className="px-4 py-3 font-medium">Тип</th>
                      <th className="px-4 py-3 font-medium text-right">Количество</th>
                      <th className="hidden px-4 py-3 font-medium md:table-cell">Причина</th>
                      <th className="px-4 py-3 font-medium">Дата</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-50">
                    {movements.map((mov) => (
                      <tr key={mov.id} className="hover:bg-surface-50 transition-colors">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {movementTypeIcon[mov.movement_type] ?? <ArrowDownUp className="h-4 w-4 text-surface-400" />}
                            <span className="badge bg-surface-100 text-surface-600">{movementTypeLabel[mov.movement_type] ?? mov.movement_type}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right font-medium">{Number(mov.quantity)}</td>
                        <td className="hidden px-4 py-3 text-surface-500 md:table-cell">
                          {mov.reason ?? <span className="text-surface-300">—</span>}
                        </td>
                        <td className="px-4 py-3 text-surface-500">
                          {new Date(mov.created_at).toLocaleString("ru-RU")}
                        </td>
                      </tr>
                    ))}
                    {movements.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-4 py-12 text-center text-surface-400">
                          Движения не зафиксированы
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>

      {addOpen && (
        <Modal
          open={addOpen}
          onClose={() => setAddOpen(false)}
          title="Добавить складскую позицию"
          className="sm:max-w-xl"
          footer={
            <>
              <button
                type="button"
                onClick={() => setAddOpen(false)}
                disabled={addBusy}
                className="btn-ghost"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!addForm.name.trim() || !addForm.sku.trim()) return;
                  setAddBusy(true);
                  setAddError(null);
                  try {
                    await createWarehouseItem({
                      name: addForm.name.trim(),
                      sku: addForm.sku.trim(),
                      category: addForm.category,
                      unit: addForm.unit,
                      quantity: addForm.quantity,
                      min_quantity: addForm.min_quantity,
                      price: addForm.price,
                      description: addForm.description.trim() || null,
                      location: addForm.location.trim() || null,
                    });
                    setAddOpen(false);
                    // Reload items after creating.
                    const res = await fetchWarehouseItems({ limit: 100 });
                    setItems(res.items);
                  } catch (e) {
                    setAddError(e instanceof Error ? e.message : "Ошибка добавления позиции");
                  } finally {
                    setAddBusy(false);
                  }
                }}
                disabled={addBusy || !addForm.name.trim() || !addForm.sku.trim()}
                className="btn-primary"
              >
                {addBusy ? "Сохранение..." : "Сохранить"}
              </button>
            </>
          }
        >
          {addError && (
            <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{addError}</div>
          )}

          <div className="space-y-3">
            <div>
              <div className="mb-1 text-sm text-surface-500">Название</div>
              <input
                className="input w-full"
                value={addForm.name}
                onChange={(e) => setAddForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="Например: Фильтр для кондиционера"
              />
            </div>

            <div>
              <div className="mb-1 text-sm text-surface-500">Артикул (SKU)</div>
              <input
                className="input w-full"
                value={addForm.sku}
                onChange={(e) => setAddForm((p) => ({ ...p, sku: e.target.value }))}
                placeholder="SKU-0001"
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <div className="mb-1 text-sm text-surface-500">Категория</div>
                <select
                  className="input w-full"
                  value={addForm.category}
                  onChange={(e) => setAddForm((p) => ({ ...p, category: e.target.value }))}
                >
                  {categoryOptions.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <div className="mb-1 text-sm text-surface-500">Ед. изм.</div>
                <select
                  className="input w-full"
                  value={addForm.unit}
                  onChange={(e) => setAddForm((p) => ({ ...p, unit: e.target.value }))}
                >
                  {unitOptions.map((u) => (
                    <option key={u.value} value={u.value}>
                      {u.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <div className="mb-1 text-sm text-surface-500">Кол-во</div>
                <input
                  className="input w-full"
                  type="number"
                  step="0.001"
                  value={addForm.quantity}
                  onChange={(e) => setAddForm((p) => ({ ...p, quantity: e.target.value }))}
                />
              </div>
              <div>
                <div className="mb-1 text-sm text-surface-500">Мин. остаток</div>
                <input
                  className="input w-full"
                  type="number"
                  step="0.001"
                  value={addForm.min_quantity}
                  onChange={(e) => setAddForm((p) => ({ ...p, min_quantity: e.target.value }))}
                />
              </div>
              <div>
                <div className="mb-1 text-sm text-surface-500">Цена за ед.</div>
                <input
                  className="input w-full"
                  type="number"
                  step="0.01"
                  value={addForm.price}
                  onChange={(e) => setAddForm((p) => ({ ...p, price: e.target.value }))}
                />
              </div>
            </div>

            <div>
              <div className="mb-1 text-sm text-surface-500">Место хранения</div>
              <input
                className="input w-full"
                value={addForm.location}
                onChange={(e) => setAddForm((p) => ({ ...p, location: e.target.value }))}
                placeholder="Например: Склад-1 / Ячейка A2"
              />
            </div>

            <div>
              <div className="mb-1 text-sm text-surface-500">Описание</div>
              <textarea
                className="input w-full min-h-[90px]"
                value={addForm.description}
                onChange={(e) => setAddForm((p) => ({ ...p, description: e.target.value }))}
                placeholder="Опционально"
              />
            </div>
          </div>
        </Modal>
      )}

      {importOpen && (
        <Modal
          open={importOpen}
          onClose={() => setImportOpen(false)}
          title="Импорт Excel / 1С"
          className="sm:max-w-xl"
          footer={
            <>
              <button type="button" onClick={() => setImportOpen(false)} disabled={importBusy} className="btn-ghost">
                Отмена
              </button>
              <button
                type="button"
                disabled={importBusy || !importFile}
                className="btn-primary"
                onClick={async () => {
                  if (!importFile) return;
                  setImportBusy(true);
                  setImportError(null);
                  setImportResult(null);
                  try {
                    const res = await importWarehouseItemsExcel(importFile);
                    setImportResult(
                      `Создано: ${res.created_count}, обновлено: ${res.updated_count}, пропущено: ${res.skipped_count}, ошибок: ${res.error_count}`,
                    );
                    if (res.errors.length > 0) setImportError(res.errors.slice(0, 3).join("; "));
                    if (res.error_count === 0) setImportOpen(false);
                    const updated = await fetchWarehouseItems({ limit: 100 });
                    setItems(updated.items);
                  } catch (e) {
                    setImportError(e instanceof Error ? e.message : "Ошибка импорта");
                  } finally {
                    setImportBusy(false);
                  }
                }}
              >
                {importBusy ? "Импорт..." : "Импортировать"}
              </button>
            </>
          }
        >
          {importError && (
            <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{importError}</div>
          )}
          {importResult && (
            <div className="mb-3 rounded-lg bg-green-50 p-3 text-sm text-green-800">{importResult}</div>
          )}

          <div className="space-y-3">
            <div className="text-sm text-surface-500">
              Загрузите XLSX-файл. Колонки сопоставляются по названиям:
              <span className="font-medium text-surface-700">Название</span>, <span className="font-medium text-surface-700">Артикул (SKU)</span>,{" "}
              <span className="font-medium text-surface-700">Категория</span>, <span className="font-medium text-surface-700">Ед. изм.</span>,{" "}
              <span className="font-medium text-surface-700">Количество</span>, <span className="font-medium text-surface-700">Мин. остаток</span>,{" "}
              <span className="font-medium text-surface-700">Цена за ед.</span>.
            </div>

            <input
              type="file"
              accept=".xlsx"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setImportFile(f);
                setImportError(null);
                setImportResult(null);
              }}
              className="block w-full text-sm text-surface-600"
              disabled={importBusy}
            />

            {importFile && (
              <div className="rounded-lg border border-surface-100 bg-white/40 p-3 text-sm text-surface-600">
                Файл: <span className="font-medium text-surface-700">{importFile.name}</span>
              </div>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}

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
} from "lucide-react";
import { fetchWarehouseItems, fetchWarehouseMovements } from "@/lib/api";
import type { WarehouseItemResponse, WarehouseMovementResponse } from "@/types";

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

  const movementTypeIcon: Record<string, React.ReactNode> = {
    intake: <ArrowDownCircle className="h-4 w-4 text-green-500" />,
    return: <ArrowDownCircle className="h-4 w-4 text-green-500" />,
    consumption: <ArrowUpCircle className="h-4 w-4 text-red-500" />,
    write_off: <ArrowUpCircle className="h-4 w-4 text-red-500" />,
    transfer: <ArrowDownUp className="h-4 w-4 text-blue-500" />,
  };

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Warehouse</h1>
        <div className="flex items-center gap-2">
          <button className="btn-secondary gap-1.5">
            <ArrowDownUp className="h-4 w-4" /> Record Movement
          </button>
          <button className="btn-primary gap-1.5">
            <Plus className="h-4 w-4" /> Add Item
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
          <Package className="mr-1.5 inline h-4 w-4" /> Items
        </button>
        <button
          onClick={() => setTab("movements")}
          className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            tab === "movements" ? "bg-primary-600 text-white" : "text-surface-500 hover:text-surface-900"
          }`}
        >
          <History className="mr-1.5 inline h-4 w-4" /> Movements
        </button>
      </div>

      {/* Items Tab */}
      {tab === "items" && (
        <>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
            <input
              type="text"
              placeholder="Search by name or SKU..."
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
                      <th className="px-4 py-3 font-medium">Name</th>
                      <th className="px-4 py-3 font-medium">SKU</th>
                      <th className="px-4 py-3 font-medium text-right">Qty</th>
                      <th className="hidden px-4 py-3 font-medium text-right md:table-cell">Reserved</th>
                      <th className="hidden px-4 py-3 font-medium text-right md:table-cell">Available</th>
                      <th className="hidden px-4 py-3 font-medium text-right lg:table-cell">Min Stock</th>
                      <th className="hidden px-4 py-3 font-medium text-right lg:table-cell">Price</th>
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
                        </tr>
                      );
                    })}
                    {filteredItems.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-surface-400">
                          {search ? "No items match" : "No warehouse items"}
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
                      <th className="px-4 py-3 font-medium">Type</th>
                      <th className="px-4 py-3 font-medium text-right">Quantity</th>
                      <th className="hidden px-4 py-3 font-medium md:table-cell">Reason</th>
                      <th className="px-4 py-3 font-medium">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-50">
                    {movements.map((mov) => (
                      <tr key={mov.id} className="hover:bg-surface-50 transition-colors">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {movementTypeIcon[mov.movement_type] ?? <ArrowDownUp className="h-4 w-4 text-surface-400" />}
                            <span className="badge bg-surface-100 text-surface-600">{mov.movement_type}</span>
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
                          No movements recorded
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
  );
}

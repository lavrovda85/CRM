"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Settings,
  Plus,
  Pencil,
  Check,
  X,
  BookOpen,
  ChevronRight,
} from "lucide-react";
import {
  fetchReferences,
  fetchReference,
  createReferenceItem,
  updateReferenceItem,
} from "@/lib/api";
import type { ReferenceResponse, ReferenceItemResponse } from "@/types";

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-200 ${className}`} />;
}

export default function SettingsPage() {
  const [references, setReferences] = useState<ReferenceResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeRef, setActiveRef] = useState<ReferenceResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [newItem, setNewItem] = useState({ code: "", name: "" });
  const [showAdd, setShowAdd] = useState(false);

  const loadRefs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchReferences({ limit: 50 });
      setReferences(res.items);
      if (res.items.length > 0 && !activeRef) {
        await loadRefDetail(res.items[0].code);
      }
    } catch {
      /* empty state */
    } finally {
      setLoading(false);
    }
  }, []);

  async function loadRefDetail(code: string) {
    setDetailLoading(true);
    try {
      const ref = await fetchReference(code);
      setActiveRef(ref);
    } catch {
      /* silent */
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => { loadRefs(); }, [loadRefs]);

  async function handleAddItem() {
    if (!activeRef || !newItem.code || !newItem.name) return;
    try {
      await createReferenceItem(activeRef.code, newItem);
      setNewItem({ code: "", name: "" });
      setShowAdd(false);
      await loadRefDetail(activeRef.code);
    } catch {
      /* silent */
    }
  }

  async function handleUpdateItem(itemId: string) {
    if (!activeRef || !editName.trim()) return;
    try {
      await updateReferenceItem(activeRef.code, itemId, { name: editName });
      setEditingItem(null);
      await loadRefDetail(activeRef.code);
    } catch {
      /* silent */
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-4 lg:p-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-64" />
          <Skeleton className="h-64 lg:col-span-2" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 lg:p-6">
      <div className="flex items-center gap-2">
        <Settings className="h-6 w-6 text-surface-500" />
        <h1 className="text-2xl font-bold">Settings</h1>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Reference Tabs */}
        <div className="card">
          <div className="border-b border-surface-100 p-4">
            <h2 className="font-semibold flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-primary-500" /> Dictionaries
            </h2>
          </div>
          <div className="divide-y divide-surface-50">
            {references.map((ref) => (
              <button
                key={ref.id}
                onClick={() => loadRefDetail(ref.code)}
                className={`flex w-full items-center justify-between p-3 text-left transition-colors ${
                  activeRef?.code === ref.code
                    ? "bg-primary-50 text-primary-700"
                    : "hover:bg-surface-50"
                }`}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{ref.name}</p>
                  <p className="text-xs text-surface-400 font-mono">{ref.code}</p>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-surface-300" />
              </button>
            ))}
            {references.length === 0 && (
              <p className="p-6 text-center text-sm text-surface-400">No dictionaries</p>
            )}
          </div>
        </div>

        {/* Reference Items */}
        <div className="card lg:col-span-2">
          {activeRef ? (
            <>
              <div className="flex items-center justify-between border-b border-surface-100 p-4">
                <div>
                  <h2 className="font-semibold">{activeRef.name}</h2>
                  {activeRef.description && (
                    <p className="mt-0.5 text-sm text-surface-500">{activeRef.description}</p>
                  )}
                </div>
                <button onClick={() => setShowAdd(true)} className="btn-primary btn-sm gap-1">
                  <Plus className="h-3.5 w-3.5" /> Add
                </button>
              </div>

              {showAdd && (
                <div className="border-b border-surface-100 bg-surface-50 p-4">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Code"
                      className="input max-w-[120px]"
                      value={newItem.code}
                      onChange={(e) => setNewItem({ ...newItem, code: e.target.value })}
                    />
                    <input
                      type="text"
                      placeholder="Name"
                      className="input flex-1"
                      value={newItem.name}
                      onChange={(e) => setNewItem({ ...newItem, name: e.target.value })}
                    />
                    <button onClick={handleAddItem} className="btn-primary btn-sm" disabled={!newItem.code || !newItem.name}>
                      <Check className="h-4 w-4" />
                    </button>
                    <button onClick={() => { setShowAdd(false); setNewItem({ code: "", name: "" }); }} className="btn-ghost btn-sm">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}

              {detailLoading ? (
                <div className="p-4 space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-10" />
                  ))}
                </div>
              ) : (
                <div className="divide-y divide-surface-50">
                  {activeRef.items
                    .sort((a, b) => a.order - b.order)
                    .map((item) => (
                      <div key={item.id} className="flex items-center justify-between p-3">
                        {editingItem === item.id ? (
                          <div className="flex flex-1 items-center gap-2">
                            <input
                              type="text"
                              className="input flex-1"
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              autoFocus
                              onKeyDown={(e) => e.key === "Enter" && handleUpdateItem(item.id)}
                            />
                            <button onClick={() => handleUpdateItem(item.id)} className="btn-primary btn-sm">
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button onClick={() => setEditingItem(null)} className="btn-ghost btn-sm">
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        ) : (
                          <>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium">{item.name}</span>
                                <span className="text-xs text-surface-400 font-mono">{item.code}</span>
                                {!item.is_active && (
                                  <span className="badge bg-surface-100 text-surface-400 text-[10px]">inactive</span>
                                )}
                              </div>
                            </div>
                            <button
                              onClick={() => { setEditingItem(item.id); setEditName(item.name); }}
                              className="btn-ghost btn-sm"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    ))}
                  {activeRef.items.length === 0 && (
                    <p className="p-8 text-center text-sm text-surface-400">
                      No items in this dictionary
                    </p>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center py-16 text-surface-400">
              <p className="text-sm">Select a dictionary to manage its items</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

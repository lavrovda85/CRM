"use client";

/**
 * Client picker with debounced server search (same `/clients?search=` API as the Clients page).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchClient, fetchClients } from "@/lib/api";
import type { ClientResponse } from "@/types";

export interface ClientSearchSelectProps {
  /** Selected client UUID, empty string, or ``newOptionValue`` when "create new" is chosen. */
  value: string;
  onChange: (clientId: string) => void;
  disabled?: boolean;
  label?: string;
  selectId?: string;
  /** When set, adds an extra option that triggers ``onChange(newOptionValue)``. */
  newOptionValue?: string;
  newOptionLabel?: string;
  /** Called instead of ``onChange`` when the user should be taken elsewhere (e.g. full create form). */
  onPickCreateNew?: () => void;
}

export function ClientSearchSelect({
  value,
  onChange,
  disabled = false,
  label = "Клиент",
  selectId = "client-search-select",
  newOptionValue,
  newOptionLabel = "+ Создать клиента…",
  onPickCreateNew,
}: ClientSearchSelectProps) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [items, setItems] = useState<ClientResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [pinned, setPinned] = useState<ClientResponse | null>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(query.trim()), 300);
    return () => window.clearTimeout(t);
  }, [query]);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchClients({
        search: debounced || undefined,
        limit: 100,
        offset: 0,
      });
      setItems(res.items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [debounced]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (!value || (newOptionValue && value === newOptionValue)) {
      setPinned(null);
      return;
    }
    if (items.some((c) => c.id === value)) {
      setPinned(null);
      return;
    }
    let cancelled = false;
    void fetchClient(value)
      .then((c) => {
        if (!cancelled) setPinned(c);
      })
      .catch(() => {
        if (!cancelled) setPinned(null);
      });
    return () => {
      cancelled = true;
    };
  }, [value, items, newOptionValue]);

  const options = useMemo(() => {
    const out: ClientResponse[] = [...items];
    if (pinned && !out.some((c) => c.id === pinned.id)) {
      out.unshift(pinned);
    }
    return out;
  }, [items, pinned]);

  return (
    <div className="space-y-2">
      <label htmlFor={`${selectId}-q`} className="mb-1 block text-sm font-medium text-surface-700">
        {label}
      </label>
      <input
        id={`${selectId}-q`}
        type="search"
        className="input w-full"
        placeholder="Поиск по имени, телефону, email, адресу, ИНН, контактам…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={disabled}
        autoComplete="off"
      />
      {loading && <p className="text-xs text-surface-400">Загрузка…</p>}
      <select
        id={selectId}
        className="input w-full"
        value={value}
        disabled={disabled}
        onChange={(e) => {
          const v = e.target.value;
          if (newOptionValue && v === newOptionValue) {
            if (onPickCreateNew) {
              onPickCreateNew();
              return;
            }
            onChange(newOptionValue);
            return;
          }
          onChange(v);
        }}
      >
        <option value="">Не выбран</option>
        {options.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
            {c.phone ? ` · ${c.phone}` : ""}
            {c.email ? ` · ${c.email}` : ""}
          </option>
        ))}
        {newOptionValue ? (
          <option value={newOptionValue}>{newOptionLabel}</option>
        ) : null}
      </select>
    </div>
  );
}

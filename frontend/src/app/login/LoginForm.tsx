"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ACTIVE_COMPANY_ID_STORAGE_KEY, ApiError, fetchCompanyLoginOptions } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import type { CompanyLoginOption } from "@/types";

/**
 * Login form (client). Uses `useSearchParams`; must be under Suspense in the parent page.
 */
export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const login = useAuthStore((s) => s.login);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [companies, setCompanies] = useState<CompanyLoginOption[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = searchParams.get("next") || "/dashboard";

  useEffect(() => {
    let cancelled = false;
    setCompaniesLoading(true);
    void fetchCompanyLoginOptions()
      .then((list) => {
        if (cancelled) return;
        setCompanies(list);
        if (list.length === 1) {
          setCompanyId(list[0].id);
          return;
        }
        const saved =
          typeof window !== "undefined"
            ? localStorage.getItem(ACTIVE_COMPANY_ID_STORAGE_KEY)?.trim()
            : null;
        if (saved && list.some((c) => c.id === saved)) {
          setCompanyId(saved);
        }
      })
      .catch(() => {
        if (!cancelled) setCompanies([]);
      })
      .finally(() => {
        if (!cancelled) setCompaniesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (companies.length > 0 && !companyId.trim()) {
      setError("Выберите компанию");
      return;
    }
    setSubmitting(true);
    try {
      await login(email, password, companyId.trim() || null);
      router.replace(redirectTo);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Login failed";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-md p-4">
      <div className="rounded-lg border border-surface-100 bg-white p-5">
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">
              {error}
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">Компания</label>
            {companiesLoading ? (
              <p className="text-sm text-surface-500">Загрузка списка…</p>
            ) : companies.length === 0 ? (
              <p className="text-sm text-surface-500">
                Организации не найдены — вход без выбора (будет назначена по умолчанию).
              </p>
            ) : (
              <select
                className="input w-full"
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
                required={companies.length > 0}
                aria-label="Компания"
              >
                <option value="">— Выберите компанию —</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.slug ? ` (${c.slug})` : ""}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">Email</label>
            <input
              className="input w-full"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">Пароль</label>
            <input
              className="input w-full"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? "Вход..." : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}

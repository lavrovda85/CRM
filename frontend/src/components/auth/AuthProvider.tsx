"use client";

import { ReactNode, useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuthStore } from "@/stores/auth";

/**
 * Wraps authenticated routes: restores session, redirects unauthenticated users to /login.
 *
 * Login is not blocked by session bootstrap. Redirects to `/login` are debounced with a ref
 * so unstable `useRouter` / Strict Mode does not spam `router.replace` (which can freeze Next).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const initialize = useAuthStore((s) => s.initialize);
  const isLoading = useAuthStore((s) => s.isLoading);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const isLoginRoute = pathname === "/login";
  /** Prevents repeated `replace('/login?...')` while still on a protected route (infinite navigation churn). */
  const toLoginRedirectIssued = useRef(false);

  useEffect(() => {
    void initialize().catch(() => {
      useAuthStore.setState({
        isLoading: false,
        user: null,
        token: null,
        isAuthenticated: false,
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isLoading) return;

    if (isLoginRoute) {
      toLoginRedirectIssued.current = false;
    }

    if (isLoginRoute && isAuthenticated) {
      const next = new URLSearchParams(window.location.search).get("next");
      const safe =
        next &&
        next.startsWith("/") &&
        !next.startsWith("//") &&
        !next.includes("://");
      router.replace(safe ? next : "/dashboard");
      return;
    }

    if (isLoginRoute) return;

    if (!isAuthenticated) {
      if (toLoginRedirectIssued.current) return;
      toLoginRedirectIssued.current = true;
      const qs =
        typeof window !== "undefined" && window.location.search.length > 1
          ? window.location.search.slice(1)
          : "";
      const returnTo = `${pathname}${qs ? `?${qs}` : ""}`;
      const next =
        returnTo === "/login" || returnTo.startsWith("/login?") ? "/" : returnTo;
      router.replace(`/login?next=${encodeURIComponent(next)}`);
    }
  }, [isAuthenticated, isLoading, isLoginRoute, pathname, router]);

  if (isLoginRoute) {
    return <>{children}</>;
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 text-surface-600">
        <Loader2 className="h-5 w-5 animate-spin text-primary-600" aria-hidden />
        <p className="text-sm">Загрузка сессии…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 text-surface-600">
        <Loader2 className="h-5 w-5 animate-spin text-primary-600" aria-hidden />
        <p className="text-sm">Требуется вход. Перенаправление…</p>
      </div>
    );
  }

  return <>{children}</>;
}

/**
 * Top header bar with page title, search, notifications, and user menu.
 *
 * Верхняя панель приложения: заголовок, поиск, колокольчик с inbox
 * (опрос непрочитанных и список уведомлений по задачам), меню пользователя.
 */

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Search,
  Bell,
  ChevronDown,
  LogOut,
  User,
  Menu,
  Loader2,
  Building2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import { useCompanyStore } from "@/stores/company";
import { useUiStore } from "@/stores/ui";
import {
  fetchInboxNotifications,
  fetchUnreadNotificationCount,
  markInboxNotificationRead,
  markAllInboxNotificationsRead,
} from "@/lib/api";
import { playNotificationSound } from "@/lib/notificationSound";
import type { InboxNotificationItem } from "@/types";

const POLL_MS = 60_000;

interface HeaderProps {
  title?: string;
}

export function Header({ title }: HeaderProps) {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const memberships = useCompanyStore((s) => s.memberships);
  const activeCompanyId = useCompanyStore((s) => s.activeCompanyId);
  const setActiveCompanyId = useCompanyStore((s) => s.setActiveCompanyId);
  const loadCompanies = useCompanyStore((s) => s.loadFromApi);
  const toggleMobileSidebar = useUiStore((s) => s.toggleMobileSidebar);
  const searchOpen = useUiStore((s) => s.searchOpen);
  const toggleSearch = useUiStore((s) => s.toggleSearch);
  const setSearchOpen = useUiStore((s) => s.setSearchOpen);
  const tasksSearchDraft = useUiStore((s) => s.tasksSearchDraft);
  const setTasksSearchDraft = useUiStore((s) => s.setTasksSearchDraft);
  const headerToolbar = useUiStore((s) => s.headerToolbar);
  const searchPaletteRef = useRef<HTMLInputElement>(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [notifOpen, setNotifOpen] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);
  const [notifItems, setNotifItems] = useState<InboxNotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifLoading, setNotifLoading] = useState(false);
  const [searchShortcutLabel, setSearchShortcutLabel] = useState("Ctrl+K");
  const prevUnreadRef = useRef<number | null>(null);

  useEffect(() => {
    prevUnreadRef.current = null;
  }, [user?.id]);

  const refreshUnread = useCallback(async () => {
    try {
      const { unread_count } = await fetchUnreadNotificationCount();
      const prev = prevUnreadRef.current;
      if (prev !== null && unread_count > prev) {
        playNotificationSound();
      }
      prevUnreadRef.current = unread_count;
      setUnreadCount(unread_count);
    } catch {
      /* not authenticated or offline */
    }
  }, []);

  const loadInbox = useCallback(async () => {
    setNotifLoading(true);
    try {
      const res = await fetchInboxNotifications({ limit: 40 });
      setNotifItems(res.items);
      await refreshUnread();
    } catch {
      setNotifItems([]);
    } finally {
      setNotifLoading(false);
    }
  }, [refreshUnread]);

  useEffect(() => {
    refreshUnread();
    const t = setInterval(refreshUnread, POLL_MS);
    return () => clearInterval(t);
  }, [refreshUnread]);

  useEffect(() => {
    if (user) void loadCompanies();
  }, [user, loadCompanies]);

  useEffect(() => {
    setSearchShortcutLabel(
      typeof navigator !== "undefined" && /Mac|iPhone|iPad/i.test(navigator.userAgent) ? "⌘K" : "Ctrl+K",
    );
  }, []);

  useEffect(() => {
    if (notifOpen) {
      loadInbox();
    }
  }, [notifOpen, loadInbox]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    }
    if (notifOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [notifOpen]);

  useEffect(() => {
    function onGlobalKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        toggleSearch();
      }
    }
    window.addEventListener("keydown", onGlobalKey);
    return () => window.removeEventListener("keydown", onGlobalKey);
  }, [toggleSearch]);

  useEffect(() => {
    if (!searchOpen) return;
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setSearchOpen(false);
    }
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [searchOpen, setSearchOpen]);

  useEffect(() => {
    if (searchOpen) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      const t = window.setTimeout(() => searchPaletteRef.current?.focus(), 0);
      return () => {
        window.clearTimeout(t);
        document.body.style.overflow = prev;
      };
    }
  }, [searchOpen]);

  const onTasksSearchPaletteKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key !== "Enter") return;
      if (pathname === "/tasks") return;
      e.preventDefault();
      router.push("/tasks");
      setSearchOpen(false);
    },
    [pathname, router, setSearchOpen],
  );

  async function handleNotifClick(n: InboxNotificationItem) {
    if (!n.is_read) {
      try {
        await markInboxNotificationRead(n.id);
        setNotifItems((list) => list.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
        setUnreadCount((c) => Math.max(0, c - 1));
      } catch {
        /* ignore */
      }
    }
    const taskId = typeof n.data?.task_id === "string" ? n.data.task_id : null;
    setNotifOpen(false);
    if (taskId) {
      router.push(`/tasks/${taskId}`);
    }
  }

  async function handleMarkAllRead() {
    try {
      await markAllInboxNotificationsRead();
      setNotifItems((list) => list.map((x) => ({ ...x, is_read: true })));
      setUnreadCount(0);
    } catch {
      /* ignore */
    }
  }

  const initials = user?.full_name
    ?.split(" ")
    .map((part: string) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <>
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-surface-100 bg-white/95 backdrop-blur px-4 supports-[backdrop-filter]:bg-white/80">
      <button
        onClick={toggleMobileSidebar}
        className="rounded-lg p-1.5 text-surface-500 hover:bg-surface-100 md:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      {(title || pathname === "/tasks") && (
        <h1 className="hidden shrink-0 text-base font-semibold text-surface-900 sm:block">
          {pathname === "/tasks" ? "Задачи" : title}
        </h1>
      )}

      <div className="flex min-w-0 flex-1 items-center justify-center gap-2 overflow-x-auto px-1 [-ms-overflow-style:none] [scrollbar-width:none] sm:px-2 [&::-webkit-scrollbar]:hidden">
        {headerToolbar}
      </div>

      <div className="relative hidden sm:block">
        <button
          onClick={toggleSearch}
          className={cn(
            "flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition-colors",
            searchOpen
              ? "border-primary-300 bg-primary-50 text-primary-700"
              : "border-surface-200 text-surface-400 hover:border-surface-300 hover:text-surface-500",
          )}
        >
          <Search className="h-4 w-4" />
          <span className="hidden lg:inline">Поиск…</span>
          <kbd className="ml-2 hidden rounded bg-surface-100 px-1.5 py-0.5 text-[10px] font-mono text-surface-400 lg:inline">
            {searchShortcutLabel}
          </kbd>
        </button>
      </div>

      <button
        onClick={toggleSearch}
        className="rounded-lg p-1.5 text-surface-500 hover:bg-surface-100 sm:hidden"
      >
        <Search className="h-5 w-5" />
      </button>

      {user && memberships.length > 0 && (
        <div className="hidden min-w-0 max-w-[11rem] shrink-0 md:flex md:items-center">
          <label htmlFor="company-switcher" className="sr-only">
            Компания
          </label>
          <div className="flex w-full items-center gap-1.5 rounded-lg border border-surface-200 bg-white px-2 py-1">
            <Building2 className="h-4 w-4 shrink-0 text-surface-400" aria-hidden />
            <select
              id="company-switcher"
              value={activeCompanyId ?? memberships[0]?.company.id ?? ""}
              onChange={(e) => setActiveCompanyId(e.target.value.trim() || null)}
              className="min-w-0 flex-1 cursor-pointer truncate border-0 bg-transparent py-0.5 text-sm text-surface-800 focus:outline-none focus:ring-0"
            >
              {memberships.map((m) => (
                <option key={m.company.id} value={m.company.id}>
                  {m.company.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      <div className="relative" ref={notifRef}>
        <button
          type="button"
          onClick={() => setNotifOpen((o) => !o)}
          className="relative rounded-lg p-1.5 text-surface-500 hover:bg-surface-100"
          aria-expanded={notifOpen}
          aria-label="Уведомления"
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute right-0.5 top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </button>

        {notifOpen && (
          <div className="absolute right-0 top-full mt-1 w-[min(100vw-2rem,22rem)] rounded-xl border border-surface-100 bg-white py-2 shadow-lg">
            <div className="flex items-center justify-between border-b border-surface-100 px-3 pb-2">
              <span className="text-sm font-semibold text-surface-900">Уведомления</span>
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={handleMarkAllRead}
                  className="text-xs font-medium text-primary-600 hover:underline"
                >
                  Прочитать все
                </button>
              )}
            </div>
            <div className="max-h-[min(70vh,20rem)] overflow-y-auto">
              {notifLoading ? (
                <div className="flex justify-center py-8 text-surface-400">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : notifItems.length === 0 ? (
                <p className="px-3 py-6 text-center text-sm text-surface-500">Нет уведомлений</p>
              ) : (
                <ul className="divide-y divide-surface-50">
                  {notifItems.map((n) => (
                    <li key={n.id}>
                      <button
                        type="button"
                        onClick={() => handleNotifClick(n)}
                        className={cn(
                          "w-full px-3 py-2.5 text-left text-sm transition-colors hover:bg-surface-50",
                          !n.is_read && "bg-primary-50/40",
                        )}
                      >
                        <div className="font-medium text-surface-900">{n.title}</div>
                        <div className="mt-0.5 line-clamp-2 text-surface-600">{n.body}</div>
                        <div className="mt-1 text-[11px] text-surface-400">
                          {new Date(n.created_at).toLocaleString("ru-RU", {
                            day: "numeric",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="relative" ref={menuRef}>
        <button
          onClick={() => setUserMenuOpen((prev) => !prev)}
          className="flex items-center gap-2 rounded-lg p-1 transition-colors hover:bg-surface-100"
        >
          {user?.avatar_url ? (
            <img
              src={
                user.avatar_url.includes("?")
                  ? `${user.avatar_url}&cb=${encodeURIComponent(user.updated_at)}`
                  : `${user.avatar_url}?cb=${encodeURIComponent(user.updated_at)}`
              }
              alt={user.full_name || "User"}
              className="h-8 w-8 rounded-full object-cover"
            />
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-600 text-xs font-medium text-white">
              {initials || "U"}
            </div>
          )}
          <ChevronDown
            className={cn(
              "hidden h-4 w-4 text-surface-400 transition-transform sm:block",
              userMenuOpen && "rotate-180",
            )}
          />
        </button>

        {userMenuOpen && (
          <div className="absolute right-0 top-full mt-1 w-56 rounded-xl border border-surface-100 bg-white py-1 shadow-lg">
            {user && (
              <div className="border-b border-surface-100 px-3 py-2">
                <p className="truncate text-sm font-medium text-surface-900">
                  {user.full_name}
                </p>
                <p className="truncate text-xs text-surface-400">{user.email}</p>
              </div>
            )}

            <Link
              href="/profile"
              prefetch
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-surface-600 hover:bg-surface-50"
              onClick={() => setUserMenuOpen(false)}
            >
              <User className="h-4 w-4 shrink-0" aria-hidden />
              Профиль
            </Link>

            <button
              onClick={() => {
                setUserMenuOpen(false);
                logout();
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
            >
              <LogOut className="h-4 w-4" />
              Выйти
            </button>
          </div>
        )}
      </div>
    </header>

    {searchOpen && (
      <div
        className="fixed inset-0 z-[100] flex items-start justify-center bg-black/40 px-4 pt-[12vh] sm:pt-[18vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="global-task-search-title"
      >
        <button
          type="button"
          className="absolute inset-0 cursor-default"
          tabIndex={-1}
          aria-label="Закрыть"
          onClick={() => setSearchOpen(false)}
        />
        <div
          className="relative w-full max-w-lg rounded-xl border border-surface-100 bg-white p-4 shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          <p id="global-task-search-title" className="mb-3 text-sm font-semibold text-surface-900">
            Поиск задач
          </p>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400"
              aria-hidden
            />
            <input
              id="global-task-search"
              ref={searchPaletteRef}
              type="search"
              value={tasksSearchDraft}
              onChange={(e) => setTasksSearchDraft(e.target.value)}
              onKeyDown={onTasksSearchPaletteKeyDown}
              placeholder={
                pathname === "/tasks"
                  ? "Название или описание…"
                  : "Введите запрос и нажмите Enter"
              }
              className="input w-full pl-10"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              aria-label="Поиск задач по названию и описанию"
            />
          </div>
          {pathname !== "/tasks" ? (
            <p className="mt-2 text-xs text-surface-500">
              Enter — открыть раздел «Задачи» с этим запросом. Здесь же можно искать, находясь в «Задачах».
            </p>
          ) : (
            <p className="mt-2 text-xs text-surface-500">
              Совпадения по названию и описанию. Esc — закрыть.
            </p>
          )}
        </div>
      </div>
    )}
    </>
  );
}

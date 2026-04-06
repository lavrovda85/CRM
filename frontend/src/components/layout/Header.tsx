/**
 * Top header bar with page title, search, notifications, and user menu.
 *
 * Верхняя панель приложения, содержащая:
 * - Заголовок текущей страницы (передаётся через prop).
 * - Поле поиска (placeholder).
 * - Иконку уведомлений с индикатором.
 * - Аватар пользователя с выпадающим меню.
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { Search, Bell, ChevronDown, LogOut, User, Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";

interface HeaderProps {
  title?: string;
}

export function Header({ title }: HeaderProps) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const toggleMobileSidebar = useUiStore((s) => s.toggleMobileSidebar);
  const searchOpen = useUiStore((s) => s.searchOpen);
  const toggleSearch = useUiStore((s) => s.toggleSearch);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const initials = user?.full_name
    ?.split(" ")
    .map((part: string) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-surface-100 bg-white/95 backdrop-blur px-4 supports-[backdrop-filter]:bg-white/80">
      {/* Mobile menu toggle */}
      <button
        onClick={toggleMobileSidebar}
        className="rounded-lg p-1.5 text-surface-500 hover:bg-surface-100 md:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Page title */}
      {title && (
        <h1 className="text-base font-semibold text-surface-900 hidden sm:block">
          {title}
        </h1>
      )}

      <div className="flex-1" />

      {/* Search */}
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
          <span className="hidden lg:inline">Search…</span>
          <kbd className="ml-2 hidden rounded bg-surface-100 px-1.5 py-0.5 text-[10px] font-mono text-surface-400 lg:inline">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Mobile search */}
      <button
        onClick={toggleSearch}
        className="rounded-lg p-1.5 text-surface-500 hover:bg-surface-100 sm:hidden"
      >
        <Search className="h-5 w-5" />
      </button>

      {/* Notifications */}
      <button className="relative rounded-lg p-1.5 text-surface-500 hover:bg-surface-100">
        <Bell className="h-5 w-5" />
        <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500" />
      </button>

      {/* User menu */}
      <div className="relative" ref={menuRef}>
        <button
          onClick={() => setUserMenuOpen((prev) => !prev)}
          className="flex items-center gap-2 rounded-lg p-1 hover:bg-surface-100 transition-colors"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-600 text-xs font-medium text-white">
            {initials || "U"}
          </div>
          <ChevronDown
            className={cn(
              "h-4 w-4 text-surface-400 transition-transform hidden sm:block",
              userMenuOpen && "rotate-180",
            )}
          />
        </button>

        {userMenuOpen && (
          <div className="absolute right-0 top-full mt-1 w-56 rounded-xl border border-surface-100 bg-white py-1 shadow-lg">
            {user && (
              <div className="border-b border-surface-100 px-3 py-2">
                <p className="text-sm font-medium text-surface-900 truncate">
                  {user.full_name}
                </p>
                <p className="text-xs text-surface-400 truncate">
                  {user.email}
                </p>
              </div>
            )}

            <button
              onClick={() => {
                setUserMenuOpen(false);
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-surface-600 hover:bg-surface-50"
            >
              <User className="h-4 w-4" />
              Profile
            </button>

            <button
              onClick={() => {
                setUserMenuOpen(false);
                logout();
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

/**
 * Bottom navigation bar for mobile devices.
 *
 * Нижняя панель навигации, отображаемая только на мобильных устройствах (md:hidden).
 * Содержит 5 основных пунктов: Dashboard, Tasks, Time, Clients и More.
 * Кнопка "More" открывает полноэкранное меню со всеми разделами.
 */

"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard,
  CheckSquare,
  Users,
  Clock,
  MoreHorizontal,
  TrendingUp,
  FileText,
  FileStack,
  Package,
  Wrench,
  BarChart3,
  Settings,
  MessageSquareText,
  Sparkles,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui";

interface MobileNavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const PRIMARY_ITEMS: MobileNavItem[] = [
  { label: "Главная", href: "/", icon: LayoutDashboard },
  { label: "Задачи", href: "/tasks", icon: CheckSquare },
  { label: "Время", href: "/time", icon: Clock },
  { label: "Клиенты", href: "/clients", icon: Users },
];

const ALL_ITEMS: MobileNavItem[] = [
  { label: "Главная", href: "/", icon: LayoutDashboard },
  { label: "Задачи", href: "/tasks", icon: CheckSquare },
  { label: "Шаблоны", href: "/templates", icon: FileStack },
  { label: "Клиенты", href: "/clients", icon: Users },
  { label: "Сделки", href: "/deals", icon: TrendingUp },
  { label: "Тендеры", href: "/tenders", icon: FileText },
  { label: "Время", href: "/time", icon: Clock },
  { label: "Склад", href: "/warehouse", icon: Package },
  { label: "Оборудование", href: "/equipment", icon: Wrench },
  { label: "Аналитика", href: "/analytics", icon: BarChart3 },
  { label: "Чат", href: "/chat", icon: MessageSquareText },
  { label: "AI", href: "/assistant", icon: Sparkles },
  { label: "Настройки", href: "/settings", icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

export function MobileNav() {
  const pathname = usePathname();
  const menuOpen = useUiStore((s) => s.mobileMenuOpen);
  const setMenuOpen = useUiStore((s) => s.setMobileMenuOpen);

  return (
    <>
      {/* Bottom tab bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 flex md:hidden border-t border-surface-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
        {PRIMARY_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px]",
                active
                  ? "text-primary-600 font-medium"
                  : "text-surface-400",
              )}
            >
              <Icon className="h-5 w-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}

        {/* More button */}
        <button
          onClick={() => setMenuOpen(true)}
          className={cn(
            "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px]",
            menuOpen ? "text-primary-600 font-medium" : "text-surface-400",
          )}
        >
          <MoreHorizontal className="h-5 w-5" />
          <span>Ещё</span>
        </button>
      </nav>

      {/* Full-screen overlay menu */}
      {menuOpen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-white md:hidden">
          <div className="flex items-center justify-between border-b border-surface-100 px-4 py-3">
            <span className="text-base font-semibold text-surface-900">
              Меню
            </span>
            <button
              onClick={() => setMenuOpen(false)}
              className="rounded-lg p-1.5 text-surface-500 hover:bg-surface-100"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2 py-3">
            <div className="grid grid-cols-3 gap-2">
              {ALL_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    className={cn(
                      "flex flex-col items-center gap-2 rounded-xl p-4 transition-colors",
                      active
                        ? "bg-primary-50 text-primary-600"
                        : "text-surface-600 hover:bg-surface-50",
                    )}
                  >
                    <Icon className="h-6 w-6" />
                    <span className="text-xs font-medium">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

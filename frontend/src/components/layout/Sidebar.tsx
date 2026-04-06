/**
 * Collapsible desktop sidebar navigation component.
 *
 * Боковая панель навигации для десктопа с возможностью сворачивания
 * до режима "только иконки". Тёмная тема (bg-surface-900), подсветка
 * активного маршрута, иконки из lucide-react.
 */

"use client";

import { useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard,
  CheckSquare,
  Users,
  UserCog,
  TrendingUp,
  FileText,
  FileStack,
  Clock,
  Package,
  Wrench,
  BarChart3,
  Settings,
  ChevronsLeft,
  ChevronsRight,
  Shield,
  MessageSquareText,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui";
import { useAuthStore } from "@/stores/auth";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Главная", href: "/", icon: LayoutDashboard },
  { label: "Задачи", href: "/tasks", icon: CheckSquare },
  { label: "Шаблоны", href: "/templates", icon: FileStack },
  { label: "Клиенты", href: "/clients", icon: Users },
  { label: "Сделки", href: "/deals", icon: TrendingUp },
  { label: "Тендеры", href: "/tenders", icon: FileText },
  { label: "Чат", href: "/chat", icon: MessageSquareText },
  { label: "AI", href: "/assistant", icon: Sparkles },
  { label: "Учёт времени", href: "/time", icon: Clock },
  { label: "Склад", href: "/warehouse", icon: Package },
  { label: "Оборудование", href: "/equipment", icon: Wrench },
  { label: "Аналитика", href: "/analytics", icon: BarChart3 },
];

const BOTTOM_ITEMS: NavItem[] = [
  { label: "Пользователи", href: "/settings/users", icon: UserCog },
  { label: "Настройки", href: "/settings", icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

function localDayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);
  const authUser = useAuthStore((s) => s.user);
  const isAdmin = authUser?.role === "admin";
  const selectedDay = searchParams.get("calendar_date") || localDayKey(new Date());
  const tasksView = searchParams.get("view");
  const isTasksCalendar =
    pathname.startsWith("/tasks") && (tasksView === "timeline" || tasksView === "month");

  const { monthDays, monthLabel } = useMemo(() => {
    const [yRaw, mRaw] = selectedDay.split("-").map((x) => Number(x));
    const y = Number.isFinite(yRaw) ? yRaw : new Date().getFullYear();
    const m = Number.isFinite(mRaw) ? mRaw : new Date().getMonth() + 1;
    const monthStart = new Date(y, m - 1, 1, 0, 0, 0, 0);
    const firstWeekday = (monthStart.getDay() + 6) % 7;
    const gridStart = new Date(monthStart);
    gridStart.setDate(1 - firstWeekday);
    const days: string[] = [];
    for (let i = 0; i < 42; i += 1) {
      const d = new Date(gridStart);
      d.setDate(gridStart.getDate() + i);
      days.push(localDayKey(d));
    }
    return {
      monthDays: days,
      monthLabel: monthStart.toLocaleDateString("ru-RU", { month: "long", year: "numeric" }),
    };
  }, [selectedDay]);

  function setCalendarDate(dayKey: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("calendar_date", dayKey);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  return (
    <aside
      className={cn(
        "hidden md:flex flex-col h-screen bg-surface-900 text-white transition-all duration-200 ease-in-out",
        collapsed ? "w-16" : "w-60",
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 border-b border-white/10 px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-600 text-sm font-bold">
          S
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold tracking-tight whitespace-nowrap">
            SPEC CRM
          </span>
        )}
      </div>

      {!collapsed && isTasksCalendar && (
        <div className="border-b border-white/10 px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-surface-400">Календарь</div>
          <div className="mt-2 text-xs text-surface-300 capitalize">{monthLabel}</div>
          <div className="mt-2 grid grid-cols-7 gap-1 text-center text-[10px] text-surface-500">
            {["пн", "вт", "ср", "чт", "пт", "сб", "вс"].map((w) => (
              <div key={w}>{w}</div>
            ))}
            {monthDays.map((dk) => {
              const isSelected = dk === selectedDay;
              const currentMonth = dk.slice(0, 7) === selectedDay.slice(0, 7);
              return (
                <button
                  key={dk}
                  type="button"
                  onClick={() => setCalendarDate(dk)}
                  className={cn(
                    "h-6 rounded text-[11px] transition-colors",
                    isSelected
                      ? "bg-primary-600 text-white"
                      : currentMonth
                        ? "text-surface-200 hover:bg-white/10"
                        : "text-surface-600 hover:bg-white/10",
                  )}
                  title={dk}
                >
                  {Number(dk.slice(-2))}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Main nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            active={isActive(pathname, item.href)}
            collapsed={collapsed}
          />
        ))}
      </nav>

      {/* Bottom items */}
      <div className="border-t border-white/10 px-2 py-3 space-y-0.5">
        {BOTTOM_ITEMS.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            active={isActive(pathname, item.href)}
            collapsed={collapsed}
          />
        ))}
        {isAdmin && (
          <NavLink
            item={{ label: "Админка", href: "/settings/admin", icon: Shield }}
            active={isActive(pathname, "/settings/admin")}
            collapsed={collapsed}
          />
        )}

        {/* Collapse toggle */}
        <button
          onClick={toggle}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-surface-400 hover:bg-white/5 hover:text-white transition-colors"
        >
          {collapsed ? (
            <ChevronsRight className="h-5 w-5 shrink-0" />
          ) : (
            <>
              <ChevronsLeft className="h-5 w-5 shrink-0" />
              <span>Свернуть</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}

function NavLink({
  item,
  active,
  collapsed,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
}) {
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      title={collapsed ? item.label : undefined}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
        active
          ? "bg-primary-600/20 text-primary-300 font-medium"
          : "text-surface-400 hover:bg-white/5 hover:text-white",
        collapsed && "justify-center px-0",
      )}
    >
      <Icon className="h-5 w-5 shrink-0" />
      {!collapsed && <span>{item.label}</span>}
    </Link>
  );
}

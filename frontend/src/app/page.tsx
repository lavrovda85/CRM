/**
 * Dashboard landing page (placeholder).
 *
 * Главная страница-заглушка. Будет заменена полноценным дашбордом.
 */

import { Header } from "@/components/layout/Header";

export default function DashboardPage() {
  return (
    <>
      <Header title="Dashboard" />
      <div className="p-4 md:p-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Active Tasks" value="24" />
          <StatCard label="Open Deals" value="12" />
          <StatCard label="Pending Tenders" value="5" />
          <StatCard label="Low Stock Items" value="3" accent="warning" />
        </div>
      </div>
    </>
  );
}

function StatCard({
  label,
  value,
  accent = "default",
}: {
  label: string;
  value: string;
  accent?: "default" | "warning";
}) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium text-surface-400 uppercase tracking-wider">
        {label}
      </p>
      <p
        className={
          accent === "warning"
            ? "mt-1 text-2xl font-bold text-amber-600"
            : "mt-1 text-2xl font-bold text-surface-900"
        }
      >
        {value}
      </p>
    </div>
  );
}

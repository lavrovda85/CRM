import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { MobileNav } from "@/components/layout/MobileNav";
import { Header } from "@/components/layout/Header";
import { AuthProvider } from "@/components/auth/AuthProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "SPEC CRM — Управление сервисной компанией",
  description: "CRM/ERP платформа для управления сервисной компанией",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#4f46e5",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body className="min-h-screen overflow-x-hidden bg-surface-50 font-sans">
        <div className="flex h-screen max-w-full overflow-x-hidden">
          <Suspense
            fallback={
              <aside
                className="hidden h-screen w-60 shrink-0 bg-surface-900 md:flex"
                aria-hidden
              />
            }
          >
            <Sidebar />
          </Suspense>
          <main className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto pb-16 md:pb-0">
            <AuthProvider>
              <Header />
              {children}
            </AuthProvider>
          </main>
        </div>
        <MobileNav />
      </body>
    </html>
  );
}

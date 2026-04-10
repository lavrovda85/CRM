import type { Metadata, Viewport } from "next";
import Script from "next/script";
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

/** Runs before deferred Next.js chunks; pins API host:port to the real tab URL (not `<base href>`). */
const CRM_API_BASE_BOOTSTRAP =
  "try{var b=location.protocol+'//'+location.host+'/api/v1';document.documentElement.setAttribute('data-crm-api',b);window.__CRM_API_BASE__=b;}catch(e){}";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body className="min-h-screen overflow-x-hidden bg-surface-50 font-sans">
        <Script id="crm-api-base" strategy="beforeInteractive">
          {CRM_API_BASE_BOOTSTRAP}
        </Script>
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

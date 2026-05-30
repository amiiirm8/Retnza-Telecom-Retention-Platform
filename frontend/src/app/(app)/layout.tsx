"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { getToken } from "@/lib/api";
import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useI18n } from "@/i18n/provider";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { dir } = useI18n();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
    } else {
      setChecking(false);
    }
  }, [pathname, router]);

  if (checking) return <PageLoading />;

  return (
    <div className="flex min-h-screen bg-slate-50" dir={dir}>
      <Sidebar />
      <main className="flex-1 overflow-auto p-6">
        <ErrorBoundary section="Application">
          {children}
        </ErrorBoundary>
      </main>
    </div>
  );
}

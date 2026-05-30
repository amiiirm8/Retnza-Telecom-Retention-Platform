"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ListOrdered,
  Users,
  BarChart3,
  Activity,
  Shield,
  LogOut,
  Megaphone,
  FileSearch,
  PieChart,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { clearToken } from "@/lib/api";
import { useI18n } from "@/i18n/provider";
import { LanguageSwitcher } from "@/components/locale/language-switcher";

const iconSize = 18;

const links = [
  { href: "/dashboard", icon: LayoutDashboard, key: "sidebar.executive" },
  { href: "/queue", icon: ListOrdered, key: "sidebar.actionQueue" },
  { href: "/subscribers", icon: Users, key: "sidebar.subscribers" },
  { href: "/ecosystem", icon: BarChart3, key: "sidebar.ecosystem" },
  { href: "/behavioral-segments", icon: PieChart, key: "sidebar.behavioralSegments" },
  { href: "/evidence", icon: FileSearch, key: "sidebar.evidence" },
  { href: "/campaigns", icon: Megaphone, key: "sidebar.campaigns" },
  { href: "/health", icon: Activity, key: "sidebar.modelHealth" },
  { href: "/model", icon: Shield, key: "sidebar.governance" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { t, dir } = useI18n();

  function handleLogout() {
    clearToken();
    router.push("/login");
  }

  return (
    <aside className="flex w-56 flex-col border-r border-slate-800 bg-sidebar text-sidebar-foreground" dir={dir}>
      <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
        <div>
          <p className="text-lg font-bold tracking-tight">{t("app.name")}</p>
          <p className="text-xs text-slate-400">{t("app.tagline")}</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {links.map(({ href, icon: Icon, key }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
              pathname === href || (href !== "/" && pathname.startsWith(href))
                ? "bg-indigo-600 text-white"
                : "text-slate-300 hover:bg-slate-800"
            )}
          >
            <Icon size={iconSize} className="shrink-0" />
            <span>{t(key)}</span>
          </Link>
        ))}
      </nav>
      <div className="border-t border-slate-800 p-3 space-y-1">
        <LanguageSwitcher />
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
        >
          <LogOut size={iconSize} className="shrink-0" />
          {t("sidebar.signOut")}
        </button>
      </div>
    </aside>
  );
}

"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

interface DetailItem {
  label: string;
  value: string | number | null | undefined;
  mono?: boolean;
}

interface TechnicalDrawerProps {
  title?: string;
  items: DetailItem[];
  defaultOpen?: boolean;
  className?: string;
}

export function TechnicalDrawer({
  title = "Technical Details",
  items,
  defaultOpen = false,
  className,
}: TechnicalDrawerProps) {
  const [open, setOpen] = useState(defaultOpen);

  if (items.length === 0) return null;

  return (
    <div className={cn("rounded-lg border bg-slate-50", className)}>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100"
      >
        <span>{title}</span>
        <span className="text-xs text-slate-400">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 border-t border-slate-200 px-4 py-3 text-xs">
          {items.map((item, i) => (
            <div key={i} className="contents">
              <span className="text-slate-400">{item.label}</span>
              <span
                className={cn(
                  "text-slate-700",
                  item.mono && "font-mono",
                )}
              >
                {item.value ?? "—"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

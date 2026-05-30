"use client";

import { useState } from "react";

interface JsonDrawerProps {
  data: unknown;
  label: string;
  defaultOpen?: boolean;
}

export function JsonDrawer({ data, label, defaultOpen = false }: JsonDrawerProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [copied, setCopied] = useState(false);

  const json = JSON.stringify(data, null, 2);

  function handleCopy() {
    navigator.clipboard.writeText(json).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm font-medium text-slate-600 hover:bg-slate-50"
      >
        <span>{label}</span>
        <span className="text-xs text-slate-400">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="border-t border-slate-200">
          <div className="flex items-center justify-end gap-2 border-b border-slate-100 px-4 py-1.5">
            <button
              onClick={handleCopy}
              className="text-xs text-indigo-600 hover:text-indigo-500"
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre className="max-h-80 overflow-auto p-4 text-xs leading-relaxed text-slate-700">
            <code>{json}</code>
          </pre>
        </div>
      )}
    </div>
  );
}

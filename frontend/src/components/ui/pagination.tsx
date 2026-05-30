import { cn } from "@/lib/utils";
import { formatNumber } from "@/lib/format";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  labelPrev?: string;
  labelNext?: string;
  labelTotal?: string;
  locale?: string;
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  labelPrev = "Prev",
  labelNext = "Next",
  labelTotal,
  locale,
}: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  const fmtTotal = formatNumber(total, locale || "en");
  const fallback = `${fmtTotal} total — page ${page} of ${totalPages}`;
  const totalLabel = labelTotal
    ? labelTotal.replace("{count}", fmtTotal).replace("{page}", String(page)).replace("{pages}", String(totalPages))
    : fallback;

  return (
    <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
      <span className="text-slate-500">{totalLabel}</span>
      <div className="flex items-center gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className={cn(
            "rounded-lg border px-3 py-1.5 text-sm transition-colors",
            page <= 1
              ? "cursor-not-allowed border-slate-200 text-slate-300"
              : "border-slate-300 text-slate-600 hover:bg-slate-50"
          )}
        >
          {labelPrev}
        </button>
        {getPageNumbers(page, totalPages).map((p, i) =>
          p === "..." ? (
            <span key={`ellipsis-${i}`} className="px-1 text-slate-400">
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p as number)}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-sm transition-colors",
                p === page
                  ? "border-indigo-600 bg-indigo-600 text-white"
                  : "border-slate-300 text-slate-600 hover:bg-slate-50"
              )}
            >
              {p}
            </button>
          )
        )}
        <button
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className={cn(
            "rounded-lg border px-3 py-1.5 text-sm transition-colors",
            page >= totalPages
              ? "cursor-not-allowed border-slate-200 text-slate-300"
              : "border-slate-300 text-slate-600 hover:bg-slate-50"
          )}
        >
          {labelNext}
        </button>
      </div>
    </div>
  );
}

function getPageNumbers(current: number, total: number): (number | "..." )[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | "...")[] = [1];
  if (current > 3) pages.push("...");
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  for (let i = start; i <= end; i++) pages.push(i);
  if (current < total - 2) pages.push("...");
  pages.push(total);
  return pages;
}

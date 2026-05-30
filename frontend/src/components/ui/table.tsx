import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface Column {
  key: string;
  header: string;
  render: (item: Record<string, unknown>) => ReactNode;
  className?: string;
  sortable?: boolean;
}

interface DataTableProps {
  columns: Column[];
  data: Record<string, unknown>[];
  keyField: string;
  onRowClick?: (item: Record<string, unknown>) => void;
  emptyMessage?: string;
  sortKey?: string;
  sortDir?: string;
  onSort?: (key: string) => void;
}

export function DataTable({
  columns,
  data,
  keyField,
  onRowClick,
  emptyMessage = "No data",
  sortKey,
  sortDir,
  onSort,
}: DataTableProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-xl border bg-white py-12 text-sm text-slate-400">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 font-medium",
                    col.sortable && "cursor-pointer select-none hover:text-slate-900",
                    col.className
                  )}
                  onClick={() => {
                    if (col.sortable && onSort) onSort(col.key);
                  }}
                >
                  <span className="flex items-center gap-1">
                    {col.header}
                    {col.sortable && sortKey === col.key && (
                      <span className="text-xs">{sortDir === "asc" ? "▲" : "▼"}</span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((item) => (
              <tr
                key={String(item[keyField])}
                className={cn(
                  "border-t transition-colors",
                  onRowClick && "cursor-pointer hover:bg-slate-50"
                )}
                onClick={() => onRowClick?.(item)}
              >
                {columns.map((col) => (
                  <td key={col.key} className={cn("px-4 py-2.5", col.className)}>
                    {col.render(item)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

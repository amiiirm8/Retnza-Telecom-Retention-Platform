import { Card, CardTitle, CardValue } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function KpiCard({ title, value, subtitle, trend, className }: KpiCardProps) {
  return (
    <Card className={cn("relative overflow-hidden", className)}>
      {trend && (
        <span
          className={cn(
            "absolute right-3 top-3 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
            trend === "up" && "bg-red-50 text-red-600",
            trend === "down" && "bg-emerald-50 text-emerald-600",
            trend === "neutral" && "bg-slate-50 text-slate-500"
          )}
        >
          {trend === "up" && "↑"} {trend === "down" && "↓"} {trend === "neutral" && "→"}
        </span>
      )}
      <CardTitle>{title}</CardTitle>
      <CardValue>{value}</CardValue>
      {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
    </Card>
  );
}

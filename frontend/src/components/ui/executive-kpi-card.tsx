import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ExecutiveKpiCardProps {
  title: string;
  value: string;
  interpretation?: string;
  trend?: { direction: "up" | "down" | "neutral"; label: string };
  className?: string;
  accentColor?: "indigo" | "emerald" | "amber" | "red" | "blue" | "slate";
}

const accentBorders: Record<string, string> = {
  indigo: "border-l-indigo-500",
  emerald: "border-l-emerald-500",
  amber: "border-l-amber-500",
  red: "border-l-red-500",
  blue: "border-l-blue-500",
  slate: "border-l-slate-400",
};

export function ExecutiveKpiCard({
  title,
  value,
  interpretation,
  trend,
  className,
  accentColor = "indigo",
}: ExecutiveKpiCardProps) {
  return (
    <Card className={cn("border-l-4", accentBorders[accentColor], className)}>
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
        {title}
      </p>
      <p className="mt-1 text-3xl font-bold text-slate-900">{value}</p>
      {interpretation && (
        <p className="mt-1 text-sm text-slate-500 leading-snug">{interpretation}</p>
      )}
      {trend && (
        <p
          className={cn(
            "mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
            trend.direction === "up" && "bg-red-50 text-red-600",
            trend.direction === "down" && "bg-emerald-50 text-emerald-600",
            trend.direction === "neutral" && "bg-slate-50 text-slate-500"
          )}
        >
          {trend.direction === "up" && "↑"}
          {trend.direction === "down" && "↓"}
          {trend.direction === "neutral" && "→"}
          {trend.label}
        </p>
      )}
    </Card>
  );
}

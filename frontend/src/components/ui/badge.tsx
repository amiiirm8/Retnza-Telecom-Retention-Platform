import { cn } from "@/lib/utils";
import { getExecutiveRiskTier, RISK_TIER_EXEC_COLORS } from "@/lib/risk-labels";
import { getCompatibilityLabel } from "@/lib/governance-labels";

interface BadgeProps {
  variant?: "default" | "success" | "warning" | "danger" | "info" | "outline";
  children: React.ReactNode;
  className?: string;
}

const variants: Record<string, string> = {
  default: "bg-slate-100 text-slate-700",
  success: "bg-emerald-100 text-emerald-700",
  warning: "bg-amber-100 text-amber-700",
  danger: "bg-red-100 text-red-700",
  info: "bg-indigo-100 text-indigo-700",
  outline: "border border-slate-300 text-slate-600",
};

const priorityColors: Record<string, string> = {
  P1: "bg-red-100 text-red-700",
  P2: "bg-amber-100 text-amber-700",
  P3: "bg-blue-100 text-blue-700",
  P4: "bg-slate-100 text-slate-600",
};

export function Badge({ variant = "default", children, className }: BadgeProps) {
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", variants[variant], className)}>
      {children}
    </span>
  );
}

export function ExecutiveRiskBadge({ tier, showTechnical }: { tier: string | null; showTechnical?: boolean }) {
  if (!tier) return null;
  const execLabel = getExecutiveRiskTier(tier);
  const isMapped = execLabel !== tier;
  const colorClass = RISK_TIER_EXEC_COLORS[execLabel] || variants.default;

  return (
    <span className={cn("group relative inline-flex items-center gap-1.5", colorClass, "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium")}>
      {execLabel}
      {isMapped && showTechnical && (
        <span className="opacity-60">({tier})</span>
      )}
      {isMapped && (
        <div className="absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded border bg-white px-2 py-1 shadow-lg group-hover:block">
          <span className="text-xs text-slate-500">Risk tier (raw): {tier}</span>
        </div>
      )}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return null;
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", priorityColors[priority] || variants.default)}>
      {priority}
    </span>
  );
}

export function CompatBadge({ status }: { status: string | null }) {
  if (!status) return <Badge variant="outline">Unknown</Badge>;
  const label = getCompatibilityLabel(status);
  return <Badge variant={status === "compatible" ? "success" : "danger"}>{label}</Badge>;
}

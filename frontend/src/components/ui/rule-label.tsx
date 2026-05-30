import { getExecutiveRuleName, getRuleDescription } from "@/lib/rule-labels";
import { cn } from "@/lib/utils";

interface RuleLabelProps {
  ruleId: string | null;
  showTechnical?: boolean;
  className?: string;
}

export function RuleLabel({ ruleId, showTechnical = false, className }: RuleLabelProps) {
  if (!ruleId) {
    return <span className={cn("text-slate-400", className)}>—</span>;
  }

  const execName = getExecutiveRuleName(ruleId);
  const description = getRuleDescription(ruleId);
  const isTechnical = execName !== ruleId;

  return (
    <span className={cn("group relative inline-flex items-center gap-1.5", className)}>
      <span className="font-medium text-slate-800">{execName}</span>
      {(showTechnical || isTechnical) && (
        <span className="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
          {ruleId}
        </span>
      )}
      {description && (
        <div className="absolute bottom-full left-0 z-10 mb-1 hidden w-56 rounded-lg border bg-white p-2 shadow-lg group-hover:block">
          <p className="text-xs text-slate-600">{description}</p>
        </div>
      )}
    </span>
  );
}

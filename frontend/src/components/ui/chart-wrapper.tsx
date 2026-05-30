import { Card, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ChartWrapperProps {
  title: string;
  children: React.ReactNode;
  subtitle?: string;
  className?: string;
  height?: number;
}

export function ChartWrapper({ title, children, subtitle, className, height }: ChartWrapperProps) {
  return (
    <Card className={cn("flex flex-col", className)}>
      <div className="mb-3">
        <CardTitle>{title}</CardTitle>
        {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
      </div>
      <div className="flex-1" style={height ? { height } : undefined}>
        {children}
      </div>
    </Card>
  );
}

import { Card } from "@/components/ui/card";

interface SummaryBannerProps {
  title: string;
  items: {
    icon?: string;
    text: string;
    highlight?: boolean;
  }[];
}

export function SummaryBanner({ title, items }: SummaryBannerProps) {
  return (
    <Card className="border-indigo-200 bg-gradient-to-br from-indigo-50 to-white">
      <h2 className="text-base font-bold text-indigo-900">{title}</h2>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item, i) => (
          <div
            key={i}
            className={`flex items-start gap-2 rounded-lg p-2 text-sm ${
              item.highlight
                ? "bg-indigo-100 font-medium text-indigo-900"
                : "text-slate-600"
            }`}
          >
            {item.icon && <span className="mt-0.5 shrink-0">{item.icon}</span>}
            <span>{item.text}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

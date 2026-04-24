import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type MetricCardProps = {
  label: string;
  value: string | number;
  subtext?: string;
  tone?: "default" | "success" | "warning" | "destructive";
};

export function MetricCard({ label, value, subtext, tone = "default" }: MetricCardProps) {
  const toneClass =
    tone === "success"
      ? "text-success"
      : tone === "warning"
      ? "text-warning"
      : tone === "destructive"
      ? "text-destructive"
      : "text-foreground";
  return (
    <Card className="border-border bg-[hsl(var(--surface))]">
      <CardContent className="pt-6">
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className={cn("mt-2 text-2xl font-semibold tracking-tight", toneClass)}>
          {value}
        </div>
        {subtext && <div className="mt-1 text-xs text-muted-foreground">{subtext}</div>}
      </CardContent>
    </Card>
  );
}

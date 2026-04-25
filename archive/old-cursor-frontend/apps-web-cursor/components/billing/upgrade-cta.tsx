import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type UpgradeCtaProps = {
  title?: string;
  message: string;
  actionLabel?: string;
};

export function UpgradeCta({ title = "Upgrade required", message, actionLabel = "View plans" }: UpgradeCtaProps) {
  return (
    <Card className="border-border bg-[hsl(var(--surface))]">
      <CardContent className="flex flex-col gap-3 pt-6 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-sm font-semibold text-foreground">{title}</div>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
        <Button asChild variant="primary" size="sm">
          <Link href="/pricing">{actionLabel}</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

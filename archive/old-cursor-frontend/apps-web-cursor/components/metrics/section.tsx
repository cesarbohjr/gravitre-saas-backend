import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type SectionProps = {
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
};

export function MetricsSection({ title, children, actions }: SectionProps) {
  return (
    <Card className="border-border bg-[hsl(var(--surface))]">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">{title}</CardTitle>
        {actions}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

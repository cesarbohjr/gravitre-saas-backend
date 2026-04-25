"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getEnvironmentHeader } from "@/lib/environment";

export default function EnvironmentsPage() {
  const environment = getEnvironmentHeader();
  return (
    <Card className="border-border bg-[hsl(var(--surface))]">
      <CardHeader>
        <CardTitle className="text-lg">Environments</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Environment: <span className="font-medium text-foreground">{environment}</span>
        </p>
        <p className="text-sm text-muted-foreground">Coming soon.</p>
        <p className="text-sm text-muted-foreground">
          Environment management will be available soon. Use the environment
          selector in the top bar to switch context.
        </p>
        <p className="text-sm text-muted-foreground">
          Next step:{" "}
          <Link href="/workflows" className="text-primary hover:underline">
            manage workflows
          </Link>
          .
        </p>
      </CardContent>
    </Card>
  );
}

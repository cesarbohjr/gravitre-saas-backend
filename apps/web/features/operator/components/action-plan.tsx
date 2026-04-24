import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ActionPlanStep } from "@/features/operator/types/operator";

type ActionPlanProps = {
  title: string;
  summary: string;
  steps: ActionPlanStep[];
};

export function ActionPlan({ title, summary, steps }: ActionPlanProps) {
  return (
    <Card className="border-border bg-[hsl(var(--surface))]">
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{summary}</p>
        <div className="space-y-3">
          {steps.map((step, index) => (
            <ActionPlanStep
              key={step.id}
              index={index + 1}
              title={step.title}
              description={step.description}
              stepType={step.step_type}
              explanation={step.explanation}
              dependencies={step.dependencies}
              linkedEntity={step.linked_entity ?? null}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

type ActionPlanStepProps = {
  index: number;
  title: string;
  description: string;
  stepType: string;
  explanation: ActionPlanStep["explanation"];
  dependencies: string[];
  linkedEntity?: ActionPlanStep["linked_entity"];
};

export function ActionPlanStep({
  index,
  title,
  description,
  stepType,
  explanation,
  dependencies,
  linkedEntity,
}: ActionPlanStepProps) {
  const approvalLabel = explanation.approval_required ? "Approval required" : "No approval";
  const adminLabel = explanation.admin_required ? "Admin required" : "Member allowed";
  const executionLabel = explanation.executable ? "Executable" : "Draft only";
  const confirmationLabel = explanation.confirmation_required ? "Confirmation required" : "No confirmation";
  const linkedHref = linkedEntity
    ? `/${linkedEntity.type}s/${linkedEntity.id}`
    : null;
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-muted" aria-hidden="true" />
            <p className="text-sm font-medium text-foreground">
              Step {index}: {title}
            </p>
          </div>
          <p className="text-sm text-muted-foreground">{description}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span className="rounded-full bg-muted px-2 py-0.5">{approvalLabel}</span>
            <span className="rounded-full bg-muted px-2 py-0.5">{adminLabel}</span>
            <span className="rounded-full bg-muted px-2 py-0.5">{executionLabel}</span>
            <span className="rounded-full bg-muted px-2 py-0.5">{confirmationLabel}</span>
          </div>
          {dependencies.length > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Depends on: {dependencies.join(", ")}
            </p>
          ) : null}
          {linkedHref ? (
            <Link href={linkedHref} className="mt-2 inline-block text-xs text-primary hover:underline">
              View {linkedEntity?.type} details
            </Link>
          ) : null}
        </div>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {stepType.replaceAll("_", " ")}
        </span>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type ActionProposalCardProps = {
  title: string;
  description: string;
  environment: string;
  requiresApproval: boolean;
  requiresAdmin: boolean;
  executionState: "draft" | "executable";
  confirmationRequired: boolean;
  ctaLabel: string;
  onConfirm?: () => void;
  isExecuting?: boolean;
};

export function ActionProposalCard({
  title,
  description,
  environment,
  requiresApproval,
  requiresAdmin,
  executionState,
  confirmationRequired,
  ctaLabel,
  onConfirm,
  isExecuting = false,
}: ActionProposalCardProps) {
  const [isConfirming, setIsConfirming] = useState(false);
  const approvalLabel = requiresApproval ? "Approval required" : "No approval required";
  const adminLabel = requiresAdmin ? "Admin required" : "Member allowed";
  const executionLabel = executionState === "draft" ? "Draft only" : "Executable";
  const confirmationLabel = confirmationRequired ? "Confirmation required" : "No confirmation";
  const requiresConfirmation = confirmationRequired || executionState === "executable";
  const canExecute = executionState === "executable" && Boolean(onConfirm);

  return (
    <Card className="border-border bg-background">
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">{title}</p>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            Env: {environment}
          </span>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          <span className="rounded-full bg-muted px-2 py-0.5">{approvalLabel}</span>
          <span className="rounded-full bg-muted px-2 py-0.5">{adminLabel}</span>
          <span className="rounded-full bg-muted px-2 py-0.5">{executionLabel}</span>
          <span className="rounded-full bg-muted px-2 py-0.5">{confirmationLabel}</span>
        </div>
        <div>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setIsConfirming((prev) => !prev)}
            title="Review required before execution"
          >
            {ctaLabel}
          </Button>
        </div>
        {requiresConfirmation && isConfirming ? (
          <div className="rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground space-y-2">
            <p>Confirmation required before any execution.</p>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={onConfirm}
                disabled={!canExecute || isExecuting}
                title={!canExecute ? "Execution disabled" : undefined}
              >
                {isExecuting ? "Executing…" : "Confirm"}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setIsConfirming(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

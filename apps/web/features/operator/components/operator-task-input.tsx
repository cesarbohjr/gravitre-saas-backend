"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

type OperatorTaskInputProps = {
  onSubmit: (prompt: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
  contextLabel?: string;
  defaultPrompt?: string;
};

export function OperatorTaskInput({
  onSubmit,
  isLoading = false,
  disabled = false,
  contextLabel,
  defaultPrompt = "",
}: OperatorTaskInputProps) {
  const [prompt, setPrompt] = useState(defaultPrompt);

  useEffect(() => {
    setPrompt(defaultPrompt);
  }, [defaultPrompt]);

  const handleSubmit = () => {
    if (disabled || !prompt.trim()) return;
    onSubmit(prompt.trim());
  };

  return (
    <div className="rounded-md border border-border bg-background p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Operator task
          </p>
          {contextLabel ? (
            <p className="text-xs text-muted-foreground mt-1">{contextLabel}</p>
          ) : null}
        </div>
        <Button size="sm" variant="primary" onClick={handleSubmit} disabled={disabled || isLoading}>
          {isLoading ? "Generating…" : "Generate plan"}
        </Button>
      </div>
      <textarea
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        rows={3}
        placeholder="Describe the operator task or investigation goal."
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        disabled={disabled || isLoading}
      />
      <p className="text-xs text-muted-foreground">
        All actions remain in draft until reviewed and confirmed.
      </p>
    </div>
  );
}

"use client"

import { Suspense, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { useSearchParams, useRouter } from "next/navigation"
import useSWR from "swr"
import { Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card } from "@/components/ui/card"
import { Icon } from "@/lib/icons"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { LitePageShell } from "@/components/gravitre/lite-page-shell"

function LiteAssignContent() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const params = useSearchParams()
  const [workflowId, setWorkflowId] = useState(params.get("workflowId") || "")
  const [notes, setNotes] = useState(params.get("task") || "")
  const [inputsRaw, setInputsRaw] = useState("{}")
  const [submitting, setSubmitting] = useState(false)

  const { data, isLoading } = useSWR(
    user ? ["lite-workflows", user.id] : null,
    () => liteApi.getAvailableWorkflows(),
    { revalidateOnFocus: false },
  )

  const selectedWorkflow = useMemo(
    () => data?.workflows.find((w) => w.id === workflowId),
    [data?.workflows, workflowId],
  )

  const handleSubmit = async () => {
    if (!workflowId) {
      toast.error("Select a workflow")
      return
    }
    let inputs: Record<string, unknown> = {}
    try {
      inputs = inputsRaw.trim() ? JSON.parse(inputsRaw) : {}
    } catch {
      toast.error("Inputs must be valid JSON")
      return
    }
    setSubmitting(true)
    try {
      await liteApi.assignWork(workflowId, inputs, notes || undefined)
      toast.success("Task assigned")
      router.push("/lite/tasks")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to assign task")
    } finally {
      setSubmitting(false)
    }
  }

  if (!loading && !isLoading && !user) {
    return (
      <LitePageShell title="Assign Work" description="Sign in to continue." icon={Send}>
        <p className="text-sm text-muted-foreground">Sign in required.</p>
      </LitePageShell>
    )
  }

  return (
    <LitePageShell
      title="Assign Work"
      description="Pick a workflow and send work to your AI team."
      icon={Send}
      loading={loading || isLoading}
      loadingLabel="Loading workflows"
    >
      <Card className="space-y-4 p-4">
        <div>
          <p className="mb-2 text-sm font-medium">Workflow</p>
          <div className="grid gap-2">
            {(data?.workflows ?? []).map((workflow, index) => (
              <motion.button
                key={workflow.id}
                type="button"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index, 8) * 0.04, type: "spring", stiffness: 380, damping: 30 }}
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.99 }}
                className={cn(
                  "relative rounded-lg border p-3 text-left transition-colors",
                  workflowId === workflow.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/40",
                )}
                onClick={() => setWorkflowId(workflow.id)}
              >
                {workflowId === workflow.id && (
                  <motion.span
                    layoutId="lite-assign-selected"
                    className="pointer-events-none absolute inset-0 rounded-lg ring-2 ring-primary/50"
                    transition={{ type: "spring", stiffness: 500, damping: 38 }}
                  />
                )}
                <p className="font-medium">{workflow.name}</p>
                <p className="text-xs text-muted-foreground">
                  {workflow.description || "No description"}
                </p>
              </motion.button>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium">Task Notes</p>
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        <div>
          <p className="mb-2 text-sm font-medium">Inputs (JSON)</p>
          <Input value={inputsRaw} onChange={(e) => setInputsRaw(e.target.value)} />
          {selectedWorkflow?.required_inputs?.length ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Required inputs: {selectedWorkflow.required_inputs.join(", ")}
            </p>
          ) : null}
        </div>

        <Button onClick={handleSubmit} disabled={submitting} className="gap-2">
          {submitting ? (
            <Icon name="spinner" size="sm" className="animate-spin" />
          ) : (
            <Icon name="play" size="sm" />
          )}
          {submitting ? "Assigning..." : "Assign Task"}
        </Button>
      </Card>
    </LitePageShell>
  )
}

export default function LiteAssignPage() {
  return (
    <Suspense
      fallback={
        <LitePageShell title="Assign Work" icon={Send} loading loadingLabel="Loading">
          <span className="sr-only">Loading</span>
        </LitePageShell>
      }
    >
      <LiteAssignContent />
    </Suspense>
  )
}

"use client"

import { Suspense, useMemo, useState } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card } from "@/components/ui/card"
import { Icon } from "@/lib/icons"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"

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
    { revalidateOnFocus: false }
  )

  const selectedWorkflow = useMemo(
    () => data?.workflows.find((w) => w.id === workflowId),
    [data?.workflows, workflowId]
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

  if (loading || isLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Loading workflows...</div>
  }
  if (!user) {
    return <div className="p-8 text-sm text-muted-foreground">Sign in required.</div>
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto space-y-4">
        <h1 className="text-2xl font-bold">Assign Work</h1>
        <Card className="p-4 space-y-4">
          <div>
            <p className="text-sm font-medium mb-2">Workflow</p>
            <div className="grid gap-2">
              {(data?.workflows ?? []).map((workflow) => (
                <button
                  key={workflow.id}
                  className={`text-left border rounded-lg p-3 ${workflowId === workflow.id ? "border-emerald-500 bg-emerald-500/5" : "border-border"}`}
                  onClick={() => setWorkflowId(workflow.id)}
                >
                  <p className="font-medium">{workflow.name}</p>
                  <p className="text-xs text-muted-foreground">{workflow.description || "No description"}</p>
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-sm font-medium mb-2">Task Notes</p>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>

          <div>
            <p className="text-sm font-medium mb-2">Inputs (JSON)</p>
            <Input value={inputsRaw} onChange={(e) => setInputsRaw(e.target.value)} />
            {selectedWorkflow?.required_inputs?.length ? (
              <p className="text-xs text-muted-foreground mt-2">
                Required inputs: {selectedWorkflow.required_inputs.join(", ")}
              </p>
            ) : null}
          </div>

          <Button onClick={handleSubmit} disabled={submitting} className="gap-2">
            {submitting ? <Icon name="spinner" size="sm" className="animate-spin" /> : <Icon name="play" size="sm" />}
            {submitting ? "Assigning..." : "Assign Task"}
          </Button>
        </Card>
      </div>
    </div>
  )
}

export default function LiteAssignPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">Loading...</div>}>
      <LiteAssignContent />
    </Suspense>
  )
}

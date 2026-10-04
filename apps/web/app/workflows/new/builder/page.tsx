"use client"

import { useRef, useState, type FormEvent } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { workflowsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { isPersistableWorkflowId } from "@/lib/workflows/builder-persistence"
import { TYPE } from "@/lib/design-system"

export default function NewWorkflowPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()
  const lock = useRef(false)
  const createdId = useRef<string | null>(null)
  const [name, setName] = useState("")
  const [goal, setGoal] = useState("")
  const [description, setDescription] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedId, setSavedId] = useState<string | null>(null)
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : ""

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (lock.current || !user || !name.trim()) return
    lock.current = true
    setBusy(true)
    setError(null)
    try {
      if (!createdId.current) {
        const workflow = await workflowsApi.create({
          name: name.trim(),
          goal: goal.trim() || undefined,
          description: description.trim() || undefined,
        })
        if (!workflow.id || !isPersistableWorkflowId(workflow.id)) {
          throw new Error(
            "The API returned no usable workflow ID. Check Workflows before creating another.",
          )
        }
        createdId.current = workflow.id
        setSavedId(workflow.id)
      }
      router.replace(`/workflows/${createdId.current}/builder${suffix}`)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not create the workflow. Your draft is retained.",
      )
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  return (
    <AppShell title="New workflow">
      <div
        className="mx-auto max-w-4xl pb-24 [&_[data-slot=button]]:min-h-11"
        data-composition="create"
      >
        <GravitrePageHeader
          eyebrow="Workflows / Create"
          title="Give the work a direction"
          description="Define the outcome, then connect the steps in the builder."
          actions={
            <Button variant="ghost" asChild>
              <Link href="/workflows">Back to workflows</Link>
            </Button>
          }
        />
        <div className="grid gap-8 px-[var(--np-page-pad-sm)] pt-6 sm:px-[var(--np-page-pad)] lg:grid-cols-[minmax(0,1fr)_240px]">
          <form onSubmit={(event) => void create(event)} className="space-y-6">
            <fieldset
              disabled={busy || !user || Boolean(savedId)}
              className="space-y-5 disabled:opacity-70"
            >
              <div className="space-y-2">
                <Label htmlFor="workflow-name">Workflow name</Label>
                <Input
                  id="workflow-name"
                  required
                  maxLength={200}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Invoice follow-up"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="workflow-goal">
                  Desired outcome <span className="text-muted-foreground">(optional)</span>
                </Label>
                <Textarea
                  id="workflow-goal"
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  placeholder="What should be true when this workflow finishes?"
                  className="min-h-28"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="workflow-description">
                  Context <span className="text-muted-foreground">(optional)</span>
                </Label>
                <Textarea
                  id="workflow-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Who is this for, and what should the builder account for?"
                />
              </div>
            </fieldset>
            {!user ? (
              <p role="status" className="text-sm text-muted-foreground">
                Sign in to create a workflow.
              </p>
            ) : null}
            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
            {savedId ? (
              <p role="status" className="text-sm text-muted-foreground">
                Workflow created. Continue to its builder to configure and save steps.
              </p>
            ) : null}
            <Button type="submit" disabled={busy || !user || !name.trim()}>
              {busy
                ? "Creating workflow…"
                : savedId
                  ? "Open saved builder"
                  : "Create & open builder"}
            </Button>
          </form>
          <aside className="space-y-3 border-t border-[color:var(--g-border-subtle)] pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
            <p className={TYPE.eyebrow}>Next in the builder</p>
            <ol className="space-y-3 text-sm text-muted-foreground">
              <li>Choose sources and agents.</li>
              <li>Connect steps and approval gates.</li>
              <li>Save and review a dry run.</li>
            </ol>
            <p className="border-t border-[color:var(--g-border-subtle)] pt-3 text-sm text-muted-foreground">
              Creating this workflow does not execute it or set a schedule.
            </p>
          </aside>
        </div>
      </div>
    </AppShell>
  )
}

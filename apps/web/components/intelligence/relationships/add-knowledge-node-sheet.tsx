"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  KNOWLEDGE_NODE_TYPE_LABELS,
  RELATIONSHIPS_GUIDE,
  RELATIONSHIPS_ONBOARDING,
  knowledgeNodeTypeLabel,
} from "@/lib/learning-ui-copy"
import { Building, Cube, Storefront, User, UsersThree } from "@phosphor-icons/react"
import type { RelationshipsWorkspaceState } from "./use-relationships-workspace"

const FIRST_ENTITY_TYPES = ["company", "customer", "employee", "product", "vendor"] as const

const TYPE_ICONS: Record<string, typeof Building> = {
  company: Building,
  customer: UsersThree,
  employee: User,
  product: Cube,
  vendor: Storefront,
}

export function AddKnowledgeNodeSheet({
  workspace,
}: {
  workspace: RelationshipsWorkspaceState
}) {
  const { addNodeOpen, setAddNodeOpen, addNodeMode, nodeTypes, createNode } = workspace
  const [nodeName, setNodeName] = useState("")
  const [nodeType, setNodeType] = useState("company")
  const [busy, setBusy] = useState(false)
  const isFirst = addNodeMode === "first"

  async function handleSubmit() {
    setBusy(true)
    const ok = await createNode(nodeType, nodeName)
    setBusy(false)
    if (ok) {
      setNodeName("")
      setAddNodeOpen(false)
    }
  }

  return (
    <Sheet open={addNodeOpen} onOpenChange={setAddNodeOpen}>
      <SheetContent className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle>
            {isFirst ? RELATIONSHIPS_ONBOARDING.sheetTitle : "Add organization entity"}
          </SheetTitle>
          <SheetDescription>
            {isFirst ? RELATIONSHIPS_ONBOARDING.sheetLead : RELATIONSHIPS_GUIDE.nodesBody}
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-4 px-4 py-2">
          {isFirst ? (
            <div className="space-y-2">
              <span className="text-xs font-medium text-[color:var(--g-text-muted)]">Entity type</span>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {FIRST_ENTITY_TYPES.map((t) => {
                  const Icon = TYPE_ICONS[t] ?? Building
                  const selected = nodeType === t
                  return (
                    <button
                      key={t}
                      type="button"
                      className={`flex flex-col items-center gap-1.5 rounded-[var(--np-radius-md)] border px-2 py-3 text-center transition-colors ${
                        selected
                          ? "border-[color:var(--g-brand)]/50 bg-[color:var(--g-brand-soft)]/40"
                          : "border-divide bg-[color:var(--g-surface-1)] hover:bg-[color:var(--g-surface-2)]"
                      }`}
                      onClick={() => setNodeType(t)}
                    >
                      <Icon className="h-5 w-5 text-[color:var(--g-brand)]" aria-hidden />
                      <span className="text-xs font-medium">{KNOWLEDGE_NODE_TYPE_LABELS[t] ?? t}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-1.5">
              <span className="text-xs font-medium text-[color:var(--g-text-muted)]">Type</span>
              <div className="flex flex-wrap gap-2">
                {nodeTypes.map((t) => (
                  <Button
                    key={t}
                    type="button"
                    size="sm"
                    variant={nodeType === t ? "default" : "outline"}
                    onClick={() => setNodeType(t)}
                  >
                    {knowledgeNodeTypeLabel(t)}
                  </Button>
                ))}
              </div>
            </div>
          )}
          <div className="space-y-1.5">
            <label htmlFor="kn-name-drawer" className="text-xs font-medium text-[color:var(--g-text-muted)]">
              Name
            </label>
            <Input
              id="kn-name-drawer"
              value={nodeName}
              onChange={(e) => setNodeName(e.target.value)}
              placeholder="e.g. Acme Corp"
            />
          </div>
          {!isFirst ? (
            <p className="text-xs leading-relaxed text-[color:var(--g-text-muted)]">{RELATIONSHIPS_GUIDE.nodesHint}</p>
          ) : null}
        </div>
        <SheetFooter>
          <Button type="button" variant="outline" onClick={() => setAddNodeOpen(false)}>
            Cancel
          </Button>
          <Button type="button" disabled={busy} onClick={() => void handleSubmit()}>
            {isFirst ? "Add organization entity" : "Add entity"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { RELATIONSHIPS_GUIDE } from "@/lib/learning-ui-copy"
import type { RelationshipsWorkspaceState } from "./use-relationships-workspace"

export function AddKnowledgeNodeSheet({
  workspace,
}: {
  workspace: RelationshipsWorkspaceState
}) {
  const { addNodeOpen, setAddNodeOpen, nodeTypes, createNode } = workspace
  const [nodeName, setNodeName] = useState("")
  const [nodeType, setNodeType] = useState("company")
  const [busy, setBusy] = useState(false)

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
          <SheetTitle>Add organization knowledge</SheetTitle>
          <SheetDescription>{RELATIONSHIPS_GUIDE.nodesBody}</SheetDescription>
        </SheetHeader>
        <div className="space-y-4 px-4 py-2">
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
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-[color:var(--g-text-muted)]">Type</span>
            <Select value={nodeType} onValueChange={setNodeType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {nodeTypes.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <p className="text-xs leading-relaxed text-[color:var(--g-text-muted)]">{RELATIONSHIPS_GUIDE.nodesHint}</p>
        </div>
        <SheetFooter>
          <Button type="button" variant="outline" onClick={() => setAddNodeOpen(false)}>
            Cancel
          </Button>
          <Button type="button" disabled={busy} onClick={() => void handleSubmit()}>
            Add node
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

"use client"

/**
 * Branch routing editor for IF / Switch / Decision nodes: what each path tests,
 * and which connected step it goes to. Unrouted connections never run.
 */
import { useId, useMemo, useState } from "react"
import { AlertTriangle, Plus, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { CanvasWorkflowNode, DecisionPath } from "@/lib/workflows/builder-persistence"
import {
  CONDITION_OPERATORS,
  appendConditionClause,
  stepReferenceSlug,
  unroutedConnections,
} from "@/lib/workflows/branch-wiring"

type BranchNode = CanvasWorkflowNode

function upstreamNodes(node: BranchNode, allNodes: BranchNode[]): BranchNode[] {
  const byTarget = new Map<string, BranchNode[]>()
  for (const n of allNodes) {
    for (const target of n.connections) {
      byTarget.set(target, [...(byTarget.get(target) ?? []), n])
    }
  }
  const seen = new Set<string>()
  const queue = [...(byTarget.get(node.id) ?? [])]
  const out: BranchNode[] = []
  while (queue.length) {
    const current = queue.shift()!
    if (seen.has(current.id)) continue
    seen.add(current.id)
    out.push(current)
    queue.push(...(byTarget.get(current.id) ?? []))
  }
  return out
}

/** Inline "field / operator / value" row that appends a clause to a condition string. */
export function ConditionBuilder({
  value,
  onChange,
  fieldSuggestions,
  placeholder,
  ariaLabel,
}: {
  value: string
  onChange: (next: string) => void
  fieldSuggestions: string[]
  placeholder?: string
  ariaLabel: string
}) {
  const listId = useId()
  const [field, setField] = useState("")
  const [operator, setOperator] = useState<string>("==")
  const [clauseValue, setClauseValue] = useState("")
  const [join, setJoin] = useState<"and" | "or">("and")
  const hasExisting = value.trim().length > 0

  return (
    <div className="space-y-1.5">
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "e.g. steps.lead_scorer.score > 80 and $region == 'EMEA'"}
        className="h-8 text-xs bg-secondary border-border font-mono"
        aria-label={ariaLabel}
      />
      <div className="flex flex-wrap items-center gap-1.5">
        {hasExisting ? (
          <select
            value={join}
            onChange={(e) => setJoin(e.target.value as "and" | "or")}
            className="h-7 rounded border border-border bg-secondary px-1 text-[11px]"
            aria-label="Combine with"
          >
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        ) : null}
        <input
          list={listId}
          value={field}
          onChange={(e) => setField(e.target.value)}
          placeholder="Field"
          className="h-7 min-w-0 flex-1 rounded border border-border bg-secondary px-2 text-[11px] font-mono"
          aria-label="Field"
        />
        <datalist id={listId}>
          {fieldSuggestions.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
        <select
          value={operator}
          onChange={(e) => setOperator(e.target.value)}
          className="h-7 rounded border border-border bg-secondary px-1 text-[11px]"
          aria-label="Operator"
        >
          {CONDITION_OPERATORS.map((op) => (
            <option key={op.value} value={op.value}>
              {op.label}
            </option>
          ))}
        </select>
        <input
          value={clauseValue}
          onChange={(e) => setClauseValue(e.target.value)}
          placeholder="Value"
          className="h-7 w-24 rounded border border-border bg-secondary px-2 text-[11px]"
          aria-label="Value"
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 px-2 text-[11px]"
          disabled={!field.trim()}
          onClick={() => {
            onChange(appendConditionClause(value, { field, operator, value: clauseValue }, join))
            setField("")
            setClauseValue("")
          }}
        >
          Add
        </Button>
      </div>
    </div>
  )
}

function useFieldSuggestions(node: BranchNode, allNodes: BranchNode[]): string[] {
  return useMemo(() => {
    const refs = upstreamNodes(node, allNodes)
      .filter((n) => n.type !== "source")
      .map((n) => `steps.${stepReferenceSlug(n.name)}.`)
    return ["input.", ...refs, "$"]
  }, [node, allNodes])
}

function TargetSelect({
  node,
  path,
  allNodes,
  onChange,
}: {
  node: BranchNode
  path: DecisionPath
  allNodes: BranchNode[]
  onChange: (targetNodeId: string | undefined) => void
}) {
  const names = new Map(allNodes.map((n) => [n.id, n.name]))
  return (
    <select
      value={path.targetNodeId ?? ""}
      onChange={(e) => onChange(e.target.value || undefined)}
      className="h-7 max-w-[9rem] rounded border border-border bg-secondary px-1 text-[11px]"
      aria-label={`Where ${path.label} goes`}
    >
      <option value="">{node.connections.length ? "Goes to…" : "Connect a step first"}</option>
      {node.connections.map((id) => (
        <option key={id} value={id}>
          {names.get(id) ?? "Step"}
        </option>
      ))}
    </select>
  )
}

function UnroutedWarning({ node, allNodes }: { node: BranchNode; allNodes: BranchNode[] }) {
  const unrouted = unroutedConnections(node)
  if (!unrouted.length) return null
  const names = new Map(allNodes.map((n) => [n.id, n.name]))
  return (
    <p className="flex items-start gap-1.5 text-[11px] text-warning">
      <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
      {unrouted.map((id) => names.get(id) ?? "A step").join(", ")}{" "}
      {unrouted.length === 1 ? "isn't" : "aren't"} on any branch, so {unrouted.length === 1 ? "it" : "they"} will never run.
      Add a branch or pick it under “Goes to”.
    </p>
  )
}

/** Goes-to selectors for Decision nodes, whose path editing lives in the decision panel. */
export function BranchTargetsEditor({
  node,
  allNodes,
  onUpdate,
}: {
  node: BranchNode
  allNodes: BranchNode[]
  onUpdate: (updates: Partial<BranchNode>) => void
}) {
  const paths = node.outputPaths ?? []
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">Where each branch goes</p>
      {paths.map((path) => (
        <div key={path.id} className="flex items-center justify-between gap-2">
          <span className="truncate text-xs text-foreground">{path.label}</span>
          <TargetSelect
            node={node}
            path={path}
            allNodes={allNodes}
            onChange={(targetNodeId) =>
              onUpdate({ outputPaths: paths.map((p) => (p.id === path.id ? { ...p, targetNodeId } : p)) })
            }
          />
        </div>
      ))}
      <UnroutedWarning node={node} allNodes={allNodes} />
    </div>
  )
}

/** Full editor for IF and Switch nodes. */
export function BranchRoutingPanel({
  node,
  allNodes,
  onUpdate,
}: {
  node: BranchNode
  allNodes: BranchNode[]
  onUpdate: (updates: Partial<BranchNode>) => void
}) {
  const suggestions = useFieldSuggestions(node, allNodes)
  const paths = node.outputPaths ?? []
  const setPaths = (next: DecisionPath[]) => onUpdate({ outputPaths: next })
  const updatePath = (id: string, patch: Partial<DecisionPath>) =>
    setPaths(paths.map((p) => (p.id === id ? { ...p, ...patch } : p)))
  const expression = String(node.config?.expression ?? "")

  return (
    <div className="space-y-4 pt-4 border-t border-[color:var(--g-signal)]/20">
      <div>
        <h4 className="text-sm font-medium text-foreground">
          {node.type === "if" ? "Condition" : "Cases"}
        </h4>
        <p className="text-[10px] text-muted-foreground">
          Reference earlier steps with <code>steps.&lt;step name&gt;.&lt;field&gt;</code>, the previous step with{" "}
          <code>input.&lt;field&gt;</code>, and run inputs with <code>$name</code>. Combine tests with AND / OR.
        </p>
      </div>

      {node.type === "if" ? (
        <>
          <ConditionBuilder
            value={expression}
            onChange={(next) =>
              onUpdate({
                config: { ...node.config, expression: next },
                decisionConfig: { ...node.decisionConfig, strategy: "rule-based", conditions: next },
              })
            }
            fieldSuggestions={suggestions}
            ariaLabel="IF condition"
          />
          <div className="space-y-2">
            {paths.map((path) => (
              <div key={path.id} className="flex items-center justify-between gap-2">
                <span className="text-xs text-foreground">
                  {path.isDefault ? "Otherwise (false)" : "When true"}
                </span>
                <TargetSelect node={node} path={path} allNodes={allNodes} onChange={(t) => updatePath(path.id, { targetNodeId: t })} />
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="space-y-3">
          {paths.map((path, idx) => (
            <div key={path.id} className="space-y-1.5 rounded-lg border border-border bg-secondary/30 p-2">
              <div className="flex items-center gap-2">
                <Input
                  value={path.label}
                  onChange={(e) => updatePath(path.id, { label: e.target.value })}
                  className="h-7 flex-1 text-xs bg-secondary border-border"
                  aria-label="Case name"
                />
                <TargetSelect node={node} path={path} allNodes={allNodes} onChange={(t) => updatePath(path.id, { targetNodeId: t })} />
                {!path.isDefault ? (
                  <button
                    type="button"
                    onClick={() => setPaths(paths.filter((p) => p.id !== path.id))}
                    className="p-1 text-muted-foreground hover:text-destructive"
                    aria-label={`Remove ${path.label}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                ) : null}
              </div>
              {path.isDefault ? (
                <p className="text-[10px] text-muted-foreground">Taken when no case above matches.</p>
              ) : (
                <ConditionBuilder
                  value={path.condition ?? ""}
                  onChange={(next) => updatePath(path.id, { condition: next })}
                  fieldSuggestions={suggestions}
                  ariaLabel={`Condition for case ${idx + 1}`}
                />
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={() => {
              const defaults = paths.filter((p) => p.isDefault)
              const cases = paths.filter((p) => !p.isDefault)
              const next: DecisionPath = { id: `case-${Date.now()}`, label: `Case ${cases.length + 1}`, condition: "" }
              setPaths([...cases, next, ...defaults])
            }}
            className={cn("flex items-center gap-1 text-[11px] text-[color:var(--g-signal)]")}
          >
            <Plus className="h-3 w-3" /> Add case
          </button>
          <p className="text-[10px] text-muted-foreground">Cases are checked top to bottom; the first match wins.</p>
        </div>
      )}
      <UnroutedWarning node={node} allNodes={allNodes} />
    </div>
  )
}

import { outcomePackComposition } from "@/lib/outcome-pack-composition"

export function OutcomePackComposition({ config }: { config: Record<string, unknown> | undefined }) {
  const composition = outcomePackComposition(config)
  if (!composition) return null
  return <section aria-label="Outcome Pack capabilities" className="gv-card td-section space-y-3">
    <h2>Pack capabilities</h2>
    <p className="text-sm text-muted-foreground">Declared contents. Connection, approval, and production evidence are checked separately before use.</p>
    <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
      {Object.entries({ Agents: composition.agents, Plays: composition.plays, "Knowledge sources": composition.knowledge, "Defined metrics": composition.metrics, Dashboards: composition.dashboards, "Skill packages": composition.skillPackages.length }).map(([label, count]) => <div key={label}><dt>{label}</dt><dd className="font-semibold tabular-nums">{count}</dd></div>)}
    </dl>
    {composition.actions.length ? <details><summary className="cursor-pointer py-2 text-sm">Declared app actions ({composition.actions.length})</summary><ul className="list-disc pl-5 text-sm">{composition.actions.map(action => <li key={action}>{action}</li>)}</ul></details> : null}
    {composition.approvalPlays.length ? <p className="text-sm">Approval required: {composition.approvalPlays.join(", ")}.</p> : null}
    <p className="text-xs text-muted-foreground">Defined metrics and estimated savings are not measured outcomes. Verified results appear only after independent source checks.</p>
  </section>
}

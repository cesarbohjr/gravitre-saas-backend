export function WorkflowFleetSummary({ successRate, weeklyRuns }: { successRate: number | null; weeklyRuns: number | null }) {
  return <section aria-label="Organization workflow summary" className="mt-5 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
    <p className="text-xs text-muted-foreground">Organization totals · all workflows, independent of list filters</p>
    <dl className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div><dt className="text-xs text-muted-foreground">Overall execution success</dt><dd className="mt-1 font-sans text-2xl font-medium tabular-nums text-foreground">{successRate == null ? "Not reported" : `${Math.round(successRate)}%`}</dd></div>
      <div><dt className="text-xs text-muted-foreground">Runs this week</dt><dd className="mt-1 font-sans text-2xl font-medium tabular-nums text-foreground">{weeklyRuns == null ? "Not reported" : weeklyRuns.toLocaleString()}</dd></div>
    </dl>
    <p className="mt-3 text-xs text-muted-foreground">Execution success does not establish a verified business outcome.</p>
  </section>
}

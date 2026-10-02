"use client"

import { useState } from "react"
import Link from "next/link"
import { motion, useReducedMotion } from "framer-motion"
import { Activity, ArrowRight, BookOpen, CircleDollarSign, Database, Headphones, HeartHandshake, Layers, Megaphone, ShieldCheck, Users } from "lucide-react"
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { certificateLabel, DEPARTMENT_DESIGNS, type DepartmentWorkspace as Workspace } from "@/lib/marketplace3"

const icons = { service: Headphones, security: ShieldCheck, revenue: Activity, success: HeartHandshake, finance: CircleDollarSign, marketing: Megaphone, people: Users, executive: Layers }
const readable = (text: string) => text.replace(/[_-]/g, " ")
const number = (value: number) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)

export function DepartmentWorkspace({ workspace, preview = false }: { workspace: Workspace; preview?: boolean }) {
  const { asset, contract, install, measurements, recentRuns, sources } = workspace
  const design = DEPARTMENT_DESIGNS[asset.slug] ?? DEPARTMENT_DESIGNS["executive-command-center-3"]
  const Icon = icons[design.icon]
  const reduced = useReducedMotion()
  const [query, setQuery] = useState("")
  const plays = contract.plays.filter(p => `${p.name} ${p.description}`.toLowerCase().includes(query.toLowerCase()))
  return (
    <motion.section initial={false} animate={{ opacity: 1, y: 0 }} transition={{ duration: .25 }} className="space-y-6" data-testid="department-workspace" data-department-pack={asset.slug}>
      <header className="relative overflow-hidden rounded-2xl border bg-card p-5 sm:p-7">
        <div className="pointer-events-none absolute right-0 top-0 h-56 w-56 rounded-full opacity-10 blur-3xl" style={{ background: design.accent }} aria-hidden />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-3">
            <div className="flex items-center gap-3"><span className="rounded-xl border p-3" style={{ color: design.accent }}><Icon className="h-6 w-6" aria-hidden /></span><p className="text-xs font-medium tracking-wide text-muted-foreground">{design.focus}</p></div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{asset.title}</h1>
            <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">{contract.outcome.target_outcome}</p>
            <div className="flex flex-wrap gap-2"><Badge variant="outline">Catalog: {certificateLabel(asset.certificationLevel)}</Badge><Badge variant="secondary">{preview ? "Blueprint preview" : install?.pilot ? "Observe pilot" : "Installed"}</Badge>{install ? <Badge variant="outline">Version {install.version}</Badge> : null}{contract.providers.map(p => <Badge key={p} variant="outline">{readable(p)}</Badge>)}</div>
          </div>
          <svg viewBox="0 0 150 100" className="hidden h-24 w-36 shrink-0 sm:block" role="img" aria-label={`${design.focus} operating loop`}>
            <path d="M25 50 L75 20 L125 50 L75 80 Z M25 50 H125 M75 20 V80" fill="none" stroke={design.accent} strokeWidth="1.5" opacity=".5" />
            {[[25,50],[75,20],[125,50],[75,80]].map(([x,y],i) => <circle key={i} cx={x} cy={y} r="7" fill={design.accent} opacity=".7" />)}
            <circle cx="75" cy="50" r="13" fill="var(--background)" stroke={design.accent} strokeWidth="2" />
            <path d="m69 50 4 4 8-8" stroke={design.accent} strokeWidth="2" fill="none" />
          </svg>
        </div>
      </header>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <GravitreMetric label="Plays" value={contract.plays.length} hint={preview ? "Included in this pack" : "Open a workflow to review inputs"} />
        <GravitreMetric label="Agents" value={preview ? contract.agents.length : install?.agentIds.length ?? "—"} hint={preview ? "Included roles" : "Installed roles"} />
        <GravitreMetric label="Measured results" value={preview ? "—" : measurements.length} hint={preview ? "Live evidence appears after installation" : "Verified results in the recent activity window"} />
        <GravitreMetric label="KPI coverage" value={preview ? "—" : `${new Set(measurements.map(m => m.metricKey)).size}/${contract.outcome.kpis.length}`} hint="KPIs with source-linked measurements" />
      </div>
      <Tabs defaultValue="overview" className="space-y-5">
        <TabsList className="h-auto w-full justify-start overflow-x-auto flex-wrap"><TabsTrigger value="overview">Overview</TabsTrigger><TabsTrigger value="plays">Plays</TabsTrigger><TabsTrigger value="evidence">Evidence</TabsTrigger><TabsTrigger value="data">Data & standards</TabsTrigger><TabsTrigger value="team">Agents & activity</TabsTrigger></TabsList>
        <TabsContent value="overview" className="space-y-5">
          <div className="rounded-xl border bg-muted/20 p-4"><h2 className="text-sm font-semibold">{preview ? "Dashboard blueprint" : "Department dashboard"}</h2><p className="mt-1 text-sm text-muted-foreground">{preview ? "KPI contracts and chart choices are shown below. This preview contains no live results." : "Charts use verified measurements from this install’s production workflows. Missing measurements remain unavailable."}</p></div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {contract.dashboard.metrics.map(metric => {
              const kpi = contract.outcome.kpis.find(k => k.key === metric.kpi_key)
              const points = measurements.filter(m => m.metricKey === metric.kpi_key).sort((a,b) => a.measuredAt.localeCompare(b.measuredAt))
              const latest = points.at(-1)
              const chart = points.map(m => ({ date: new Date(m.measuredAt).toLocaleDateString(), baseline: m.baselineValue, result: m.resultValue }))
              return <article key={metric.kpi_key} className="min-w-0 rounded-xl border bg-card p-4" data-kpi-key={metric.kpi_key}>
                <p className="text-sm font-medium">{metric.label}</p>{metric.description ? <p className="mt-1 text-xs text-muted-foreground">{metric.description}</p> : null}<div className="mt-2 flex items-baseline gap-2"><span className="text-2xl font-semibold tabular-nums">{latest ? number(latest.resultValue) : "—"}</span><span className="text-xs text-muted-foreground">{kpi?.unit}</span></div>
                {kpi?.target != null ? <p className="mt-1 text-xs text-muted-foreground">Configured target: {String(kpi.target)} {kpi.unit}</p> : null}{latest ? <p className="mt-1 text-xs text-muted-foreground">Baseline {number(latest.baselineValue)} · {new Date(latest.measuredAt).toLocaleDateString()}</p> : <p className="mt-1 text-xs text-muted-foreground">{preview ? "Awaiting tenant measurements" : "No verified measurement yet"}</p>}
                {metric.visualization === "trend" && chart.length > 0 ? <div className="mt-4 h-36" role="img" aria-label={`${metric.label}: baseline and measured result over time`}><ResponsiveContainer width="100%" height="100%"><LineChart data={chart}><CartesianGrid strokeDasharray="3 3" opacity={.2} /><XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} width={40} /><Tooltip /><Line type="monotone" dataKey="baseline" name="Baseline" stroke="var(--muted-foreground)" strokeDasharray="4 3" isAnimationActive={!reduced} /><Line type="monotone" dataKey="result" name="Verified result" stroke={design.accent} strokeWidth={2} isAnimationActive={!reduced} /></LineChart></ResponsiveContainer></div> : <p className="mt-4 border-t pt-3 text-xs text-muted-foreground">{metric.visualization === "trend" ? "Trend chart activates with verified data" : "Source-verified metric"} · {kpi?.direction === "decrease" ? "Lower is better" : kpi?.direction === "increase" ? "Higher is better" : "Maintain target"}</p>}
              </article>
            })}
          </div>
          <section className="rounded-xl border p-5"><h2 className="text-sm font-semibold">Success criteria</h2><ul className="mt-3 space-y-2 text-sm text-muted-foreground">{contract.outcome.success_criteria.map(c => <li key={c} className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{c}</li>)}</ul></section>
        </TabsContent>
        <TabsContent value="plays" className="space-y-4">
          <label className="block text-sm font-medium">Find a Play<input type="search" value={query} onChange={e => setQuery(e.target.value)} className="mt-2 block w-full rounded-lg border bg-background px-3 py-2 font-normal" placeholder="Search workflows and decisions" /></label>
          {!plays.length ? <p className="text-sm text-muted-foreground">No Plays match your search.</p> : null}
          <div className="grid gap-4 md:grid-cols-2">{plays.map(play => {
            const row = install?.plays.find(p => p.playKey === play.key)
            return <article key={play.key} className="space-y-3 rounded-xl border bg-card p-5"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-sm font-semibold">{play.name}</h2><Badge variant="outline">{play.trigger.cadence ?? play.trigger.type ?? "Manual"}</Badge></div><p className="text-sm text-muted-foreground">{play.description}</p><div className="flex flex-wrap gap-1.5">{play.kpiKeys.map(key => <Badge key={key} variant="secondary">{contract.outcome.kpis.find(k => k.key === key)?.label ?? readable(key)}</Badge>)}</div>{play.runtimeInputs.length ? <p className="text-xs text-muted-foreground">Required runtime inputs: {play.runtimeInputs.map(readable).join(", ")}</p> : null}{!preview ? <Button asChild size="sm" variant="outline"><Link href={row?.workflowId ? `/workflows/${row.workflowId}/builder` : `/plays?play=${encodeURIComponent(play.key)}`}>Review play<ArrowRight className="ml-2 h-3.5 w-3.5" aria-hidden /></Link></Button> : null}</article>
          })}</div>
        </TabsContent>
        <TabsContent value="evidence" className="space-y-4">
          <h2 className="text-base font-semibold">Measured business results</h2><p className="text-sm text-muted-foreground">Completed production runs, declared KPIs, and independently verified source records are required. Execution activity alone does not prove an outcome.</p>
          {!measurements.length ? <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No verified business measurements are available for this pack.</div> : <div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><caption className="sr-only">Verified department measurements</caption><thead className="bg-muted/30"><tr>{["KPI", "Baseline", "Result", "Measured", "Source evidence"].map(h => <th key={h} className="p-3 font-medium">{h}</th>)}</tr></thead><tbody>{measurements.map(m => <tr key={m.evidenceId} className="border-t"><td className="p-3">{contract.outcome.kpis.find(k => k.key === m.metricKey)?.label ?? readable(m.metricKey)}</td><td className="p-3 tabular-nums">{number(m.baselineValue)}</td><td className="p-3 tabular-nums">{number(m.resultValue)}</td><td className="whitespace-nowrap p-3">{new Date(m.measuredAt).toLocaleDateString()}</td><td className="p-3"><details><summary className="cursor-pointer">{m.sourceRecords.length} source records</summary><p className="mt-2 text-xs">{m.verificationMethod}</p><ul className="mt-2 space-y-1 text-xs">{m.sourceRecords.map((r,i) => <li key={i}>{r.system} · {r.record_type} · {r.record_id}</li>)}</ul></details></td></tr>)}</tbody></table></div>}
        </TabsContent>
        <TabsContent value="data" className="space-y-5">
          <section className="space-y-3"><h2 className="flex items-center gap-2 font-semibold"><Database className="h-4 w-4" aria-hidden />Dataset contracts</h2><p className="text-sm text-muted-foreground">These schemas define required data. Installation does not populate or ingest source records.</p><div className="grid gap-3 md:grid-cols-2">{contract.dataset.entities.map(e => <details key={e.name} className="rounded-xl border p-4"><summary className="cursor-pointer text-sm font-medium">{readable(e.name)} <span className="ml-2 text-xs font-normal text-muted-foreground">{e.source} · {e.fields.length} fields</span></summary><p className="mt-3 text-xs text-muted-foreground">Primary key: {e.primary_key}</p><p className="mt-2 break-words text-xs text-muted-foreground">{e.fields.join(", ")}</p></details>)}</div></section>
          <section className="space-y-3"><h2 className="text-sm font-semibold">Metric definitions</h2><div className="grid gap-3 md:grid-cols-2">{contract.dataset.metrics.map(metric => <article key={metric.key} className="rounded-xl border p-4"><h3 className="text-sm font-medium">{metric.label}</h3><p className="mt-2 break-words text-xs text-muted-foreground">{metric.formula}</p><p className="mt-2 text-xs text-muted-foreground">Unit: {metric.unit}</p></article>)}</div></section>
          <section className="space-y-3"><h2 className="flex items-center gap-2 font-semibold"><BookOpen className="h-4 w-4" aria-hidden />Operating standards</h2><div className="grid gap-3 md:grid-cols-2">{contract.knowledge.map((k,i) => { const source = sources.find(s => s.title === k.title); return <article key={`${k.title}-${i}`} className="rounded-xl border p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-sm font-medium">{k.title}</h3><Badge variant="outline">{preview ? "Tenant upload required" : readable(source?.status ?? "Source unavailable")}</Badge></div><p className="mt-2 text-sm text-muted-foreground">{k.purpose}</p>{source ? <Link href={`/sources/${source.id}`} className="mt-3 inline-block text-xs font-medium text-primary hover:underline">Open knowledge source →</Link> : null}</article>})}</div></section>
        </TabsContent>
        <TabsContent value="team" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">{contract.agents.map((agent,i) => <article key={agent.name} className="rounded-xl border p-4"><h2 className="text-sm font-semibold">{agent.name}</h2><p className="mt-2 text-sm text-muted-foreground">{agent.purpose}</p><div className="mt-3 flex flex-wrap gap-1">{agent.capabilities.map(c => <Badge key={c} variant="secondary">{readable(c)}</Badge>)}</div>{install?.agentIds[i] ? <Link href={`/agents/${install.agentIds[i]}`} className="mt-3 inline-block text-xs font-medium text-primary hover:underline">Open agent →</Link> : null}</article>)}</div>
          {install?.capabilityPackageIds.length ? <div className="rounded-xl border p-4"><p className="text-sm">Runtime capability packages require tenant review before activation.</p><Button asChild size="sm" variant="outline" className="mt-3"><Link href="/marketplace/capabilities">Review capabilities</Link></Button></div> : null}
          <section className="rounded-xl border p-5"><h2 className="font-semibold">Recent workflow activity</h2><p className="mt-1 text-xs text-muted-foreground">Latest {workspace.activityLimit} runs at most. Dry runs and simulations do not count as production proof.</p>{!recentRuns.length ? <p className="mt-4 text-sm text-muted-foreground">No workflow runs yet.</p> : <ul className="mt-3 divide-y">{recentRuns.slice(0,20).map(r => <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"><Link href={`/runs/${r.id}`} className="font-medium hover:underline">{r.status.replace(/_/g," ")} run</Link><span className="text-xs text-muted-foreground">{r.run_type} · {r.environment} · {new Date(r.created_at).toLocaleString()}</span></li>)}</ul>}</section>
        </TabsContent>
      </Tabs>
    </motion.section>
  )
}

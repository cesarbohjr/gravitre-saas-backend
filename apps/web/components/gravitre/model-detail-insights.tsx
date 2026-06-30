"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import {
  Activity,
  Beaker,
  Cable,
  CheckCircle2,
  Circle,
  FlaskConical,
  Layers,
  Link2,
  Rocket,
  Sparkles,
  Target,
  Workflow,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import type { MlModelDetail } from "@/types/api"
import {
  ML_LIFECYCLE_STEPS,
  ML_TRAINING_GUIDANCE,
  inferenceSampleInputs,
  layerForModelType,
  lifecycleStepIndex,
  lookupBaseModelOption,
  modelTypeMeta,
  stackLayerById,
  type BaseModelOption,
} from "@/lib/ml-registry-catalog"
import { cn } from "@/lib/utils"

const availabilityBadge: Record<string, string> = {
  platform: "bg-sky-500/10 text-sky-300 border-sky-500/25",
  connected: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
  requires_connection: "bg-amber-500/10 text-amber-400 border-amber-500/25",
}

function formatMetricKey(key: string): string {
  return key.replace(/_/g, " ")
}

function formatMetricValue(value: unknown): string {
  if (value == null) return "—"
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4)
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}

function formatDate(value?: string | null): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleString()
}

function formatBytes(bytes?: number | null): string {
  if (bytes == null || bytes <= 0) return "—"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

interface ModelDetailInsightsProps {
  model: MlModelDetail
  baseModelOption?: BaseModelOption
  connectedDataSources: string[]
  canDeploy: boolean
  isDeploying: boolean
  onDeploy: () => void
  inferenceJson: string
  onInferenceJsonChange: (value: string) => void
  isPredicting: boolean
  predictResult: string | null
  predictError: string | null
  onRunInference: () => void
  onResetInferenceSample: () => void
}

export function ModelDetailInsights({
  model,
  baseModelOption,
  connectedDataSources,
  canDeploy,
  isDeploying,
  onDeploy,
  inferenceJson,
  onInferenceJsonChange,
  isPredicting,
  predictResult,
  predictError,
  onRunInference,
  onResetInferenceSample,
}: ModelDetailInsightsProps) {
  const typeMeta = modelTypeMeta(model.modelType)
  const layer = stackLayerById(layerForModelType(model.modelType))
  const guidance = ML_TRAINING_GUIDANCE[model.modelType]
  const activeStep = lifecycleStepIndex(model.status)
  const hasVersions = model.versions.length > 0
  const canInfer =
    hasVersions &&
    (model.status === "ready" || model.status === "deployed") &&
    (model.deployedVersion != null || model.currentVersion > 0)

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-card/80 via-card/40 to-emerald-500/5 p-5 sm:p-6"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-emerald-500/10 blur-3xl"
        />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            {typeMeta ? (
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
                <Sparkles className="h-3 w-3" />
                {typeMeta.label}
              </div>
            ) : null}
            <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
              {typeMeta?.tagline ??
                "Org-scoped model entry tracked through training, validation, and deployment."}
              {model.taskType ? (
                <>
                  {" "}
                  Task profile:{" "}
                  <span className="text-foreground/90">{model.taskType.replace(/_/g, " ")}</span>.
                </>
              ) : null}
            </p>
            {typeMeta ? (
              <p className="text-xs text-muted-foreground">
                Common uses: {typeMeta.examples.join(" · ")}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link href="/training">
                <FlaskConical className="mr-1 h-4 w-4" />
                Training
              </Link>
            </Button>
            <Button size="sm" disabled={!canDeploy || isDeploying} onClick={onDeploy}>
              <Rocket className="mr-1 h-4 w-4" />
              {isDeploying ? "Deploying…" : "Deploy latest"}
            </Button>
          </div>
        </div>
      </motion.section>

      <Card className="border-border/70 bg-card/40">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Workflow className="h-4 w-4 text-muted-foreground" />
            Model lifecycle
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-5">
            {ML_LIFECYCLE_STEPS.map((step, index) => {
              const done = index < activeStep || (model.status === "deployed" && index <= activeStep)
              const current = index === activeStep
              return (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={cn(
                    "rounded-xl border p-3 text-center transition-colors",
                    current && "border-emerald-500/40 bg-emerald-500/5",
                    done && !current && "border-emerald-500/25 bg-emerald-500/5",
                    !done && !current && "border-border/60 bg-secondary/20"
                  )}
                >
                  <div className="mb-2 flex justify-center">
                    {done ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                    ) : (
                      <Circle className={cn("h-5 w-5", current ? "text-emerald-400" : "text-muted-foreground/40")} />
                    )}
                  </div>
                  <p className="text-xs font-medium">{step.label}</p>
                  <p className="mt-1 text-[10px] leading-snug text-muted-foreground">{step.detail}</p>
                </motion.div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        {layer ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className={cn(
              "rounded-xl border bg-background/50 p-4 ring-1 lg:col-span-1",
              layer.accent
            )}
          >
            <div className="mb-2 flex items-center gap-2">
              <Layers className="h-4 w-4" />
              <p className="text-sm font-medium">{layer.title}</p>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">{layer.summary}</p>
            <ul className="mt-3 space-y-1">
              {layer.highlights.map((h) => (
                <li
                  key={h}
                  className="text-[11px] text-muted-foreground before:mr-1.5 before:text-emerald-400 before:content-['•']"
                >
                  {h}
                </li>
              ))}
            </ul>
          </motion.div>
        ) : null}

        <Card className="border-border/70 lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Target className="h-4 w-4" />
              Base model
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {model.baseModel ? (
              <>
                <p className="font-medium text-foreground">
                  {baseModelOption?.label ?? model.baseModel}
                </p>
                {baseModelOption ? (
                  <>
                    <p className="text-xs text-muted-foreground">{baseModelOption.description}</p>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      <Badge variant="outline" className="text-[10px]">
                        {baseModelOption.provider}
                      </Badge>
                      {baseModelOption.versionTag ? (
                        <Badge variant="outline" className="font-mono text-[10px]">
                          {baseModelOption.versionTag}
                        </Badge>
                      ) : null}
                      {baseModelOption.fineTunable ? (
                        <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-400">
                          Fine-tunable
                        </Badge>
                      ) : null}
                      <Badge
                        variant="outline"
                        className={cn("text-[10px] capitalize", availabilityBadge[baseModelOption.availability])}
                      >
                        {baseModelOption.availability === "platform"
                          ? "Platform"
                          : baseModelOption.availability === "connected"
                            ? "Connected"
                            : "Needs connector"}
                      </Badge>
                    </div>
                    <p className="pt-1 font-mono text-[10px] text-muted-foreground">{baseModelOption.id}</p>
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground font-mono">{model.baseModel}</p>
                )}
              </>
            ) : (
              <p className="text-muted-foreground">No base model selected at registration.</p>
            )}
          </CardContent>
        </Card>

        <Card className="border-border/70 lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Cable className="h-4 w-4" />
              Data sources
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {connectedDataSources.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {connectedDataSources.map((source) => (
                  <Badge key={source} variant="secondary" className="capitalize text-[10px]">
                    {source.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Connect PostgreSQL, Snowflake, or Segment on{" "}
                <Link href="/connectors" className="text-primary underline-offset-4 hover:underline">
                  Connectors
                </Link>{" "}
                to unlock tabular base models.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Type" value={model.modelType.replace(/_/g, " ")} capitalize />
            <Row label="Current version" value={`v${model.currentVersion}`} />
            <Row
              label="Deployed version"
              value={model.deployedVersion != null ? `v${model.deployedVersion}` : "—"}
            />
            {model.datasetId ? (
              <div className="flex justify-between gap-2">
                <span className="text-muted-foreground">Dataset</span>
                <Link href="/training" className="truncate text-primary underline-offset-4 hover:underline">
                  {model.datasetId}
                </Link>
              </div>
            ) : (
              <Row label="Dataset" value="Not linked" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Timeline</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Created" value={formatDate(model.createdAt)} />
            <Row label="Updated" value={formatDate(model.updatedAt)} />
          </CardContent>
        </Card>
      </div>

      <Card className="border-emerald-500/20 bg-emerald-500/[0.03]">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Beaker className="h-4 w-4 text-emerald-500" />
            Training guidance
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="font-medium text-foreground/90">{guidance.headline}</p>
          <ul className="space-y-1.5">
            {guidance.bullets.map((bullet) => (
              <li key={bullet} className="text-xs leading-relaxed text-muted-foreground before:mr-2 before:content-['→']">
                {bullet}
              </li>
            ))}
          </ul>
          <div className="rounded-lg border border-border/60 bg-background/50 p-3 text-xs">
            <p className="font-medium text-foreground/90">Dataset</p>
            <p className="mt-1 text-muted-foreground">{guidance.datasetHint}</p>
            <p className="mt-2 font-medium text-foreground/90">Key metrics</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {guidance.evalMetrics.map((m) => (
                <Badge key={m} variant="outline" className="text-[10px] capitalize">
                  {formatMetricKey(m)}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Versions</CardTitle>
        </CardHeader>
        <CardContent>
          {!hasVersions ? (
            <p className="text-sm text-muted-foreground">
              No trained versions yet. Start a training job from{" "}
              <Link href="/training" className="text-primary underline-offset-4 hover:underline">
                Training
              </Link>{" "}
              and link it to this registry entry.
            </p>
          ) : (
            <ul className="space-y-2">
              {model.versions.map((version, index) => {
                const metrics = version.metrics ?? {}
                const metricEntries = Object.entries(metrics).filter(([, v]) => v != null)
                const isLive = model.deployedVersion === version.version
                return (
                  <motion.li
                    key={version.version}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.04 }}
                    className={cn(
                      "rounded-lg border px-3 py-3 text-sm",
                      isLive ? "border-emerald-500/30 bg-emerald-500/5" : "border-border/70"
                    )}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">v{version.version}</span>
                        {isLive ? (
                          <Badge variant="outline" className="border-emerald-500/30 text-emerald-400 text-[10px]">
                            Live
                          </Badge>
                        ) : null}
                      </div>
                      <span className="text-xs text-muted-foreground">{formatDate(version.createdAt)}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>Artifact: {formatBytes(version.artifactSizeBytes)}</span>
                      {metricEntries.length > 0 ? (
                        metricEntries.slice(0, 6).map(([key, value]) => (
                          <span key={key}>
                            {formatMetricKey(key)}: {formatMetricValue(value)}
                          </span>
                        ))
                      ) : (
                        <span>No metrics recorded</span>
                      )}
                    </div>
                  </motion.li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card className="border-teal-500/20 bg-teal-500/[0.03]">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-4 w-4 text-teal-500" />
            Inference smoke test
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {!canInfer ? (
            <p className="text-sm text-muted-foreground">
              Train at least one version and deploy before running live inference against production.
            </p>
          ) : (
            <>
              <p className="text-xs text-muted-foreground">
                Sends a sample payload to{" "}
                <code className="rounded bg-secondary/80 px-1 py-0.5 text-[11px]">POST /api/ml/models/{model.id}/predict</code>{" "}
                via the production backend proxy.
              </p>
              <Textarea
                value={inferenceJson}
                onChange={(e) => onInferenceJsonChange(e.target.value)}
                rows={6}
                className="font-mono text-xs"
                spellCheck={false}
              />
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={onResetInferenceSample}>
                  Reset sample
                </Button>
                <Button size="sm" disabled={isPredicting} onClick={onRunInference}>
                  {isPredicting ? "Running…" : "Run inference"}
                </Button>
              </div>
              {predictError ? (
                <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-xs text-red-300">
                  {predictError}
                </div>
              ) : null}
              {predictResult ? (
                <pre className="max-h-48 overflow-auto rounded-lg border border-border/70 bg-background/80 p-3 text-xs text-emerald-300">
                  {predictResult}
                </pre>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <div className="rounded-xl border border-border/50 bg-secondary/20 p-4 text-xs text-muted-foreground">
        <p className="flex items-center gap-1.5 font-medium text-foreground/90">
          <Link2 className="h-3.5 w-3.5" />
          Wire into workflows
        </p>
        <p className="mt-2">
          Reference this model ID from Meson inference nodes or agent tool configs once deployed.
          Roll back by redeploying a prior version from this page.
        </p>
      </div>
    </div>
  )
}

function Row({
  label,
  value,
  capitalize: cap,
}: {
  label: string
  value: string
  capitalize?: boolean
}) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("truncate", cap && "capitalize")}>{value}</span>
    </div>
  )
}

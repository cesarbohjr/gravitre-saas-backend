"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import {
  Activity,
  ArrowRight,
  Check,
  Cloud,
  Database,
  FileText,
  Globe,
  HardDrive,
  Loader2,
  Search,
  Server,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { sourcesApi } from "@/lib/api"
import type {
  CreateSourceRequest,
  DataSourceConnectionField,
  DataSourceTypeDefinition,
} from "@/types/api"

const ICON_MAP: Record<string, typeof Database> = {
  database: Database,
  cloud: Cloud,
  leaf: HardDrive,
  file: FileText,
  globe: Globe,
  search: Search,
  stream: Activity,
  webhook: Globe,
  table: Server,
}

interface AddDataSourceModalProps {
  open: boolean
  onClose: () => void
  onCreate: (data: CreateSourceRequest) => Promise<void>
  creating: boolean
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: DataSourceConnectionField
  value: string | number | boolean
  onChange: (value: string | number | boolean) => void
}) {
  const baseClass =
    "mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none"

  if (field.type === "boolean") {
    return (
      <label className="mt-2 flex items-center gap-2 text-sm text-foreground">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
          className="rounded border-border"
        />
        {field.label}
      </label>
    )
  }

  if (field.type === "textarea") {
    return (
      <textarea
        rows={4}
        placeholder={field.placeholder}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        className={cn(baseClass, "font-mono text-xs")}
      />
    )
  }

  if (field.type === "select" && field.options?.length) {
    return (
      <select
        value={String(value ?? field.default ?? field.options[0]?.value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        className={baseClass}
      >
        {field.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    )
  }

  return (
    <input
      type={field.type === "password" ? "password" : field.type === "number" ? "number" : "text"}
      placeholder={field.placeholder}
      value={value === undefined || value === null ? "" : String(value)}
      onChange={(event) =>
        onChange(field.type === "number" ? Number(event.target.value) : event.target.value)
      }
      className={cn(baseClass, field.key.includes("connection") && "font-mono")}
    />
  )
}

export function AddDataSourceModal({ open, onClose, onCreate, creating }: AddDataSourceModalProps) {
  const [step, setStep] = useState(1)
  const [selectedType, setSelectedType] = useState<DataSourceTypeDefinition | null>(null)
  const [search, setSearch] = useState("")
  const [category, setCategory] = useState<string | null>(null)
  const [sourceName, setSourceName] = useState("")
  const [config, setConfig] = useState<Record<string, string | number | boolean>>({})
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<Awaited<ReturnType<typeof sourcesApi.testConnection>> | null>(null)
  const [testError, setTestError] = useState<string | null>(null)

  const { data: typesPayload, isLoading: typesLoading } = useSWR(
    open ? "/api/sources/types" : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const { data: connectorsPayload } = useSWR(
    open && selectedType?.oauthVendor ? `/api/sources/connectors?vendor=${selectedType.oauthVendor}` : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const linkedConnectors =
    (connectorsPayload as { connectors?: Array<{ id: string; name: string; status: string }> } | undefined)
      ?.connectors ?? []

  const types = useMemo(() => {
    const raw = (typesPayload as { types?: DataSourceTypeDefinition[] } | undefined)?.types ?? []
    return raw.filter((type) => {
      if (category && type.category !== category) return false
      if (!search.trim()) return true
      const q = search.trim().toLowerCase()
      return type.name.toLowerCase().includes(q) || type.id.includes(q)
    })
  }, [typesPayload, category, search])

  const categories = (typesPayload as { categories?: Array<{ id: string; label: string }> } | undefined)
    ?.categories ?? []

  useEffect(() => {
    if (!selectedType) return
    const defaults: Record<string, string | number | boolean> = {}
    for (const field of selectedType.connectionFields) {
      if (field.default !== undefined) defaults[field.key] = field.default
    }
    setConfig(defaults)
  }, [selectedType])

  const resetAndClose = () => {
    onClose()
    setStep(1)
    setSelectedType(null)
    setSearch("")
    setCategory(null)
    setTestResult(null)
    setTestError(null)
    setSourceName("")
    setConfig({})
  }

  const handleSelectType = (type: DataSourceTypeDefinition) => {
    setSelectedType(type)
    setSourceName(type.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"))
    setStep(2)
  }

  const handleTest = async () => {
    if (!selectedType) return
    setTesting(true)
    setTestError(null)
    setTestResult(null)
    try {
      const result = await sourcesApi.testConnection({
        typeId: selectedType.id,
        config,
        connectionString:
          typeof config.connection_string === "string" ? config.connection_string : undefined,
      })
      setTestResult(result)
    } catch (err) {
      setTestError(err instanceof Error ? err.message : "Connection test failed")
    } finally {
      setTesting(false)
    }
  }

  const handleCreateSource = async () => {
    if (!selectedType || !sourceName.trim()) return
    await onCreate({
      name: sourceName.trim(),
      type: selectedType.name,
      typeId: selectedType.id,
      description: `${selectedType.name} data source`,
      config,
      connectionString:
        typeof config.connection_string === "string" ? config.connection_string : undefined,
    })
    resetAndClose()
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && resetAndClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {step === 1 && "Add Data Source"}
            {step === 2 && `Configure ${selectedType?.name ?? "Connection"}`}
            {step === 3 && "Test & Connect"}
          </DialogTitle>
        </DialogHeader>

        <div className="flex items-center gap-2 mb-4">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={cn(
                "h-1.5 flex-1 rounded-full transition-colors",
                s <= step ? "bg-primary" : "bg-secondary"
              )}
            />
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search 50+ data sources..."
                  className="w-full rounded-md border border-border bg-secondary py-2 pl-9 pr-3 text-sm"
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setCategory(null)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium",
                  category === null ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
                )}
              >
                All
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => setCategory(cat.id)}
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium",
                    category === cat.id ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
                  )}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            {typesLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : (
              <div className="grid max-h-[420px] grid-cols-2 gap-3 overflow-y-auto pr-1 sm:grid-cols-3">
                {types.map((type) => {
                  const Icon = ICON_MAP[type.icon] ?? Database
                  return (
                    <button
                      key={type.id}
                      type="button"
                      onClick={() => handleSelectType(type)}
                      className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 text-left transition-all hover:border-primary/30 hover:bg-card/80"
                    >
                      <div
                        className="flex h-10 w-10 items-center justify-center rounded-lg"
                        style={{ backgroundColor: `${type.color}22` }}
                      >
                        <Icon className="h-5 w-5" style={{ color: type.color }} />
                      </div>
                      <div className="min-w-0">
                        <span className="block truncate text-sm font-medium text-foreground">{type.name}</span>
                        <span className="block truncate text-[10px] text-muted-foreground">{type.categoryLabel}</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {step === 2 && selectedType && (
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Source Name
              </label>
              <input
                type="text"
                value={sourceName}
                onChange={(event) => setSourceName(event.target.value)}
                className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm"
              />
            </div>

            {selectedType.oauthVendor && linkedConnectors.length > 0 ? (
              <div>
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Linked Connector *
                </label>
                <select
                  value={String(config.connector_id ?? "")}
                  onChange={(event) => setConfig((current) => ({ ...current, connector_id: event.target.value }))}
                  className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm"
                >
                  <option value="">Select a connected integration…</option>
                  {linkedConnectors.map((connector) => (
                    <option key={connector.id} value={connector.id}>
                      {connector.name} ({connector.status})
                    </option>
                  ))}
                </select>
                <p className="mt-2 text-[11px] text-muted-foreground">
                  Or connect one first from{" "}
                  <a href="/connectors" className="text-primary underline">
                    Connectors
                  </a>
                  .
                </p>
              </div>
            ) : null}

            {selectedType.connectionFields.map((field) => (
              field.key === "connector_id" && selectedType.oauthVendor && linkedConnectors.length > 0 ? null : (
              <div key={field.key}>
                {field.type !== "boolean" && (
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {field.label}
                    {field.required ? " *" : ""}
                  </label>
                )}
                <FieldInput
                  field={field}
                  value={config[field.key] ?? ""}
                  onChange={(value) => setConfig((current) => ({ ...current, [field.key]: value }))}
                />
              </div>
              )
            ))}

            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button onClick={() => setStep(3)} disabled={!sourceName.trim()}>
                Continue <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            {!testing && !testResult && !testError && (
              <div className="py-6 text-center">
                <p className="mb-4 text-sm text-muted-foreground">
                  Test connectivity and discover schema before saving
                </p>
                <Button onClick={() => void handleTest()} className="gap-2">
                  <Activity className="h-4 w-4" />
                  Test Connection
                </Button>
              </div>
            )}

            {testing && (
              <div className="py-6 text-center">
                <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">Testing connection...</p>
              </div>
            )}

            {testError && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-center text-sm text-red-400">
                {testError}
              </div>
            )}

            {testResult?.success && (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
                <div className="text-center">
                  <Check className="mx-auto mb-2 h-8 w-8 text-emerald-500" />
                  <p className="text-sm font-medium text-emerald-400">
                    {testResult.message ?? "Connection successful"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Found {testResult.tables ?? 0} tables
                    {(testResult.records ?? 0) > 0 ? `, ~${testResult.records} records` : ""}
                    {testResult.driverPending ? " (driver validation only)" : ""}
                  </p>
                </div>
                {testResult.suggestions?.length ? (
                  <div className="mt-4 border-t border-emerald-500/20 pt-3">
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Suggested questions after connect
                    </p>
                    <ul className="space-y-1 text-xs text-muted-foreground">
                      {testResult.suggestions.slice(0, 3).map((item) => (
                        <li key={item}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" onClick={() => setStep(2)}>
                Back
              </Button>
              {!testResult && !testing ? (
                <Button variant="outline" onClick={() => void handleTest()}>
                  Retry Test
                </Button>
              ) : null}
              <Button
                onClick={() => void handleCreateSource()}
                disabled={!testResult?.success || creating || !sourceName.trim()}
                className="gap-2"
              >
                {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                {creating ? "Adding..." : "Add Source"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

"use client"

import { useState, use } from "react"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { ArrowLeft, Save, Eye, EyeOff, AlertCircle, CheckCircle } from "lucide-react"

interface Secret {
  key: string
  value: string
  isVisible: boolean
}

export default function IntegrationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const isAdmin = true

  const [status, setStatus] = useState<string>("active")
  const [config, setConfig] = useState<string>(
    JSON.stringify(
      {
        channel: "#alerts",
        webhook_url: "https://hooks.slack.com/services/xxx",
        notify_on_failure: true,
        notify_on_success: false,
      },
      null,
      2
    )
  )
  const [secrets, setSecrets] = useState<Secret[]>([
    { key: "API_TOKEN", value: "sk-xxxxxxxxxxxx", isVisible: false },
    { key: "WEBHOOK_SECRET", value: "whsec_xxxxxxxx", isVisible: false },
  ])
  const [configError, setConfigError] = useState<string | null>(null)
  const [configSuccess, setConfigSuccess] = useState<string | null>(null)
  const [secretsError, setSecretsError] = useState<string | null>(null)
  const [secretsSuccess, setSecretsSuccess] = useState<string | null>(null)
  const [isSavingConfig, setIsSavingConfig] = useState(false)
  const [isSavingSecrets, setIsSavingSecrets] = useState(false)

  const handleSaveConfig = async () => {
    setIsSavingConfig(true)
    setConfigError(null)
    setConfigSuccess(null)
    try {
      // Validate JSON
      JSON.parse(config)
      // Simulate save
      await new Promise((resolve) => setTimeout(resolve, 500))
      setConfigSuccess("Configuration saved successfully")
    } catch {
      setConfigError("Invalid JSON configuration")
    } finally {
      setIsSavingConfig(false)
    }
  }

  const handleSaveSecrets = async () => {
    setIsSavingSecrets(true)
    setSecretsError(null)
    setSecretsSuccess(null)
    try {
      // Simulate save
      await new Promise((resolve) => setTimeout(resolve, 500))
      setSecretsSuccess("Secrets saved successfully")
    } catch {
      setSecretsError("Failed to save secrets")
    } finally {
      setIsSavingSecrets(false)
    }
  }

  const toggleSecretVisibility = (index: number) => {
    setSecrets((prev) =>
      prev.map((s, i) => (i === index ? { ...s, isVisible: !s.isVisible } : s))
    )
  }

  const updateSecretValue = (index: number, value: string) => {
    setSecrets((prev) => prev.map((s, i) => (i === index ? { ...s, value } : s)))
  }

  return (
    <AppShell title="Integration">
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <Link
            href="/integrations"
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Integrations
          </Link>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold text-foreground">Slack Notifications</h1>
              <StatusBadge variant="success" dot>
                active
              </StatusBadge>
              <EnvironmentBadge environment="production" />
            </div>
            {!isAdmin && (
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                Read-only
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Integration ID: <span className="font-mono">{id}</span>
          </p>
        </div>

        <div className="space-y-6">
          {/* Configuration Card */}
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Configuration</h2>
            </div>
            <div className="p-4 space-y-4">
              {/* Status Select */}
              <div className="flex items-center gap-4">
                <label className="text-sm text-muted-foreground w-24">Status</label>
                <Select
                  value={status}
                  onValueChange={setStatus}
                  disabled={!isAdmin}
                >
                  <SelectTrigger className="w-40 h-8 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Config JSON Editor */}
              <div>
                <label className="mb-2 block text-sm text-muted-foreground">
                  Configuration JSON
                </label>
                <textarea
                  value={config}
                  onChange={(e) => setConfig(e.target.value)}
                  disabled={!isAdmin}
                  className="w-full h-48 rounded-md border border-border bg-muted/50 px-3 py-2 font-mono text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  spellCheck={false}
                />
              </div>

              {/* Config Messages */}
              {configError && (
                <div className="flex items-center gap-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  {configError}
                </div>
              )}
              {configSuccess && (
                <div className="flex items-center gap-2 text-sm text-success">
                  <CheckCircle className="h-4 w-4" />
                  {configSuccess}
                </div>
              )}

              {/* Save Button */}
              {isAdmin && (
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    className="h-8 gap-2"
                    onClick={handleSaveConfig}
                    disabled={isSavingConfig}
                  >
                    <Save className="h-3.5 w-3.5" />
                    {isSavingConfig ? "Saving..." : "Save configuration"}
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Secrets Card */}
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Secrets</h2>
            </div>
            <div className="p-4 space-y-4">
              {secrets.map((secret, index) => (
                <div key={secret.key} className="flex items-center gap-4">
                  <label className="text-sm text-muted-foreground w-36 font-mono">
                    {secret.key}
                  </label>
                  <div className="flex flex-1 items-center gap-2">
                    <Input
                      type={secret.isVisible ? "text" : "password"}
                      value={secret.value}
                      onChange={(e) => updateSecretValue(index, e.target.value)}
                      disabled={!isAdmin}
                      className="h-8 font-mono text-sm"
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0"
                      onClick={() => toggleSecretVisibility(index)}
                    >
                      {secret.isVisible ? (
                        <EyeOff className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      )}
                    </Button>
                  </div>
                </div>
              ))}

              {/* Secrets Messages */}
              {secretsError && (
                <div className="flex items-center gap-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  {secretsError}
                </div>
              )}
              {secretsSuccess && (
                <div className="flex items-center gap-2 text-sm text-success">
                  <CheckCircle className="h-4 w-4" />
                  {secretsSuccess}
                </div>
              )}

              {/* Save Button */}
              {isAdmin && (
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    className="h-8 gap-2"
                    onClick={handleSaveSecrets}
                    disabled={isSavingSecrets}
                  >
                    <Save className="h-3.5 w-3.5" />
                    {isSavingSecrets ? "Saving..." : "Save secrets"}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}

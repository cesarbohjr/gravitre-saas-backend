"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Package,
  Plug,
  Sparkles,
} from "lucide-react"
import { toast } from "sonner"
import type { DepartmentRolePack } from "@/types/api"

function ConnectorChecklist({ pack }: { pack: DepartmentRolePack }) {
  return (
    <ul className="space-y-2">
      {pack.connectorChecklist.map((item) => (
        <li
          key={`${pack.packId}-${item.connectorType}`}
          className="flex items-center justify-between gap-2 rounded-md border border-border/60 px-3 py-2 text-sm"
        >
          <div className="flex items-center gap-2 min-w-0">
            <Plug className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
            <span className="truncate text-foreground">{item.label}</span>
            {!item.required ? (
              <Badge variant="outline" className="shrink-0 text-[10px]">
                Optional
              </Badge>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {item.connected ? (
              <CheckCircle2 className="h-4 w-4 text-success" aria-label="Connected" />
            ) : (
              <Button variant="outline" size="sm" className="h-7" asChild>
                <Link href={item.connectPath || `/connectors?type=${item.connectorType}`}>Connect</Link>
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

function PackCard({
  pack,
  isAdmin,
  installing,
  onInstall,
}: {
  pack: DepartmentRolePack
  isAdmin: boolean
  installing: string | null
  onInstall: (packId: string) => void
}) {
  const ready = pack.connectorsReady || pack.requiredConnectorsTotal === 0
  return (
    <Card className={cn(pack.installed && "border-success/30")}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">{pack.name}</CardTitle>
            <CardDescription>{pack.department}</CardDescription>
          </div>
          {pack.installed ? (
            <Badge variant="outline" className="border-success/30 bg-success/10 text-success">
              Installed
            </Badge>
          ) : (
            <Badge variant="outline">Not installed</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground text-pretty">{pack.description}</p>
        <div className="flex flex-wrap gap-1.5">
          {pack.tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="text-[10px] capitalize">
              {tag}
            </Badge>
          ))}
        </div>
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Connector checklist
          </p>
          <ConnectorChecklist pack={pack} />
        </div>
        <p className="text-xs text-muted-foreground">
          {pack.requiredConnectorsConnected}/{pack.requiredConnectorsTotal} required connectors connected
        </p>
        {isAdmin ? (
          <Button
            className="w-full sm:w-auto"
            disabled={!!installing || (!ready && !pack.installed)}
            onClick={() => onInstall(pack.packId)}
          >
            {installing === pack.packId ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                Installing…
              </>
            ) : pack.installed ? (
              "Reinstall pack"
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" aria-hidden />
                Install pack
              </>
            )}
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">Admin access required to install packs.</p>
        )}
      </CardContent>
    </Card>
  )
}

export default function RolePacksPage() {
  const { user } = useAuth()
  const [installing, setInstalling] = useState<string | null>(null)
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"

  const { data, isLoading, mutate } = useSWR(
    user ? "marketplace-role-packs" : null,
    () => marketplaceApi.listRolePacks(),
  )

  const handleInstall = async (packId: string) => {
    setInstalling(packId)
    try {
      const result = await marketplaceApi.installRolePack(packId)
      toast.success(`${packId} installed`, {
        description: `${result.workflowIds?.length ?? 0} workflow(s), ${result.agentIds?.length ?? 0} agent(s)`,
      })
      await mutate()
    } catch (err) {
      toast.error("Install failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      setInstalling(null)
    }
  }

  const packs = data?.packs ?? []

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-6 md:py-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
              <Link href="/connectors">
                <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                Apps
              </Link>
            </Button>
            <h1 className="flex items-center gap-2 text-2xl font-semibold text-foreground">
              <Package className="h-6 w-6 text-primary" aria-hidden />
              Department role packs
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground text-pretty">
              One-click install of agents, RAG sources, workflows, and connector checklists for Sales, Marketing,
              Support, and Finance.
            </p>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link href="/settings/enterprise?tab=cs">CS dashboard</Link>
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-24 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" aria-hidden />
            Loading packs…
          </div>
        ) : packs.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center text-sm text-muted-foreground">
              No department packs available for this organization.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {packs.map((pack) => (
              <PackCard
                key={pack.packId}
                pack={pack}
                isAdmin={isAdmin}
                installing={installing}
                onInstall={(id) => void handleInstall(id)}
              />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}

"use client"

import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState } from "@/components/gravitre/empty-state"
import { fetcher } from "@/lib/fetcher"
import { AlertCircle, Server } from "lucide-react"
import { toast } from "sonner"
import { useEffect } from "react"

interface ConnectedSystem {
  id: string
  name: string
  type: string
  status: string
}

export default function SystemsPage() {
  const { data, error, isLoading } = useSWR<{ systems: ConnectedSystem[] }>("/api/systems", fetcher)
  const systems = data?.systems ?? []

  useEffect(() => {
    if (error) {
      toast.error("Failed to load data")
    }
  }, [error])

  if (isLoading) {
    return (
      <AppShell title="Systems">
        <div className="space-y-4 p-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title="Systems">
        <EmptyState
          icon={AlertCircle}
          title="Error loading data"
          description="Failed to load data"
          variant="error"
        />
      </AppShell>
    )
  }

  if (!systems.length) {
    return (
      <AppShell title="Systems">
        <EmptyState
          icon={Server}
          title="No systems yet"
          description="Connect your first system to get started."
        />
      </AppShell>
    )
  }

  return (
    <AppShell title="Systems">
      <div className="p-6 space-y-3">
        {systems.map((system) => (
          <div key={system.id} className="rounded-lg border border-border p-4">
            <div className="text-sm font-medium">{system.name}</div>
            <div className="text-xs text-muted-foreground mt-1">
              {system.type} · {system.status}
            </div>
          </div>
        ))}
      </div>
    </AppShell>
  )
}

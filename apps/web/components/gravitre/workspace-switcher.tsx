"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { toast } from "sonner"
import { organizationsApi } from "@/lib/api"
import type { Organization } from "@/types/api"
import { useAuth } from "@/lib/auth-context"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { OrgMonogram } from "@/components/gravitre/organization-logo"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import {
  getSelectedEnvironmentFromStorage,
  setSelectedEnvironmentInStorage,
  type AppEnvironment,
} from "@/lib/environment-context"
import {
  ensureSelectedOrg,
  getSelectedOrgFromStorage,
  invalidateOrgCache,
  setSelectedOrgInStorage,
} from "@/lib/org-context"

/** Org + environment identity shared by the sidebar switcher and the mobile top bar. */
export function useWorkspaceIdentity() {
  const { user } = useAuth()
  const [environment, setEnvironment] = useState<AppEnvironment>(() => getSelectedEnvironmentFromStorage())
  const [org, setOrg] = useState(() => getSelectedOrgFromStorage()?.name ?? "Organization")
  const [orgId, setOrgId] = useState(() => getSelectedOrgFromStorage()?.id ?? null)
  const [isSwitchingOrg, setIsSwitchingOrg] = useState(false)

  // Real membership list (organizationsApi.list), never hardcoded demo orgs:
  // switching to an org the user is not a member of 403s every request.
  const { data: orgsData } = useSWR(user ? "organizations:list" : null, () => organizationsApi.list(), {
    revalidateOnFocus: false,
  })
  const memberOrgs = (orgsData?.organizations as Organization[] | undefined) ?? []

  useEffect(() => {
    void ensureSelectedOrg().then((resolvedOrgId) => {
      const stored = getSelectedOrgFromStorage()
      if (stored?.name) setOrg(stored.name)
      else if (resolvedOrgId) setOrg("Organization")
      setOrgId(stored?.id ?? resolvedOrgId ?? null)
    })
    setEnvironment(getSelectedEnvironmentFromStorage())
    const onEnvChange = (event: Event) => {
      const detail = (event as CustomEvent<AppEnvironment>).detail
      if (detail) setEnvironment(detail)
    }
    window.addEventListener("gravitre:environment-changed", onEnvChange)
    return () => window.removeEventListener("gravitre:environment-changed", onEnvChange)
  }, [])

  const selectEnvironment = (next: AppEnvironment) => {
    setEnvironment(next)
    setSelectedEnvironmentInStorage(next)
  }

  const switchOrg = async (nextOrgId: string, nextOrgName: string) => {
    if (nextOrgId === orgId || isSwitchingOrg) return
    setIsSwitchingOrg(true)
    try {
      // Real backend switch (STA-72); localStorage keeps every fetch's x-org-id in sync.
      await organizationsApi.switch(nextOrgId)
      setOrg(nextOrgName)
      setSelectedOrgInStorage({ id: nextOrgId, name: nextOrgName })
      invalidateOrgCache()
      window.location.reload()
    } catch (error) {
      console.error("Failed to switch organization", error)
      toast.error(error instanceof Error ? error.message : "Failed to switch organization")
      setIsSwitchingOrg(false)
    }
  }

  return { org, orgId, memberOrgs, isSwitchingOrg, switchOrg, environment, selectEnvironment }
}

type WorkspaceIdentity = ReturnType<typeof useWorkspaceIdentity>

function OrgMenuItems({ identity }: { identity: WorkspaceIdentity }) {
  const { memberOrgs, org, orgId, isSwitchingOrg, switchOrg } = identity
  return (
    <>
      <DropdownMenuLabel className="text-[11px] font-medium text-muted-foreground">Organizations</DropdownMenuLabel>
      {memberOrgs.length > 0 ? (
        memberOrgs.map((memberOrg) => (
          <DropdownMenuItem
            key={memberOrg.id}
            onClick={() => void switchOrg(memberOrg.id, memberOrg.name)}
            disabled={isSwitchingOrg}
            className="gap-2.5"
          >
            <OrgMonogram name={memberOrg.name} size="sm" />
            <span className="flex-1 truncate">{memberOrg.name}</span>
            {memberOrg.id === orgId ? <Icon name="check" size="sm" className="text-primary" /> : null}
          </DropdownMenuItem>
        ))
      ) : (
        <DropdownMenuItem disabled className="gap-2.5 text-muted-foreground">
          {org}
        </DropdownMenuItem>
      )}
      <DropdownMenuSeparator />
      <DropdownMenuItem className="cursor-pointer gap-2 text-muted-foreground" asChild>
        <Link href="/settings/organizations">
          <Icon name="settings" size="sm" />
          Manage organizations
        </Link>
      </DropdownMenuItem>
    </>
  )
}

function EnvironmentMenuItems({ identity }: { identity: WorkspaceIdentity }) {
  return (
    <>
      <DropdownMenuLabel className="text-[11px] font-medium text-muted-foreground">Environment</DropdownMenuLabel>
      {(["production", "staging"] as const).map((env) => (
        <DropdownMenuItem key={env} onClick={() => identity.selectEnvironment(env)} className="gap-2">
          <span
            className={cn("h-2 w-2 rounded-full", env === "production" ? "bg-success" : "bg-warning")}
            aria-hidden
          />
          <span className="flex-1 capitalize">{env}</span>
          {identity.environment === env ? <Icon name="check" size="sm" className="text-primary" /> : null}
        </DropdownMenuItem>
      ))}
    </>
  )
}

/**
 * Workspace identity at the head of the navigation: which organization and which
 * environment every action on screen applies to. Rail mode shows the monogram only.
 */
export function WorkspaceSwitcher({ collapsed = false, className }: { collapsed?: boolean; className?: string }) {
  const identity = useWorkspaceIdentity()
  const { org, environment } = identity
  const isProduction = environment === "production"

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Organization: ${org}. Switch organization`}
          data-testid="workspace-switcher"
          className={cn(
            "group flex w-full min-w-0 items-center gap-2.5 rounded-[10px] text-left transition-colors",
            "hover:bg-[color:var(--g-chrome-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            collapsed ? "justify-center p-1.5" : "px-2 py-1.5",
            className,
          )}
        >
          <span className="relative shrink-0">
            <OrgMonogram name={org} size="sm" />
            <span
              className={cn(
                "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[color:var(--g-chrome)]",
                isProduction ? "bg-success" : "bg-warning",
              )}
              aria-hidden
            />
          </span>
          {collapsed ? null : (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold leading-tight text-foreground">{org}</span>
                <span className="mt-0.5 flex items-center gap-1 text-[11px] leading-tight text-muted-foreground">
                  <span className="capitalize">{environment}</span>
                  <span aria-hidden>·</span>
                  <span>Workspace</span>
                </span>
              </span>
              <Icon
                name="caretDown"
                size="xs"
                className="shrink-0 text-muted-foreground transition-colors group-hover:text-foreground"
              />
            </>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side={collapsed ? "right" : "bottom"} className="w-60">
        <OrgMenuItems identity={identity} />
        <DropdownMenuSeparator />
        <EnvironmentMenuItems identity={identity} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

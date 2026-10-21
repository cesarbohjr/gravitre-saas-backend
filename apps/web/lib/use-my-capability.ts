"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { ROLE_PERMISSIONS_KEY, type RolePermissionsResponse } from "@/lib/settings-api/roles"

/**
 * Whether the signed-in member's role holds ``capability`` in this workspace
 * (Trust & Safety > Role permissions). Owners and admins hold everything; use
 * this for controls a non-admin role can be granted. The backend enforces the
 * same matrix regardless.
 */
export function useMyCapability(capability: string): boolean {
  const { data } = useSWR<RolePermissionsResponse>(ROLE_PERMISSIONS_KEY, fetcher, { revalidateOnFocus: false })
  return Boolean(data?.my_capabilities?.includes(capability))
}

import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Role Permissions | Gravitre",
  "See what each workspace role can access and manage.",
  { canonical: "/settings/team/permissions" },
)

export default function PermissionsLayout({ children }: { children: React.ReactNode }) {
  return children
}

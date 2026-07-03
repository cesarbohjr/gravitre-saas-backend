import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"
import { SettingsShell } from "@/components/settings/settings-shell"

export const metadata: Metadata = authenticatedMetadata(
  "Settings | Gravitre",
  "Workspace, team, security, and AI settings.",
  { canonical: "/settings" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return <SettingsShell>{children}</SettingsShell>
}

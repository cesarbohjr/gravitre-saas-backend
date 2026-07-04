import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"
import { APP_ROUTES } from "@/lib/app-routes"

export const metadata: Metadata = authenticatedMetadata(
  "Gravitre AI | Workspace",
  "Unified AI workspace for chat, search, and execution.",
  { canonical: APP_ROUTES.gravitreAi },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}

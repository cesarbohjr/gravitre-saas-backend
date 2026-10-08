import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"
import { APP_ROUTES } from "@/lib/app-routes"

export const metadata: Metadata = authenticatedMetadata(
  "Universal Search | Gravitre",
  "Search org knowledge, connectors, and intelligence.",
  { canonical: APP_ROUTES.universalSearch },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}

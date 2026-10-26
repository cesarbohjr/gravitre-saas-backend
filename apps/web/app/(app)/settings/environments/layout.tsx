import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Environments | Gravitre",
  "Where agents and workflows run, from testing to production.",
  { canonical: "/settings/environments" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}

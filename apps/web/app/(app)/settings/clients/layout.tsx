import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Clients | Gravitre",
  "Partner program: add client workspaces, pay wholesale and bill clients your own price.",
  { canonical: "/settings/clients" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}

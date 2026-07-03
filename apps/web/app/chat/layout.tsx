import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Chat | Gravitre",
  "Workspace chat conversations.",
  { canonical: "/chat" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}

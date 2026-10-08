import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Notifications | Gravitre",
  "Notification preferences and history.",
  { canonical: "/notifications" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}

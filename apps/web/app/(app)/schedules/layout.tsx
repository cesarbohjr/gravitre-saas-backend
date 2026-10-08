import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Schedules | Gravitre",
  "Scheduled workflow and automation runs.",
  { canonical: "/schedules" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}

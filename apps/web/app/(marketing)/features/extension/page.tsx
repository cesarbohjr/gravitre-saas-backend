import { marketingMetadata } from "@/lib/seo"
import { ExtensionPage } from "@/components/marketing/features/extension-page"

export const metadata = marketingMetadata({
  title: "Browser extension — Overlay and approve",
  description:
    "Gravitre Chrome extension: enrich LinkedIn, Gmail, Outlook, and company pages, approve governed catalog writes, and see them in Outcomes — same path as chat.",
  ogDescription:
    "Install → connect → enrich → approve → Outcomes. Catalog actions only. No parallel CRM bot.",
})

export default function ExtensionRoute() {
  return <ExtensionPage />
}

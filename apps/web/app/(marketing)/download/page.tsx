import type { Metadata } from "next"
import { DesktopDownloadSection } from "@/components/marketing/desktop-download-section"
import { DESKTOP_RELEASE_MANIFEST } from "@/lib/desktop-release"
import { DivideX } from "@/components/marketing/nodus/divide"
import {
  MarketingPageEndCta,
  MarketingPageHero,
} from "@/components/marketing/nodus/page-shell"

export const metadata: Metadata = {
  title: "Download Gravitre Desktop",
  description:
    "Download Gravitre for Windows, macOS, and Linux — global-shortcut companion for chat, activity, and approvals.",
}

export default function DownloadPage() {
  return (
    <div className="relative overflow-hidden bg-white">
      <MarketingPageHero
        badge="Desktop"
        title="Gravitre for your desktop"
        description="Global-shortcut companion for chat, activity, and approvals — Windows, macOS, and Linux."
      />
      <DivideX />
      <DesktopDownloadSection
        initialManifest={DESKTOP_RELEASE_MANIFEST}
        className="relative overflow-hidden bg-white"
      />
      <MarketingPageEndCta />
    </div>
  )
}

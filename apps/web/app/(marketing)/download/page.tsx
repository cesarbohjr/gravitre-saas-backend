import type { Metadata } from "next"
import { DesktopDownloadSection } from "@/components/marketing/desktop-download-section"
import type { DesktopReleaseManifest } from "@/lib/desktop-release"
import latestManifest from "@/../public/desktop/latest.json"

export const metadata: Metadata = {
  title: "Download Gravitre Desktop",
  description:
    "Download Gravitre for Windows, macOS, and Linux — global-shortcut companion for chat, activity, and approvals.",
}

export default function DownloadPage() {
  const manifest = latestManifest as DesktopReleaseManifest

  return (
    <div className="bg-white pt-16">
      <DesktopDownloadSection initialManifest={manifest} className="relative py-24 sm:py-32 bg-white" />
    </div>
  )
}

import type { Metadata } from "next"
import { DesktopDownloadSection } from "@/components/marketing/desktop-download-section"
import { DESKTOP_RELEASE_MANIFEST } from "@/lib/desktop-release"

export const metadata: Metadata = {
  title: "Download Gravitre Desktop",
  description:
    "Download Gravitre for Windows, macOS, and Linux — global-shortcut companion for chat, activity, and approvals.",
}

export default function DownloadPage() {
  return (
    <div className="bg-white pt-16">
      <DesktopDownloadSection
        initialManifest={DESKTOP_RELEASE_MANIFEST}
        className="relative py-24 sm:py-32 bg-white"
      />
    </div>
  )
}

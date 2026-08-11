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
    <div className="relative overflow-hidden bg-[#F8F7F2]">
      <DesktopDownloadSection
        initialManifest={DESKTOP_RELEASE_MANIFEST}
        className="relative overflow-hidden bg-[#F8F7F2]"
      />
    </div>
  )
}

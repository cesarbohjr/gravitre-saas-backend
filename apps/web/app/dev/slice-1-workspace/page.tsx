import type { Metadata } from "next"
import { Slice1WorkspacePreview } from "./_components/slice-1-workspace-preview"

export const metadata: Metadata = {
  title: "Slice 1 AI workspace (internal) · Gravitre",
  robots: { index: false, follow: false },
}

export default function Slice1WorkspacePage() {
  return <Slice1WorkspacePreview />
}

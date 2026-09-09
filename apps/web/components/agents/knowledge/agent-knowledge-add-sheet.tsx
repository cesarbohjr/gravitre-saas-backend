"use client"

import Link from "next/link"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { FileArrowUp, Books, Sparkle, Plugs, Database } from "@phosphor-icons/react"

export function AgentKnowledgeAddSheet({
  open,
  onOpenChange,
  onBrowseExpertPacks,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onBrowseExpertPacks: () => void
}) {
  const tiles = [
    {
      icon: FileArrowUp,
      title: "Upload files",
      description: "Add documents through the organization knowledge library.",
      href: "/sources",
      supported: true,
    },
    {
      icon: Database,
      title: "Existing library",
      description: "Assign organization sources already indexed in Gravitre.",
      action: () => onOpenChange(false),
      supported: true,
    },
    {
      icon: Sparkle,
      title: "Expert pack",
      description: "Assign platform-curated intelligence without copying content.",
      action: () => {
        onOpenChange(false)
        onBrowseExpertPacks()
      },
      supported: true,
    },
    {
      icon: Plugs,
      title: "Connected app",
      description: "Use connectors that expose a supported ingestion capability.",
      href: "/connectors",
      supported: true,
    },
    {
      icon: Books,
      title: "Write knowledge",
      description: "Native text documents — not yet available in this environment.",
      supported: false,
    },
  ]

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Add knowledge</SheetTitle>
          <SheetDescription>What would you like Gravitre to learn from?</SheetDescription>
        </SheetHeader>
        <div className="mt-4 grid gap-2">
          {tiles.map((tile) => {
            const Icon = tile.icon
            const body = (
              <div
                className={`flex items-start gap-3 rounded-[var(--np-radius-md)] border p-3 text-left transition-colors ${
                  tile.supported
                    ? "border-divide hover:border-[color:var(--g-brand)]/30 hover:bg-[color:var(--g-surface-2)]"
                    : "border-divide/60 opacity-60"
                }`}
              >
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-[color:var(--g-brand)]" weight="duotone" aria-hidden />
                <div>
                  <p className="text-sm font-medium">{tile.title}</p>
                  <p className="text-xs text-[color:var(--g-text-muted)]">{tile.description}</p>
                </div>
              </div>
            )
            if (!tile.supported) {
              return (
                <div key={tile.title} aria-disabled="true">
                  {body}
                </div>
              )
            }
            if (tile.href) {
              return (
                <Link key={tile.title} href={tile.href} onClick={() => onOpenChange(false)}>
                  {body}
                </Link>
              )
            }
            return (
              <button key={tile.title} type="button" className="w-full" onClick={tile.action}>
                {body}
              </button>
            )
          })}
        </div>
        <div className="mt-4">
          <Button type="button" variant="outline" className="w-full" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}

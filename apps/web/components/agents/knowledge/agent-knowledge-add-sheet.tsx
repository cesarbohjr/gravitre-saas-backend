"use client"

import Link from "next/link"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import {
  FileArrowUp,
  Books,
  Sparkle,
  Plugs,
  Database,
} from "@phosphor-icons/react"

export function AgentKnowledgeAddSheet({
  open,
  onOpenChange,
  onBrowseExpertPacks,
  onBrowseSources,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onBrowseExpertPacks: () => void
  onBrowseSources?: () => void
}) {
  const tiles = [
    {
      icon: FileArrowUp,
      title: "Open upload library",
      description: "Add documents through the organization knowledge library.",
      href: "/sources",
      supported: true,
    },
    {
      icon: Database,
      title: "Existing library",
      description: "Assign organization sources already indexed in Gravitre.",
      action: () => {
        onOpenChange(false)
        onBrowseSources?.()
      },
      supported: true,
    },
    {
      icon: Sparkle,
      title: "Expert pack",
      description:
        "Assign platform-curated intelligence without copying content.",
      action: () => {
        onOpenChange(false)
        onBrowseExpertPacks()
      },
      supported: true,
    },
    {
      icon: Plugs,
      title: "Configure a connected app",
      description:
        "Use connectors that expose a supported ingestion capability.",
      href: "/connectors",
      supported: true,
    },
    {
      icon: Books,
      title: "Write knowledge",
      description:
        "Native text documents — not yet available in this environment.",
      supported: false,
    },
  ]

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="max-h-[100dvh] overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Add knowledge</SheetTitle>
          <SheetDescription>
            What would you like Gravitre to learn from?
          </SheetDescription>
        </SheetHeader>
        <div className="mt-4 divide-y divide-[color:var(--g-border-subtle)]">
          {tiles.map((tile) => {
            const Icon = tile.icon
            const body = (
              <div
                className={`flex min-h-16 items-start gap-3 px-3 py-4 text-left transition-colors ${
                  tile.supported
                    ? "hover:bg-[color:var(--g-brand-soft)]"
                    : "text-muted-foreground"
                }`}
              >
                <Icon
                  className="mt-0.5 h-5 w-5 shrink-0 text-[color:var(--g-brand)]"
                  weight="duotone"
                  aria-hidden
                />
                <div>
                  <p className="text-sm font-medium">{tile.title}</p>
                  <p className="text-xs text-[color:var(--g-text-muted)]">
                    {tile.description}
                  </p>
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
                <Link
                  key={tile.title}
                  href={tile.href}
                  onClick={() => onOpenChange(false)}
                >
                  {body}
                </Link>
              )
            }
            return (
              <button
                key={tile.title}
                type="button"
                className="min-h-11 w-full"
                onClick={tile.action}
              >
                {body}
              </button>
            )
          })}
        </div>
        <div className="mt-4">
          <Button
            type="button"
            variant="outline"
            className="min-h-11 w-full"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}

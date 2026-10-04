"use client"

import { useState } from "react"
import Link from "next/link"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
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
  onCreateText,
  creatingText = false,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onBrowseExpertPacks: () => void
  onBrowseSources?: () => void
  onCreateText?: (input: { title: string; text: string }) => Promise<boolean>
  creatingText?: boolean
}) {
  const [mode, setMode] = useState<"choose" | "write">("choose")
  const [title, setTitle] = useState("")
  const [text, setText] = useState("")
  const [error, setError] = useState<string | null>(null)
  function close(next: boolean) {
    if (creatingText) return
    if (!next) {
      setMode("choose")
      setTitle("")
      setText("")
      setError(null)
    }
    onOpenChange(next)
  }
  const tiles = [
    {
      icon: FileArrowUp,
      title: "Open upload library",
      description: "Add documents through the organization knowledge library.",
      href: "/sources",
    },
    {
      icon: Database,
      title: "Existing library",
      description: "Assign organization sources already indexed in Gravitre.",
      action: () => {
        close(false)
        onBrowseSources?.()
      },
    },
    {
      icon: Sparkle,
      title: "Expert pack",
      description:
        "Assign platform-curated intelligence without copying content.",
      action: () => {
        close(false)
        onBrowseExpertPacks()
      },
    },
    {
      icon: Plugs,
      title: "Configure a connected app",
      description:
        "Use connectors that expose a supported ingestion capability.",
      href: "/connectors",
    },
    {
      icon: Books,
      title: "Write knowledge",
      description:
        "Create a native text document, queue ingestion, and assign it to this agent.",
      action: () => {
        setMode("write")
        setError(null)
      },
    },
  ]

  return (
    <Sheet open={open} onOpenChange={close}>
      <SheetContent className="max-h-[100dvh] overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>
            {mode === "write" ? "Write knowledge" : "Add knowledge"}
          </SheetTitle>
          <SheetDescription>
            {mode === "write"
              ? "The text is saved as a manual source and queued for ingestion. Assignment does not mean retrieval is ready."
              : "What would you like Gravitre to learn from?"}
          </SheetDescription>
        </SheetHeader>
        {mode === "write" ? (
          <form
            className="mt-4 space-y-4"
            onSubmit={async (event) => {
              event.preventDefault()
              if (!onCreateText || creatingText) return
              if (!title.trim() || !text.trim()) {
                setError("Enter a title and the knowledge text.")
                return
              }
              setError(null)
              const saved = await onCreateText({ title, text })
              if (saved) close(false)
            }}
          >
            <label className="block space-y-2 text-sm">
              <span className="font-medium">Title</span>
              <Input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                disabled={creatingText}
                className="min-h-11"
              />
            </label>
            <label className="block space-y-2 text-sm">
              <span className="font-medium">Knowledge text</span>
              <Textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                disabled={creatingText}
                rows={8}
              />
            </label>
            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className="min-h-11"
                disabled={creatingText}
                onClick={() => {
                  setMode("choose")
                  setError(null)
                }}
              >
                Back
              </Button>
              <Button type="submit" className="min-h-11" disabled={creatingText}>
                {creatingText ? "Saving…" : "Save and assign"}
              </Button>
            </div>
          </form>
        ) : (
          <div className="mt-4 divide-y divide-[color:var(--g-border-subtle)]">
            {tiles.map((tile) => {
              const Icon = tile.icon
              const body = (
                <div className="flex min-h-16 items-start gap-3 px-3 py-4 text-left transition-colors hover:bg-[color:var(--g-brand-soft)]">
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
              if (tile.href) {
                return (
                  <Link
                    key={tile.title}
                    href={tile.href}
                    onClick={() => close(false)}
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
        )}
        {mode === "choose" ? (
          <div className="mt-4">
            <Button
              type="button"
              variant="outline"
              className="min-h-11 w-full"
              onClick={() => close(false)}
            >
              Cancel
            </Button>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}

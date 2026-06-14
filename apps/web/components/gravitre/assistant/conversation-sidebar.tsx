"use client"

import { useMemo, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import {
  Archive,
  Check,
  CheckCheck,
  ListChecks,
  MessageCircle,
  MessageSquarePlus,
  MoreHorizontal,
  Pencil,
  Search,
  Share2,
  Trash2,
  X,
  PanelLeft,
  PanelLeftClose,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { Conversation } from "@/types/api"

function groupConversationsByDate(conversations: Conversation[]) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)
  const lastMonth = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000)

  const groups: { label: string; conversations: Conversation[] }[] = [
    { label: "Today", conversations: [] },
    { label: "Yesterday", conversations: [] },
    { label: "Previous 7 days", conversations: [] },
    { label: "Previous 30 days", conversations: [] },
    { label: "Older", conversations: [] },
  ]

  for (const conv of conversations) {
    const date = new Date(conv.updated_at)
    if (date >= today) groups[0].conversations.push(conv)
    else if (date >= yesterday) groups[1].conversations.push(conv)
    else if (date >= lastWeek) groups[2].conversations.push(conv)
    else if (date >= lastMonth) groups[3].conversations.push(conv)
    else groups[4].conversations.push(conv)
  }

  return groups.filter((g) => g.conversations.length > 0)
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return "now"
  if (diffMins < 60) return `${diffMins}m`
  if (diffHours < 24) return `${diffHours}h`
  if (diffDays < 7) return `${diffDays}d`
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelect,
  onNew,
  onDelete,
  onArchive,
  onRename,
  onBulkDelete,
  isOpen,
  onToggle,
}: {
  conversations: Conversation[]
  activeConversationId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void | Promise<void>
  onArchive: (id: string) => void
  onRename: (id: string, title: string) => void
  onBulkDelete: (ids: string[]) => void | Promise<void>
  isOpen: boolean
  onToggle: () => void
}) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [selectionMode, setSelectionMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isBulkDeleting, setIsBulkDeleting] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState("")
  const { reduced } = useMotionPrefs()

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return conversations
    return conversations.filter((c) => (c.title || "").toLowerCase().includes(q))
  }, [conversations, searchQuery])

  const grouped = useMemo(() => groupConversationsByDate(filtered), [filtered])

  const allSelected = filtered.length > 0 && selectedIds.size === filtered.length

  const enterSelection = () => {
    setSelectionMode(true)
    setSearchOpen(false)
  }

  const exitSelection = () => {
    setSelectionMode(false)
    setSelectedIds(new Set())
  }

  const toggleSelected = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    setSelectedIds((prev) => (prev.size === filtered.length ? new Set() : new Set(filtered.map((c) => c.id))))
  }

  const handleRowClick = (id: string) => {
    if (renamingId) return
    if (selectionMode) {
      toggleSelected(id)
      return
    }
    onSelect(id)
  }

  const confirmDelete = async () => {
    if (!conversationToDelete || isDeleting) return
    setIsDeleting(true)
    try {
      await onDelete(conversationToDelete)
    } finally {
      setIsDeleting(false)
      setConversationToDelete(null)
      setDeleteDialogOpen(false)
    }
  }

  const confirmBulkDelete = async () => {
    if (isBulkDeleting || selectedIds.size === 0) return
    setIsBulkDeleting(true)
    try {
      await onBulkDelete(Array.from(selectedIds))
      exitSelection()
      setBulkDeleteOpen(false)
    } finally {
      setIsBulkDeleting(false)
    }
  }

  const archiveSelected = () => {
    selectedIds.forEach((id) => onArchive(id))
    exitSelection()
  }

  const shareLink = (id: string) => {
    const url = `${window.location.origin}/assistant?c=${id}`
    void navigator.clipboard.writeText(url)
  }

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={onToggle}
        className="fixed top-20 left-4 z-40 md:hidden h-9 w-9 bg-white shadow-md border border-zinc-200"
      >
        {isOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
      </Button>

      {isOpen && <div className="fixed inset-0 z-30 bg-black/40 md:hidden backdrop-blur-sm" onClick={onToggle} />}

      <aside
        className={cn(
          "fixed md:static inset-y-0 left-0 z-40 w-72 flex flex-col bg-zinc-50/80 border-r border-zinc-200 transition-all duration-300",
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0 md:w-0 md:border-0 md:overflow-hidden",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between h-14 px-3 border-b border-zinc-200 bg-white gap-2">
          {selectionMode ? (
            <TooltipProvider delayDuration={300}>
              <div className="flex items-center gap-1 flex-1">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-zinc-500" onClick={exitSelection}>
                      <X className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">Cancel</TooltipContent>
                </Tooltip>
                <span className="text-sm font-medium text-zinc-900 tabular-nums">
                  {selectedIds.size > 0 ? `${selectedIds.size} selected` : "Select items"}
                </span>
                <div className="ml-auto flex items-center gap-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-zinc-500" onClick={toggleSelectAll}>
                        {allSelected ? <CheckCheck className="h-4 w-4 text-emerald-600" /> : <ListChecks className="h-4 w-4" />}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">{allSelected ? "Clear selection" : "Select all"}</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-zinc-500 disabled:opacity-40"
                        disabled={selectedIds.size === 0}
                        onClick={archiveSelected}
                      >
                        <Archive className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">Archive</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50 disabled:opacity-40"
                        disabled={selectedIds.size === 0}
                        onClick={() => setBulkDeleteOpen(true)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">Delete</TooltipContent>
                  </Tooltip>
                </div>
              </div>
            </TooltipProvider>
          ) : (
            <TooltipProvider delayDuration={300}>
              <span className="text-sm font-semibold text-zinc-900 pl-1">History</span>
              <div className="flex items-center gap-0.5">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-zinc-500" onClick={() => setSearchOpen((v) => !v)}>
                      <Search className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">Search</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-zinc-500 disabled:opacity-40"
                      disabled={conversations.length === 0}
                      onClick={enterSelection}
                    >
                      <ListChecks className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">Select</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-zinc-500" onClick={onNew}>
                      <MessageSquarePlus className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">New conversation</TooltipContent>
                </Tooltip>
              </div>
            </TooltipProvider>
          )}
        </div>

        {/* Search */}
        {searchOpen && !selectionMode && (
          <div className="px-3 py-2 border-b border-zinc-200 bg-white">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-400" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search conversations..."
                className="h-8 pl-8 pr-8 text-xs"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    setSearchQuery("")
                    setSearchOpen(false)
                  }
                }}
              />
              <button
                className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600"
                onClick={() => {
                  setSearchQuery("")
                  setSearchOpen(false)
                }}
                aria-label="Close search"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* List */}
        <ScrollArea className="flex-1">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <div className="h-12 w-12 rounded-full bg-zinc-200/70 flex items-center justify-center mb-4">
                <MessageCircle className="h-5 w-5 text-zinc-400" />
              </div>
              <p className="text-sm font-medium text-zinc-600 mb-1">
                {searchQuery ? `No matches for "${searchQuery}"` : "No conversations yet"}
              </p>
              {!searchQuery && <p className="text-xs text-zinc-400">Start a new chat to begin</p>}
            </div>
          ) : (
            <div className="py-2">
              {grouped.map((group) => (
                <div key={group.label} className="mb-2">
                  <div className="px-4 pb-1 pt-2">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                      {group.label}
                    </span>
                  </div>
                  <div className="px-2">
                    <AnimatePresence initial={false}>
                      {group.conversations.map((conv) => {
                        const isActive = activeConversationId === conv.id
                        const isSelected = selectedIds.has(conv.id)
                        const isRenaming = renamingId === conv.id
                        return (
                          <motion.div
                            key={conv.id}
                            layout={!reduced}
                            initial={reduced ? { opacity: 0 } : { opacity: 0, x: -12 }}
                            animate={reduced ? { opacity: 1 } : { opacity: 1, x: 0 }}
                            exit={reduced ? { opacity: 0 } : { opacity: 0, x: -12, height: 0 }}
                            transition={{ type: "spring", stiffness: 420, damping: 34 }}
                            className={cn(
                              "relative group flex items-center gap-2.5 rounded-lg px-2.5 py-2 cursor-pointer transition-colors",
                              isActive && !selectionMode
                                ? "bg-emerald-50 text-emerald-900"
                                : isSelected
                                  ? "bg-emerald-50/70"
                                  : "hover:bg-zinc-100",
                            )}
                            onClick={() => handleRowClick(conv.id)}
                            onContextMenu={(e) => e.preventDefault()}
                          >
                            {isActive && !selectionMode && (
                              <motion.span
                                layoutId="conversation-active-rail"
                                className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-emerald-500"
                                transition={{ type: "spring", stiffness: 500, damping: 40 }}
                              />
                            )}

                            {/* Leading: checkbox in selection mode, chat glyph otherwise */}
                            {selectionMode ? (
                              <span
                                className={cn(
                                  "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
                                  isSelected ? "border-emerald-600 bg-emerald-600 text-white" : "border-zinc-300 bg-white",
                                )}
                                aria-hidden
                              >
                                {isSelected && <Check className="h-3 w-3" strokeWidth={3} />}
                              </span>
                            ) : (
                              <MessageCircle
                                className={cn(
                                  "h-4 w-4 shrink-0",
                                  isActive ? "text-emerald-500" : "text-zinc-400",
                                )}
                              />
                            )}

                            <div className="flex-1 min-w-0">
                              {isRenaming ? (
                                <Input
                                  value={renameValue}
                                  onChange={(e) => setRenameValue(e.target.value)}
                                  className="h-7 text-xs"
                                  autoFocus
                                  onClick={(e) => e.stopPropagation()}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") {
                                      onRename(conv.id, renameValue.trim() || conv.title)
                                      setRenamingId(null)
                                    }
                                    if (e.key === "Escape") setRenamingId(null)
                                  }}
                                  onBlur={() => {
                                    if (renameValue.trim()) onRename(conv.id, renameValue.trim())
                                    setRenamingId(null)
                                  }}
                                />
                              ) : (
                                <>
                                  <p
                                    className={cn(
                                      "text-sm truncate leading-tight",
                                      isActive && !selectionMode ? "text-emerald-700 font-medium" : "text-zinc-700",
                                    )}
                                  >
                                    {conv.title || "New conversation"}
                                  </p>
                                  <p className="text-[10px] text-zinc-400 mt-0.5">{formatRelativeTime(conv.updated_at)}</p>
                                </>
                              )}
                            </div>

                            {/* Trailing actions (hidden in selection mode) */}
                            {!selectionMode && !isRenaming && (
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <button
                                    onClick={(e) => e.stopPropagation()}
                                    className="opacity-0 group-hover:opacity-100 focus:opacity-100 data-[state=open]:opacity-100 p-1.5 rounded-md hover:bg-zinc-200 text-zinc-400 hover:text-zinc-600 transition-colors shrink-0"
                                    aria-label="Conversation options"
                                  >
                                    <MoreHorizontal className="h-4 w-4" />
                                  </button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-44">
                                  <DropdownMenuItem
                                    onClick={() => {
                                      setRenamingId(conv.id)
                                      setRenameValue(conv.title || "")
                                    }}
                                  >
                                    <Pencil className="h-3.5 w-3.5 mr-2" /> Rename
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => onArchive(conv.id)}>
                                    <Archive className="h-3.5 w-3.5 mr-2" /> Archive
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => shareLink(conv.id)}>
                                    <Share2 className="h-3.5 w-3.5 mr-2" /> Copy link
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem
                                    className="text-red-600 focus:text-red-600 focus:bg-red-50"
                                    onClick={() => {
                                      setConversationToDelete(conv.id)
                                      setDeleteDialogOpen(true)
                                    }}
                                  >
                                    <Trash2 className="h-3.5 w-3.5 mr-2" /> Delete
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            )}
                          </motion.div>
                        )
                      })}
                    </AnimatePresence>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </aside>

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the conversation and its messages. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault()
                void confirmDelete()
              }}
              disabled={isDeleting}
              className="bg-red-500 hover:bg-red-600"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selectedIds.size} conversation{selectedIds.size === 1 ? "" : "s"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              The selected conversations and their messages will be permanently removed. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isBulkDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault()
                void confirmBulkDelete()
              }}
              disabled={isBulkDeleting}
              className="bg-red-500 hover:bg-red-600"
            >
              {isBulkDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

"use client"

import { useMemo, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import {
  Archive,
  Check,
  CheckCheck,
  Filter,
  ListChecks,
  MessageCircle,
  MessageSquarePlus,
  MoreHorizontal,
  Pencil,
  Search,
  Share2,
  Trash2,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
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

type HistoryDateFilter = "all" | "today" | "week" | "archived"

const DATE_FILTER_OPTIONS: { value: HistoryDateFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "today", label: "Today" },
  { value: "week", label: "This week" },
  { value: "archived", label: "Archived" },
]

function isConversationArchived(conversation: Conversation): boolean {
  return Boolean(conversation.archived_at)
}

function matchesHistoryDateFilter(conversation: Conversation, filter: HistoryDateFilter): boolean {
  const archived = isConversationArchived(conversation)
  if (filter === "archived") return archived
  if (archived) return false

  const updated = new Date(conversation.updated_at)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfWeek = new Date(startOfToday.getTime() - 7 * 24 * 60 * 60 * 1000)

  if (filter === "today") return updated >= startOfToday
  if (filter === "week") return updated >= startOfWeek
  return true
}

function emptyHistoryMessage(filter: HistoryDateFilter, searchQuery: string): string {
  if (searchQuery.trim()) return `No matches for "${searchQuery.trim()}"`
  if (filter === "archived") return "No archived conversations"
  if (filter === "today") return "No conversations from today"
  if (filter === "week") return "No conversations this week"
  return "No conversations yet"
}

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

function ConversationListSkeleton() {
  return (
    <div className="space-y-1 px-2 py-3">
      {Array.from({ length: 7 }).map((_, index) => (
        <div key={index} className="flex items-center gap-2.5 rounded-lg px-2.5 py-2">
          <Skeleton className="h-4 w-4 shrink-0 rounded-full" />
          <div className="min-w-0 flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-4/5" />
            <Skeleton className="h-2.5 w-12" />
          </div>
        </div>
      ))}
    </div>
  )
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
  isLoading = false,
  loadError,
  onRetry,
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
  isLoading?: boolean
  loadError?: unknown
  onRetry?: () => void
}) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [dateFilter, setDateFilter] = useState<HistoryDateFilter>("all")
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
    return conversations.filter((conversation) => {
      if (!matchesHistoryDateFilter(conversation, dateFilter)) return false
      if (!q) return true
      return (conversation.title || "").toLowerCase().includes(q)
    })
  }, [conversations, searchQuery, dateFilter])

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
    const url = `${window.location.origin}/ai?c=${id}`
    void navigator.clipboard.writeText(url)
  }

  return (
    <>
      {/* Mobile-only scrim. The single open/close toggle lives in the chat
          header; tapping the scrim or the in-sidebar close button dismisses it. */}
      {isOpen && <div className="fixed inset-0 z-30 bg-black/40 md:hidden backdrop-blur-sm" onClick={onToggle} />}

      <aside
        className={cn(
          "fixed md:static inset-y-0 left-0 z-50 w-72 flex flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-all duration-300",
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0 md:w-0 md:border-0 md:overflow-hidden",
        )}
      >
        {/* Header */}
        <div className="flex h-14 items-center justify-between gap-2 border-b border-sidebar-border bg-sidebar px-3">
          {selectionMode ? (
            <TooltipProvider delayDuration={300}>
              <div className="flex items-center gap-1 flex-1">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground" onClick={exitSelection}>
                      <X className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">Cancel</TooltipContent>
                </Tooltip>
                <span className="pl-1 text-sm font-medium tabular-nums text-sidebar-foreground">
                  {selectedIds.size > 0 ? `${selectedIds.size} selected` : "Select items"}
                </span>
                <div className="ml-auto flex items-center gap-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground" onClick={toggleSelectAll}>
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
                        className="h-8 w-8 text-muted-foreground disabled:opacity-40"
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
                        className="h-8 w-8 text-red-500 hover:bg-destructive/10 hover:text-red-600 disabled:opacity-40 dark:hover:text-red-400"
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
              <span className="pl-1 text-sm font-semibold text-sidebar-foreground">History</span>
              <div className="flex items-center gap-0.5">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground" onClick={() => setSearchOpen((v) => !v)}>
                      <Search className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">Search</TooltipContent>
                </Tooltip>
                <DropdownMenu>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className={cn(
                            "h-8 w-8",
                            dateFilter === "all" ? "text-muted-foreground" : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
                          )}
                          aria-label="Filter conversations by date"
                        >
                          <Filter className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">Filter</TooltipContent>
                  </Tooltip>
                  <DropdownMenuContent align="end" className="w-40">
                    {DATE_FILTER_OPTIONS.map((option) => (
                      <DropdownMenuItem
                        key={option.value}
                        onClick={() => setDateFilter(option.value)}
                        className="flex items-center justify-between"
                      >
                        <span>{option.label}</span>
                        {dateFilter === option.value && (
                          <Check className="h-3.5 w-3.5 text-emerald-600" />
                        )}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground disabled:opacity-40"
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
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground" onClick={onNew}>
                      <MessageSquarePlus className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">New conversation</TooltipContent>
                </Tooltip>
                {/* Explicit close affordance on mobile (sidebar is an overlay there) */}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground md:hidden"
                  onClick={onToggle}
                  aria-label="Close conversation history"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </TooltipProvider>
          )}
        </div>

        {/* Search */}
        {searchOpen && !selectionMode && (
          <div className="border-b border-sidebar-border bg-sidebar px-3 py-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
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
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
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

        {dateFilter !== "all" && !selectionMode && (
          <div className="flex items-center justify-between border-b border-sidebar-border bg-sidebar px-3 py-2">
            <span className="text-[11px] font-medium text-muted-foreground">
              {DATE_FILTER_OPTIONS.find((option) => option.value === dateFilter)?.label}
            </span>
            <button
              type="button"
              className="text-[11px] text-muted-foreground transition-colors hover:text-foreground"
              onClick={() => setDateFilter("all")}
            >
              Clear
            </button>
          </div>
        )}

        {/* List */}
        <ScrollArea className="flex-1">
          {isLoading ? (
            <ConversationListSkeleton />
          ) : loadError ? (
            <WorkSectionErrorCard
              title="Couldn't load history"
              message="We couldn't fetch your conversations. Check your connection and try again."
              error={loadError}
              onRetry={onRetry}
              className="mx-3 my-6 border-destructive/30 bg-destructive/10"
            />
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <MessageCircle className="h-5 w-5 text-muted-foreground" />
              </div>
              <p className="mb-1 text-sm font-medium text-foreground">
                {emptyHistoryMessage(dateFilter, searchQuery)}
              </p>
              {!searchQuery && dateFilter === "all" && (
                <p className="text-xs text-muted-foreground">Start a new chat to begin</p>
              )}
            </div>
          ) : (
            <div className="py-2">
              {grouped.map((group) => (
                <div key={group.label} className="mb-2">
                  <div className="px-4 pb-1 pt-2">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
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
                              "relative group flex items-center gap-2 rounded-lg px-2.5 py-2 cursor-pointer transition-colors min-w-0",
                              isActive && !selectionMode
                                ? "bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
                                : isSelected
                                  ? "bg-emerald-500/10"
                                  : "hover:bg-sidebar-accent",
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
                                  isSelected ? "border-emerald-600 bg-emerald-600 text-white" : "border-border bg-background",
                                )}
                                aria-hidden
                              >
                                {isSelected && <Check className="h-3 w-3" strokeWidth={3} />}
                              </span>
                            ) : (
                              <MessageCircle
                                className={cn(
                                  "h-4 w-4 shrink-0",
                                  isActive ? "text-emerald-500" : "text-muted-foreground",
                                )}
                              />
                            )}

                            <div className="min-w-0 flex-1 overflow-hidden pr-1">
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
                                <div className="flex min-w-0 items-center gap-2">
                                  <p
                                    title={conv.title || "New conversation"}
                                    className={cn(
                                      "min-w-0 flex-1 truncate text-sm leading-snug",
                                      isActive && !selectionMode
                                        ? "font-medium text-emerald-700 dark:text-emerald-300"
                                        : "text-sidebar-foreground",
                                    )}
                                  >
                                    {conv.title || "New conversation"}
                                  </p>
                                  <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
                                    {formatRelativeTime(conv.updated_at)}
                                  </span>
                                </div>
                              )}
                            </div>

                            {/* Trailing actions (hidden in selection mode) */}
                            {!selectionMode && !isRenaming && (
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <button
                                    onClick={(e) => e.stopPropagation()}
                                    className="shrink-0 rounded-md p-1.5 text-muted-foreground opacity-0 transition-colors hover:bg-sidebar-accent hover:text-foreground focus:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100"
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
                                    className="text-red-600 focus:bg-destructive/10 focus:text-red-600 dark:text-red-400 dark:focus:text-red-400"
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

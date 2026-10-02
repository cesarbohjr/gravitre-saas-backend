"use client"

import { useMemo, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import {
  Archive,
  ArchiveRestore,
  ArrowDownUp,
  Check,
  Filter,
  MessageCircle,
  MessageSquarePlus,
  MoreHorizontal,
  Pencil,
  Pin,
  PinOff,
  Search,
  Share2,
  Trash2,
  X,
} from "lucide-react"
import { toast } from "sonner"
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
import { groupConversationsByRecency } from "@/lib/conversation-history-groups"
import {
  HISTORY_DATE_FILTER_OPTIONS,
  HISTORY_SORT_OPTIONS,
  emptyHistoryMessage,
  isConversationArchived,
  matchesHistoryDateFilter,
  readStoredHistoryDateFilter,
  readStoredHistorySort,
  sortConversations,
  writeStoredHistoryDateFilter,
  writeStoredHistorySort,
  type HistoryDateFilter,
  type HistorySort,
} from "@/lib/conversation-history-controls"

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
  onUnarchive,
  onPin,
  onUnpin,
  onRename,
  onBulkDelete,
  isOpen,
  onToggle,
  isLoading = false,
  loadError,
  onRetry,
  searchQuery = "",
  onSearchQueryChange,
}: {
  conversations: Conversation[]
  activeConversationId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void | Promise<void>
  onArchive: (id: string) => void
  onUnarchive?: (id: string) => void
  onPin?: (id: string) => void
  onUnpin?: (id: string) => void
  onRename: (id: string, title: string) => void
  onBulkDelete: (ids: string[]) => void | Promise<void>
  isOpen: boolean
  onToggle: () => void
  isLoading?: boolean
  loadError?: unknown
  onRetry?: () => void
  searchQuery?: string
  onSearchQueryChange?: (query: string) => void
}) {
  const [searchOpen, setSearchOpen] = useState(Boolean(searchQuery.trim()))
  const [localSearchQuery, setLocalSearchQuery] = useState(searchQuery)
  const [dateFilter, setDateFilter] = useState<HistoryDateFilter>(readStoredHistoryDateFilter)
  const [sort, setSort] = useState<HistorySort>(readStoredHistorySort)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isBulkDeleting, setIsBulkDeleting] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState("")
  const { reduced } = useMotionPrefs()

  const activeSearch = onSearchQueryChange ? searchQuery : localSearchQuery
  const setActiveSearch = (value: string) => {
    if (onSearchQueryChange) onSearchQueryChange(value)
    else setLocalSearchQuery(value)
  }

  // Date/archive filters stay client-side; title+content search is server-driven when wired.
  const filtered = useMemo(() => {
    const q = onSearchQueryChange ? "" : activeSearch.trim().toLowerCase()
    const rows = conversations.filter((conversation) => {
      if (!matchesHistoryDateFilter(conversation, dateFilter)) return false
      if (!q) return true
      return (
        (conversation.title || "").toLowerCase().includes(q) ||
        (conversation.preview || "").toLowerCase().includes(q)
      )
    })
    return sortConversations(rows, sort)
  }, [conversations, activeSearch, dateFilter, onSearchQueryChange, sort])

  const grouped = useMemo(() => groupConversationsByRecency(filtered), [filtered])

  const allSelected = filtered.length > 0 && selectedIds.size === filtered.length
  const bulkOpen = selectedIds.size > 0

  const clearSelection = () => {
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
    onSelect(id)
  }

  const confirmDelete = async () => {
    if (!conversationToDelete || isDeleting) return
    setIsDeleting(true)
    try {
      await onDelete(conversationToDelete)
      setSelectedIds((prev) => {
        const next = new Set(prev)
        next.delete(conversationToDelete)
        return next
      })
      setDeleteDialogOpen(false)
      setConversationToDelete(null)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete conversation")
    } finally {
      setIsDeleting(false)
    }
  }

  const confirmBulkDelete = async () => {
    if (isBulkDeleting || selectedIds.size === 0) return
    setIsBulkDeleting(true)
    try {
      await onBulkDelete(Array.from(selectedIds))
      clearSelection()
      setBulkDeleteOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete conversations")
    } finally {
      setIsBulkDeleting(false)
    }
  }

  const archiveSelected = () => {
    selectedIds.forEach((id) => onArchive(id))
    clearSelection()
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
        aria-hidden={!isOpen}
        className={cn(
          // Keep closed panels fully inert: a prior regression left a ghost
          // "Select items" drawer visible when the Activity rail opened because
          // closed state only used w-0/translate without opacity/pointer-events.
          "fixed inset-y-0 left-0 z-50 flex h-full w-72 min-h-0 min-w-0 flex-col isolate overflow-hidden border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width,transform,opacity,border-color] duration-300 ease-in-out md:static",
          isOpen
            ? "translate-x-0 opacity-100"
            : "-translate-x-full max-md:pointer-events-none opacity-100 md:translate-x-0 md:w-0 md:max-w-0 md:border-0 md:opacity-0 md:pointer-events-none",
        )}
      >
        {/* Header */}
        <div className="flex min-h-14 flex-col justify-center gap-2 border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-3 py-2">
          <TooltipProvider delayDuration={300}>
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-sm font-semibold text-[color:var(--g-text-primary)]">History</span>
              <div className="flex shrink-0 items-center gap-0.5">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-9 w-9 text-[color:var(--g-text-muted)]" onClick={onNew} aria-label="New conversation">
                      <MessageSquarePlus className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">New conversation</TooltipContent>
                </Tooltip>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 text-[color:var(--g-text-muted)] md:hidden"
                  onClick={onToggle}
                  aria-label="Close conversation history"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                {filtered.length > 0 ? (
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={allSelected}
                    aria-label={allSelected ? "Clear selection" : "Select all conversations"}
                    className={cn(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)]",
                      allSelected && "border-[color:var(--g-brand)] bg-[color:var(--g-brand)] text-white",
                    )}
                    onClick={toggleSelectAll}
                  >
                    {allSelected ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : null}
                  </button>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-0.5">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-9 w-9 text-[color:var(--g-text-muted)]" onClick={() => setSearchOpen((v) => !v)} aria-label="Search conversations">
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
                            "h-9 w-9",
                            dateFilter === "all" ? "text-[color:var(--g-text-muted)]" : "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
                          )}
                          aria-label="Filter conversations"
                        >
                          <Filter className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">Filter</TooltipContent>
                  </Tooltip>
                  <DropdownMenuContent align="end" className="w-40">
                    {HISTORY_DATE_FILTER_OPTIONS.map((option) => (
                      <DropdownMenuItem
                        key={option.value}
                        onClick={() => {
                          setDateFilter(option.value)
                          writeStoredHistoryDateFilter(option.value)
                        }}
                        className="flex items-center justify-between"
                      >
                        <span>{option.label}</span>
                        {dateFilter === option.value && (
                          <Check className="h-3.5 w-3.5 text-[color:var(--g-brand)]" />
                        )}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                <DropdownMenu>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className={cn(
                            "h-9 w-9",
                            sort === "newest" ? "text-[color:var(--g-text-muted)]" : "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
                          )}
                          aria-label="Sort conversations"
                        >
                          <ArrowDownUp className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">Sort</TooltipContent>
                  </Tooltip>
                  <DropdownMenuContent align="end" className="w-40">
                    {HISTORY_SORT_OPTIONS.map((option) => (
                      <DropdownMenuItem
                        key={option.value}
                        onClick={() => {
                          setSort(option.value)
                          writeStoredHistorySort(option.value)
                        }}
                        className="flex items-center justify-between"
                      >
                        <span>{option.label}</span>
                        {sort === option.value && (
                          <Check className="h-3.5 w-3.5 text-[color:var(--g-brand)]" />
                        )}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </TooltipProvider>
        </div>

        {bulkOpen ? (
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] px-3 py-2">
            <span className="text-xs font-medium tabular-nums text-[color:var(--g-text-primary)]">
              {selectedIds.size} selected
            </span>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" className="h-9" onClick={archiveSelected}>
                Archive
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-9 text-destructive"
                onClick={() => setBulkDeleteOpen(true)}
              >
                Delete
              </Button>
              <Button variant="ghost" size="sm" className="h-9" onClick={clearSelection}>
                Clear
              </Button>
            </div>
          </div>
        ) : null}

        {/* Search */}
        {searchOpen && (
          <div className="border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-3 py-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={activeSearch}
                onChange={(e) => setActiveSearch(e.target.value)}
                placeholder="Search titles and messages..."
                className="h-8 pl-8 pr-8 text-xs"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    setActiveSearch("")
                    setSearchOpen(false)
                  }
                }}
              />
              <button
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={() => {
                  setActiveSearch("")
                  setSearchOpen(false)
                }}
                aria-label="Close search"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}

        {dateFilter !== "all" && (
          <div className="flex items-center justify-between border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-3 py-2">
            <span className="text-[11px] font-medium text-[color:var(--g-text-muted)]">
              {HISTORY_DATE_FILTER_OPTIONS.find((option) => option.value === dateFilter)?.label}
            </span>
            <button
              type="button"
              className="text-[11px] text-muted-foreground transition-colors hover:text-foreground"
              onClick={() => {
                setDateFilter("all")
                writeStoredHistoryDateFilter("all")
              }}
            >
              Clear
            </button>
          </div>
        )}

        {/* List — viewport child must be block (not Radix table) so short lists
            stay top-aligned under bucket labels instead of looking clipped. */}
        <ScrollArea className="min-h-0 flex-1 overflow-hidden [&_[data-slot=scroll-area-viewport]>div]:!block [&_[data-slot=scroll-area-viewport]>div]:!min-h-0">
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
                {emptyHistoryMessage(dateFilter, activeSearch)}
              </p>
              {!activeSearch && dateFilter === "all" && (
                <p className="text-xs text-muted-foreground">Start a new chat to begin</p>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-3 py-3">
              {grouped.map((group) => (
                <div key={group.label} className="mb-2">
                  <div className="flex items-center gap-2 px-4 pb-1 pt-2">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {group.label}
                    </span>
                    <span className="rounded-full bg-muted px-1.5 py-px text-[10px] font-medium tabular-nums leading-none text-muted-foreground">
                      {group.conversations.length}
                    </span>
                    <span className="h-px flex-1 bg-border/60" aria-hidden />
                  </div>
                  <div className="flex flex-col gap-0.5 px-2">
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
                              "relative group flex min-w-0 cursor-pointer items-center gap-2 overflow-hidden rounded-[var(--np-radius-md)] px-2 py-1.5 transition-colors",
                              isActive
                                ? "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-primary)]"
                                : isSelected
                                  ? "bg-[color:var(--g-brand-soft)]"
                                  : "hover:bg-[color:var(--g-surface-2)]",
                            )}
                            onClick={() => handleRowClick(conv.id)}
                            onContextMenu={(e) => e.preventDefault()}
                          >
                            {isActive && (
                              <motion.span
                                layoutId="conversation-active-rail"
                                className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-[color:var(--g-brand)]"
                                transition={{ type: "spring", stiffness: 500, damping: 40 }}
                              />
                            )}

                            <button
                              type="button"
                              role="checkbox"
                              aria-checked={isSelected}
                              aria-label={isSelected ? "Deselect conversation" : "Select conversation"}
                              className={cn(
                                "flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)]",
                                isSelected && "border-[color:var(--g-brand)] bg-[color:var(--g-brand)] text-white",
                              )}
                              onClick={(e) => {
                                e.stopPropagation()
                                toggleSelected(conv.id)
                              }}
                            >
                              {isSelected ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : null}
                            </button>

                            {!isSelected && conv.pinned_at ? (
                              <Pin className="h-4 w-4 shrink-0 text-[color:var(--g-brand)]" />
                            ) : null}

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
                                      "min-w-0 flex-1 truncate text-sm leading-snug text-sidebar-foreground",
                                      isActive && "font-medium",
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
                            {!isRenaming && (
                              <DropdownMenu modal={false}>
                                <DropdownMenuTrigger asChild>
                                  <button
                                    onClick={(e) => e.stopPropagation()}
                                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-100 hover:bg-sidebar-accent hover:text-foreground md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100 data-[state=open]:opacity-100"
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
                                  {conv.pinned_at
                                    ? onUnpin && (
                                        <DropdownMenuItem onClick={() => onUnpin(conv.id)}>
                                          <PinOff className="h-3.5 w-3.5 mr-2" /> Unpin
                                        </DropdownMenuItem>
                                      )
                                    : onPin && (
                                        <DropdownMenuItem onClick={() => onPin(conv.id)}>
                                          <Pin className="h-3.5 w-3.5 mr-2" /> Pin
                                        </DropdownMenuItem>
                                      )}
                                  {isConversationArchived(conv)
                                    ? onUnarchive && (
                                        <DropdownMenuItem onClick={() => onUnarchive(conv.id)}>
                                          <ArchiveRestore className="h-3.5 w-3.5 mr-2" /> Unarchive
                                        </DropdownMenuItem>
                                      )
                                    : (
                                        <DropdownMenuItem onClick={() => onArchive(conv.id)}>
                                          <Archive className="h-3.5 w-3.5 mr-2" /> Archive
                                        </DropdownMenuItem>
                                      )}
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

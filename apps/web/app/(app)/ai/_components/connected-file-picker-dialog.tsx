"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Folder,
  Loader2,
  Search,
} from "lucide-react"
import { toast } from "sonner"

import {
  browseConnectedFiles,
  listConnectedFileVendors,
  type ConnectedFileAttachment,
  type ConnectedFileBrowseEntry,
  type ConnectedFileVendor,
} from "@/lib/connected-files-api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

const MAX_ATTACH = 5

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  selected: ConnectedFileAttachment[]
  onConfirm: (files: ConnectedFileAttachment[]) => void
}

type Crumb = { id: string | null; name: string }

function formatModified(value?: string | null): string {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

export function ConnectedFilePickerDialog({ open, onOpenChange, selected, onConfirm }: Props) {
  const [vendors, setVendors] = useState<ConnectedFileVendor[]>([])
  const [vendorsLoading, setVendorsLoading] = useState(false)
  const [storageNote, setStorageNote] = useState("")
  const [activeVendor, setActiveVendor] = useState<ConnectedFileVendor | null>(null)
  const [entries, setEntries] = useState<ConnectedFileBrowseEntry[]>([])
  const [browseLoading, setBrowseLoading] = useState(false)
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [crumbs, setCrumbs] = useState<Crumb[]>([{ id: null, name: "Root" }])
  const [pending, setPending] = useState<ConnectedFileAttachment[]>([])

  const folderCapable = useMemo(
    () => activeVendor?.vendor === "google_drive" || activeVendor?.vendor === "microsoft365",
    [activeVendor],
  )

  const currentFolderId = crumbs.length > 1 ? crumbs[crumbs.length - 1]?.id : null

  useEffect(() => {
    if (!open) return
    setPending(selected.slice(0, MAX_ATTACH))
    setSearch("")
    setDebouncedSearch("")
    setCrumbs([{ id: null, name: "Root" }])
  }, [open, selected])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setVendorsLoading(true)
    void listConnectedFileVendors()
      .then((data) => {
        if (cancelled) return
        setVendors(data.vendors ?? [])
        setStorageNote(data.storage_note ?? "")
        if (data.vendors?.length === 1) {
          setActiveVendor(data.vendors[0]!)
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) toast.error(error instanceof Error ? error.message : "Could not load integrations")
      })
      .finally(() => {
        if (!cancelled) setVendorsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const loadBrowse = useCallback(async () => {
    if (!activeVendor) return
    setBrowseLoading(true)
    try {
      const data = await browseConnectedFiles({
        vendor: activeVendor.vendor,
        connector_id: activeVendor.connector_id,
        folder_id: folderCapable ? currentFolderId : undefined,
        search: debouncedSearch || undefined,
        page_size: 50,
      })
      setEntries(data.entries ?? [])
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : "Browse failed")
      setEntries([])
    } finally {
      setBrowseLoading(false)
    }
  }, [activeVendor, currentFolderId, debouncedSearch, folderCapable])

  useEffect(() => {
    if (!open || !activeVendor) return
    void loadBrowse()
  }, [open, activeVendor, loadBrowse])

  const toggleFile = (entry: ConnectedFileBrowseEntry) => {
    if (entry.kind !== "file") return
    setPending((prev) => {
      const exists = prev.some((f) => f.vendor === entry.vendor && f.file_id === entry.id)
      if (exists) {
        return prev.filter((f) => !(f.vendor === entry.vendor && f.file_id === entry.id))
      }
      if (prev.length >= MAX_ATTACH) {
        toast.message(`You can attach up to ${MAX_ATTACH} files per message.`)
        return prev
      }
      return [
        ...prev,
        {
          vendor: entry.vendor,
          file_id: entry.id,
          name: entry.name,
          connector_id: entry.connector_id,
          web_link: entry.web_link,
          path: entry.path,
        },
      ]
    })
  }

  const openFolder = (entry: ConnectedFileBrowseEntry) => {
    if (entry.kind !== "folder" || !folderCapable) return
    setCrumbs((prev) => [...prev, { id: entry.id, name: entry.name }])
    setSearch("")
  }

  const goToCrumb = (index: number) => {
    setCrumbs((prev) => prev.slice(0, index + 1))
  }

  const goUp = () => {
    if (crumbs.length <= 1) return
    setCrumbs((prev) => prev.slice(0, -1))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-2xl" showCloseButton>
        <DialogHeader>
          <DialogTitle>Browse connected files</DialogTitle>
          <DialogDescription>
            {storageNote ||
              "Pick files from your connected accounts. Gravitre reads them for this chat only — nothing is uploaded or stored here."}
          </DialogDescription>
        </DialogHeader>

        {vendorsLoading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading integrations…
          </div>
        ) : vendors.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Connect Google Drive, Microsoft 365, Slack, Notion, or Confluence in Settings → Integrations to browse files here.
          </p>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col gap-3">
            {vendors.length > 1 ? (
              <div className="flex flex-wrap gap-2">
                {vendors.map((vendor) => (
                  <Button
                    key={`${vendor.vendor}-${vendor.connector_id}`}
                    type="button"
                    size="sm"
                    variant={activeVendor?.connector_id === vendor.connector_id ? "default" : "outline"}
                    onClick={() => {
                      setActiveVendor(vendor)
                      setCrumbs([{ id: null, name: "Root" }])
                    }}
                  >
                    {vendor.label}
                  </Button>
                ))}
              </div>
            ) : activeVendor ? (
              <p className="text-xs text-muted-foreground">{activeVendor.connector_name}</p>
            ) : null}

            {activeVendor ? (
              <>
                <div className="flex items-center gap-2">
                  {folderCapable ? (
                    <Button type="button" variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={goUp} disabled={crumbs.length <= 1}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                  ) : null}
                  <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1 text-xs text-muted-foreground">
                    {folderCapable
                      ? crumbs.map((crumb, index) => (
                          <span key={`${crumb.id ?? "root"}-${index}`} className="flex items-center gap-1">
                            {index > 0 ? <ChevronRight className="h-3 w-3 opacity-50" /> : null}
                            <button
                              type="button"
                              className="truncate hover:text-foreground"
                              onClick={() => goToCrumb(index)}
                            >
                              {crumb.name}
                            </button>
                          </span>
                        ))
                      : null}
                  </div>
                  <div className="relative w-full max-w-[220px]">
                    <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Filter…"
                      className="h-8 pl-8 text-xs"
                    />
                  </div>
                </div>

                <div className="min-h-[240px] flex-1 overflow-y-auto rounded-md border">
                  {browseLoading ? (
                    <div className="flex items-center justify-center py-16 text-muted-foreground">
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Loading…
                    </div>
                  ) : entries.length === 0 ? (
                    <p className="py-16 text-center text-sm text-muted-foreground">No items here.</p>
                  ) : (
                    <ul className="divide-y">
                      {entries.map((entry) => {
                        const selectedFile =
                          entry.kind === "file" &&
                          pending.some((f) => f.vendor === entry.vendor && f.file_id === entry.id)
                        return (
                          <li key={entry.id}>
                            <button
                              type="button"
                              className={cn(
                                "flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-muted/60",
                                selectedFile && "bg-emerald-500/10",
                              )}
                              onClick={() => {
                                if (entry.kind === "folder") openFolder(entry)
                                else toggleFile(entry)
                              }}
                            >
                              {entry.kind === "folder" ? (
                                <Folder className="h-4 w-4 shrink-0 text-amber-600" />
                              ) : (
                                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                              )}
                              <span className="min-w-0 flex-1 truncate font-medium">{entry.name}</span>
                              {entry.modified_at ? (
                                <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">
                                  {formatModified(entry.modified_at)}
                                </span>
                              ) : null}
                              {entry.kind === "folder" ? (
                                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                              ) : null}
                            </button>
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>

                {pending.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {pending.map((file) => (
                      <span
                        key={`${file.vendor}-${file.file_id}`}
                        className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-2.5 py-1 text-xs"
                      >
                        <FileText className="h-3 w-3" />
                        <span className="max-w-[160px] truncate">{file.name}</span>
                        <button
                          type="button"
                          className="ml-1 text-muted-foreground hover:text-foreground"
                          aria-label={`Remove ${file.name}`}
                          onClick={() =>
                            setPending((prev) =>
                              prev.filter((f) => !(f.vendor === file.vendor && f.file_id === file.file_id)),
                            )
                          }
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Choose a connected account to browse.</p>
            )}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={pending.length === 0}
            onClick={() => {
              onConfirm(pending)
              onOpenChange(false)
            }}
          >
            Attach {pending.length > 0 ? `(${pending.length})` : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

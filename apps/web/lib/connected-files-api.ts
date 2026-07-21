import { fetcher } from "@/lib/fetcher"

export type ConnectedFileVendor = {
  vendor: string
  label: string
  connector_id: string
  connector_name: string
}

export type ConnectedFileBrowseEntry = {
  vendor: string
  connector_id: string
  id: string
  name: string
  kind: "file" | "folder"
  mime_type?: string | null
  modified_at?: string | null
  web_link?: string | null
  path?: string | null
  size?: number | null
}

export type ConnectedFileAttachment = {
  vendor: string
  file_id: string
  name: string
  connector_id: string
  web_link?: string | null
  path?: string | null
}

export async function listConnectedFileVendors(): Promise<{
  vendors: ConnectedFileVendor[]
  storage_note: string
}> {
  return fetcher("/api/connected-files/vendors")
}

export async function browseConnectedFiles(params: {
  vendor: string
  connector_id?: string
  folder_id?: string | null
  search?: string
  page_size?: number
}): Promise<{
  vendor: string
  connector_id: string
  folder_id?: string | null
  entries: ConnectedFileBrowseEntry[]
  storage_note?: string
  browse_mode?: string
}> {
  const query = new URLSearchParams()
  query.set("vendor", params.vendor)
  if (params.connector_id) query.set("connector_id", params.connector_id)
  if (params.folder_id) query.set("folder_id", params.folder_id)
  if (params.search?.trim()) query.set("search", params.search.trim())
  if (params.page_size) query.set("page_size", String(params.page_size))
  return fetcher(`/api/connected-files/browse?${query.toString()}`)
}

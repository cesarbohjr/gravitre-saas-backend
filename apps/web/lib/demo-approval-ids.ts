/** Demo approval ids used by local demo-runtime-store when backend is unavailable. */
export function isDemoApprovalId(id: string): boolean {
  return id.startsWith("apr-")
}

/** Build a workflow-builder deep link that seeds a registered data source onto the canvas. */
export function buildWorkflowFromSourceUrl(source: {
  id: string
  name: string
  type?: string
  connectorId?: string
}): string {
  const params = new URLSearchParams()
  params.set("sourceId", source.id)
  params.set("sourceName", source.name)
  if (source.type) params.set("sourceType", source.type)
  if (source.connectorId) params.set("connectorId", source.connectorId)
  return `/workflows/new/builder?${params.toString()}`
}

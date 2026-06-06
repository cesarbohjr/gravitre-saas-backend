/**
 * Gravitre Connector SDK types (STA-70).
 * Mirrors backend `app/connectors/sdk/manifest.py` and `docs/integration/connector-sdk-spec.md`.
 */

export type ManifestVersion = "1.0"

export type ConnectorCapability = "actions" | "triggers" | "sync" | "rag"

export type TriggerEventType = "webhook" | "poll" | "push"

export interface OAuthAuthConfig {
  type: "oauth2"
  authorizationUrl: string
  tokenUrl: string
  scopes?: string[]
  refreshSupported?: boolean
}

export interface ApiKeyAuthConfig {
  type: "apiKey"
  headerName?: string
  prefix?: string
}

export type AuthConfig = OAuthAuthConfig | ApiKeyAuthConfig

export interface ActionDefinition {
  id: string
  name: string
  description?: string
  scopes?: string[]
  inputSchema?: Record<string, unknown>
  outputSchema?: Record<string, unknown>
  idempotent?: boolean
  destructive?: boolean
}

export interface TriggerDefinition {
  id: string
  name: string
  description?: string
  eventType?: TriggerEventType
  scopes?: string[]
}

export interface ConnectorManifest {
  manifestVersion: ManifestVersion
  id: string
  name: string
  version: string
  vendor: string
  description?: string
  auth: AuthConfig
  capabilities?: ConnectorCapability[]
  actions?: ActionDefinition[]
  triggers?: TriggerDefinition[]
  minPlatformVersion?: string
  homepageUrl?: string
  supportEmail?: string
}

/** Canonical invoke_tool action key: `{vendor}.{actionId}` */
export function actionKey(manifest: ConnectorManifest, actionId: string): string {
  return `${manifest.vendor}.${actionId}`
}

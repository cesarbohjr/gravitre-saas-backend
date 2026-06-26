import { connectorVendorKey } from "@/lib/connectors"

/** Map ML registry provider labels to connector vendor keys for brand logos. */
const ML_PROVIDER_VENDOR: Record<string, string> = {
  openai: "openai",
  anthropic: "anthropic",
  google: "google",
  xai: "xai",
  microsoft: "microsoft",
  amazon: "aws",
  meta: "meta",
  salesforce: "salesforce",
}

export function mlProviderVendorKey(provider: string): string {
  const normalized = provider.trim().toLowerCase()
  if (ML_PROVIDER_VENDOR[normalized]) return ML_PROVIDER_VENDOR[normalized]
  return connectorVendorKey(provider.replace(/\s+/g, "_"))
}

/** Map data-source type ids to the best matching brand vendor key. */
const SOURCE_TYPE_VENDOR: Record<string, string> = {
  supabase_db: "supabase",
  cloud_sql: "google",
  firestore: "google",
  gcs: "google",
  pubsub: "google",
  azure_sql: "microsoft",
  azure_blob: "microsoft",
  synapse: "microsoft",
  mssql: "microsoft",
  rds: "aws",
  kinesis: "aws",
  dynamodb: "aws",
  neon: "postgresql",
  planetscale: "mysql",
}

export function sourceTypeVendorKey(typeId: string): string {
  const key = connectorVendorKey(typeId)
  return SOURCE_TYPE_VENDOR[key] ?? key
}

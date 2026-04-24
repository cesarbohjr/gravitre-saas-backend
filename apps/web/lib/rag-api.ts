/**
 * DC-10: Client helpers for RAG admin API (same-origin). Pass token from useAuth().
 * No direct FastAPI calls from browser.
 */

import { getEnvironmentHeader } from "@/lib/environment";

const API = "/api/rag";

export type RagSourceType =
  | "manual"
  | "internal"
  | "external"
  | "product"
  | "support";

export type RagSource = {
  id: string;
  title: string;
  type: RagSourceType;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type RagDocument = {
  id: string;
  title: string | null;
  external_id: string | null;
  metadata?: Record<string, unknown>;
  updated_at: string;
  source_id?: string;
  chunks?: Array<{ id: string; chunk_index: number; content: string; created_at: string }>;
};

export type IngestResult = {
  ingest_id?: string;
  document_id?: string | null;
  source_id: string;
  external_id?: string | null;
  chunk_count?: number;
  embedding_model?: string;
  embedding_dimension?: number;
  status: "queued" | "running" | "completed" | "failed";
};

export type IngestJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  source_id: string;
  document_id: string | null;
  external_id?: string | null;
  chunk_count: number;
  model?: string;
  dimension?: number;
  error_code?: string | null;
  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
};

export type RagChunk = {
  id: string;
  text: string;
  source_id: string;
  source_title: string;
  document_id: string;
  document_title: string | null;
  chunk_index: number;
  score: number;
};

export type RagRetrieveResponse = {
  query_id: string;
  total: number;
  chunks: RagChunk[];
};

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "X-Environment": getEnvironmentHeader(),
  };
}

export async function fetchSources(token: string): Promise<{ sources: RagSource[] }> {
  const res = await fetch(`${API}/sources`, { headers: headers(token), cache: "no-store" });
  if (!res.ok) throw new Error(res.status === 401 ? "Unauthorized" : "Request failed");
  return res.json();
}

export async function createSource(
  token: string,
  payload: { title: string; type: RagSourceType; metadata?: Record<string, unknown> }
): Promise<RagSource> {
  const res = await fetch(`${API}/sources`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function updateSource(
  token: string,
  id: string,
  payload: { title?: string; metadata?: Record<string, unknown> }
): Promise<RagSource> {
  const res = await fetch(`${API}/sources/${id}`, {
    method: "PATCH",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function fetchDocuments(
  token: string,
  sourceId: string
): Promise<{ documents: RagDocument[] }> {
  const res = await fetch(`${API}/documents?source_id=${encodeURIComponent(sourceId)}`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(res.status === 401 ? "Unauthorized" : "Request failed");
  return res.json();
}

export async function fetchDocument(
  token: string,
  id: string,
  opts?: { includeChunks?: boolean }
): Promise<RagDocument> {
  const qs = opts?.includeChunks ? "?include_chunks=true" : "";
  const res = await fetch(`${API}/documents/${id}${qs}`, {
    headers: headers(token),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function postIngest(
  token: string,
  payload: Record<string, unknown>
): Promise<IngestResult> {
  const res = await fetch(`${API}/ingest`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function fetchIngestJob(token: string, ingestId: string): Promise<IngestJob> {
  const res = await fetch(`${API}/ingest/${ingestId}`, { headers: headers(token), cache: "no-store" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function retrieveRag(
  token: string,
  payload: {
    query: string;
    top_k?: number;
    source_id?: string | null;
    document_id?: string | null;
    min_score?: number | null;
  }
): Promise<RagRetrieveResponse> {
  const res = await fetch(`${API}/retrieve`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

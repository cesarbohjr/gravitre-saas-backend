import {
  consumeStream,
  convertToModelMessages,
  streamText,
  UIMessage,
  tool,
} from 'ai'
import { createOpenAI } from '@ai-sdk/openai'
import { NextRequest } from "next/server"
import { z } from 'zod'
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg, getDemoRowsForOrg } from "@/lib/supabase/demo-bootstrap"

export const maxDuration = 30

// Use the direct OpenAI provider so the chat assistant depends only on
// OPENAI_API_KEY (already configured for the backend) rather than requiring
// Vercel AI Gateway credentials.
const openai = createOpenAI({ apiKey: process.env.OPENAI_API_KEY })

// System prompt for the Gravitre AI Assistant
const SYSTEM_PROMPT = `You are a helpful AI assistant for Gravitre, an enterprise automation platform. You help users manage their:

- **Agents**: AI agents that automate tasks (Marketing, Sales, Operations, Finance, Support)
- **Workflows**: Automated processes that connect different systems
- **Connectors**: Integrations with external services (Salesforce, Stripe, Slack, HubSpot, etc.)
- **Data Sources**: Knowledge bases and documents for RAG-powered search

You can help users:
1. Understand how their systems work together
2. Troubleshoot issues with connectors or workflows
3. Suggest optimizations for their automation setup
4. Answer questions about their data and analytics
5. Guide them through creating new agents or workflows

Be concise but helpful. Use bullet points when listing items. If you don't know something specific about their setup, acknowledge it and suggest how they might find the information.`

function createChatTools(req: NextRequest, orgId: string) {
  const supabase = createSupabaseRouteClient(req)
  const demoRows = getDemoRowsForOrg(orgId)

  return {
    searchKnowledgeBase: tool({
      description: 'Search the knowledge base for relevant documents and information',
      inputSchema: z.object({
        query: z.string().describe('The search query'),
        limit: z.number().default(5).describe('Number of results to return'),
      }),
      execute: async ({ query, limit }) => {
        const safeLimit = Math.max(1, Math.min(limit, 10))
        const likeTerm = `%${query}%`

        const { data, error } = await supabase
          .from("rag_chunks")
          .select("id, content, source_id, source_name, source:rag_sources(name)")
          .eq("org_id", orgId)
          .ilike("content", likeTerm)
          .limit(safeLimit)

        if (error) {
          return {
            results: [],
            totalResults: 0,
            error: error.message,
          }
        }

        const results = (data ?? []).map((row) => {
          const content = String(row.content ?? "")
          const sourceObj = row.source as { name?: string } | null
          return {
            title: String(sourceObj?.name ?? row.source_name ?? "Knowledge Source"),
            snippet: content.slice(0, 220),
            relevance: Math.max(0.5, Math.min(0.99, query.length > 0 ? content.toLowerCase().includes(query.toLowerCase()) ? 0.92 : 0.71 : 0.7)),
          }
        })

        return {
          results,
          totalResults: results.length,
        }
      },
    }),

    getAgentStatus: tool({
      description: 'Get the current status and metrics for agents',
      inputSchema: z.object({
        agentId: z.string().optional().describe('Specific agent ID, or omit for all agents'),
      }),
      execute: async ({ agentId }) => {
        const { data, error } = await supabase
          .from("agents")
          .select("id, name, status, stats")
          .eq("org_id", orgId)
          .order("created_at", { ascending: false })

        if (error) {
          return {
            agents: [],
            error: error.message,
          }
        }

        const normalized = (data ?? []).map((row) => {
          const stats = row.stats && typeof row.stats === "object" ? (row.stats as Record<string, unknown>) : {}
          return {
            id: String(row.id),
            name: String(row.name ?? "Agent"),
            status: String(row.status ?? "idle"),
            tasksToday: Number(stats.tasksToday ?? 0),
            successRate: Number(stats.successRate ?? 100),
          }
        })

        const fallback = (demoRows?.agents ?? []).map((row) => ({
          id: String(row.id),
          name: String(row.name ?? "Agent"),
          status: String(row.status ?? "idle"),
          tasksToday: Number((row.stats as Record<string, unknown> | undefined)?.tasksToday ?? 0),
          successRate: Number((row.stats as Record<string, unknown> | undefined)?.successRate ?? 100),
        }))

        const agents = normalized.length > 0 ? normalized : fallback
        const needle = agentId?.toLowerCase()
        return {
          agents: needle
            ? agents.filter((a) => a.id.toLowerCase() === needle || a.name.toLowerCase() === needle)
            : agents,
        }
      },
    }),

    getConnectorStatus: tool({
      description: 'Get the status of connected integrations',
      inputSchema: z.object({
        connectorType: z.string().optional().describe('Specific connector type, or omit for all'),
      }),
      execute: async ({ connectorType }) => {
        const { data, error } = await supabase
          .from("connectors")
          .select("id, name, type, status, health")
          .eq("org_id", orgId)
          .order("created_at", { ascending: false })

        if (error) {
          const isMissingConnectorsTable = String(error.message).toLowerCase().includes("does not exist")
          if (!isMissingConnectorsTable) {
            return { connectors: [], error: error.message }
          }

          const { data: fallbackSystems, error: fallbackError } = await supabase
            .from("connected_systems")
            .select("id, name, system_key, type, status, config")
            .eq("org_id", orgId)
            .order("created_at", { ascending: false })

          if (fallbackError) {
            return { connectors: [], error: fallbackError.message }
          }

          const connectors = (fallbackSystems ?? []).map((row) => {
            const config = row.config && typeof row.config === "object" ? (row.config as Record<string, unknown>) : {}
            return {
              id: String(row.id),
              name: String(row.system_key ?? row.name ?? "connector"),
              type: String(row.name ?? row.type ?? "Custom"),
              status: String(row.status ?? "disconnected"),
              health: Number(config.health ?? (row.status === "connected" ? 100 : 0)),
            }
          })

          const needle = connectorType?.toLowerCase()
          return {
            connectors: needle ? connectors.filter((c) => c.type.toLowerCase() === needle) : connectors,
          }
        }

        const connectors = (data ?? []).map((row) => ({
          id: String(row.id),
          name: String(row.name ?? "connector"),
          type: String(row.type ?? "Custom"),
          status: String(row.status ?? "disconnected"),
          health: Number(row.health ?? 0),
        }))

        const needle = connectorType?.toLowerCase()
        return {
          connectors: needle ? connectors.filter((c) => c.type.toLowerCase() === needle) : connectors,
        }
      },
    }),
  }
}

function jsonError(message: string, status: number, detail?: string) {
  return new Response(JSON.stringify({ error: message, ...(detail ? { detail } : {}) }), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

export async function POST(req: NextRequest) {
  if (!process.env.OPENAI_API_KEY) {
    return jsonError("AI assistant is not configured", 503, "OPENAI_API_KEY is not set")
  }

  let messages: UIMessage[]
  try {
    const body = (await req.json()) as { messages?: UIMessage[] }
    if (!Array.isArray(body?.messages)) {
      return jsonError("Invalid request body", 400, "Expected a 'messages' array")
    }
    messages = body.messages
  } catch {
    return jsonError("Invalid JSON body", 400)
  }

  const supabase = createSupabaseRouteClient(req)
  const orgId = await resolveOrgId(supabase, req)
  if (!orgId) {
    return jsonError("Organization context required", 403)
  }

  try {
    await ensureDemoDataForOrg(supabase, orgId)
    const tools = createChatTools(req, orgId)
    const modelMessages = await convertToModelMessages(messages)

    const result = streamText({
      model: openai('gpt-4o-mini'),
      system: SYSTEM_PROMPT,
      messages: modelMessages,
      tools,
      abortSignal: req.signal,
    })

    return result.toUIMessageStreamResponse({
      originalMessages: messages,
      consumeSseStream: consumeStream,
      onError: (error) => {
        console.error("[chat] stream error:", error)
        return error instanceof Error ? error.message : "The assistant hit an unexpected error."
      },
    })
  } catch (error) {
    console.error("[chat] request failed:", error)
    return jsonError(
      "Failed to start AI assistant",
      500,
      error instanceof Error ? error.message : undefined,
    )
  }
}

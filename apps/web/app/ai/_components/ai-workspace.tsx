"use client"

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import useSWR from "swr"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { motion } from "framer-motion"
import {
  ArrowUp,
  Loader2,
  PanelLeft,
  PanelLeftClose,
  Sparkles,
  Square,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import { ensureSelectedOrg, buildChatOrgPayload } from "@/lib/org-context"
import { parseChatError } from "@/lib/chat-errors"
import { conversationMessageToUI } from "@/lib/chat-messages"
import { conversationsApi, searchApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import type { AiEngine } from "@/lib/ai-surface-handoff"
import type { SearchResult } from "@/types/api"
import { ConversationSidebar } from "@/components/gravitre/assistant/conversation-sidebar"
import { Button } from "@/components/ui/button"
import { useAsyncJob, type AgentJob } from "@/hooks/use-async-job"
import {
  buildOperatorJobPayload,
  createOperatorSession,
  fallbackActionPlanSteps,
  fallbackInsightSections,
  fallbackSuggestedActionsList,
  planFromJobResult,
  runSyncOperatorTask,
  type InlineExecutePlan,
} from "@/lib/ai-inline-execute"
import {
  describeOperatorJobError,
  isBackendUnavailableError,
} from "@/lib/operator-plan"
import { AiExecuteResults } from "./ai-execute-results"
import { AiFindResults } from "./ai-find-results"
import { AiLanding } from "./ai-landing"
import { AiLayoutPanelPicker } from "./ai-layout-panel-picker"
import { AI_MODES, getModeMeta, type ModeId } from "./ai-mode-config"
import {
  DEFAULT_RESULT_BLOCK_ORDER,
  type ResultBlockId,
} from "./draggable-result-stack"

const CONVERSATION_ID_KEY = "gravitre_ai_conversation_id"

type InlineTurn = {
  id: string
  prompt: string
  engine: AiEngine
  status: "running" | "completed" | "failed"
  executePlan?: InlineExecutePlan | null
  executeJob?: AgentJob | null
  executeError?: string | null
  findResults?: SearchResult[]
  findSuggestions?: string[]
  findError?: string | null
}

type AiWorkspaceProps = {
  initialMode?: ModeId
  initialPrompt?: string
}

function normalizeChatText(message: UIMessage): string {
  const parts = (message.parts ?? []) as Array<{ type?: string; text?: string }>
  return parts
    .filter((part) => part.type === "text" && typeof part.text === "string")
    .map((part) => part.text as string)
    .join("")
}

export function AiWorkspace({ initialMode = "auto", initialPrompt = "" }: AiWorkspaceProps) {
  const { user } = useAuth()
  const [mode, setMode] = useState<ModeId>(initialMode)
  const [input, setInput] = useState("")
  const [routing, setRouting] = useState(false)
  const [routedTo, setRoutedTo] = useState<AiEngine | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [inlineTurns, setInlineTurns] = useState<InlineTurn[]>([])
  const [layoutBlockOrder, setLayoutBlockOrder] = useState<ResultBlockId[]>(DEFAULT_RESULT_BLOCK_ORDER)
  const [layoutEnabledBlocks, setLayoutEnabledBlocks] = useState<ResultBlockId[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    return localStorage.getItem(CONVERSATION_ID_KEY)
  })
  const [conversationTitle, setConversationTitle] = useState("Gravitre AI")
  const [chatMode] = useState<"standard" | "deep">("standard")

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const activeConversationIdRef = useRef<string | null>(activeConversationId)
  const submitLockRef = useRef(false)
  const pendingConversationRef = useRef<Promise<string | null> | null>(null)
  const operatorSessionRef = useRef<string | null>(null)
  const activeExecuteTurnRef = useRef<string | null>(null)
  const initialPromptSentRef = useRef(false)
  const hydrationDoneRef = useRef(false)

  const activeMode = useMemo(() => getModeMeta(mode), [mode])

  const {
    data: conversationsData,
    error: conversationsError,
    isLoading: conversationsLoading,
    mutate: mutateConversations,
  } = useSWR(
    user ? "ai-conversations" : null,
    () => conversationsApi.list({ limit: 100, includeArchived: true }),
    { revalidateOnFocus: false },
  )
  const conversations = conversationsData?.conversations ?? []

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/chat",
        headers: async () => {
          const token = await getAccessToken()
          const orgId = await ensureSelectedOrg()
          return {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(orgId ? { "x-org-id": orgId } : {}),
          }
        },
        body: () => ({
          ...buildChatOrgPayload(),
          mode: chatMode,
          conversation_id: activeConversationIdRef.current,
        }),
      }),
    [chatMode],
  )

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport,
    onError: (error) => {
      submitLockRef.current = false
      toast.error(parseChatError(error))
    },
    onFinish: () => {
      submitLockRef.current = false
      void mutateConversations()
    },
  })

  const {
    isWorking: executeWorking,
    error: executeHookError,
    submitJob,
    reset: resetExecuteJob,
  } = useAsyncJob({
    onCompleted: useCallback((job: AgentJob) => {
      const turnId = activeExecuteTurnRef.current
      if (!turnId) return
      setInlineTurns((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: "completed",
                executeJob: job,
                executePlan: planFromJobResult(job),
                executeError: null,
              }
            : turn,
        ),
      )
      activeExecuteTurnRef.current = null
    }, []),
    onFailed: useCallback((job: AgentJob) => {
      const turnId = activeExecuteTurnRef.current
      if (!turnId) return
      setInlineTurns((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: "failed",
                executeError: job.error || "Analysis failed",
              }
            : turn,
        ),
      )
      activeExecuteTurnRef.current = null
    }, []),
  })

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId
  }, [activeConversationId])

  useEffect(() => {
    if (user) void ensureSelectedOrg(true)
  }, [user])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, inlineTurns, status])

  const classifyIntent = useCallback(async (prompt: string): Promise<AiEngine> => {
    const res = await fetch("/api/ai/route-intent", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt }),
    })
    if (!res.ok) throw new Error(`route-intent ${res.status}`)
    const data = (await res.json()) as { mode: AiEngine }
    return data.mode
  }, [])

  const resolveEngine = useCallback(
    async (prompt: string, selectedMode: ModeId): Promise<AiEngine> => {
      if (selectedMode !== "auto") return selectedMode
      setRouting(true)
      setRoutedTo(null)
      try {
        const engine = await classifyIntent(prompt)
        setRoutedTo(engine)
        return engine
      } catch {
        return "chat"
      } finally {
        setRouting(false)
        setRoutedTo(null)
      }
    },
    [classifyIntent],
  )

  const ensureConversation = useCallback(
    async (title: string) => {
      if (activeConversationIdRef.current) return activeConversationIdRef.current
      if (!pendingConversationRef.current) {
        pendingConversationRef.current = conversationsApi
          .create({ title: title.slice(0, 80) })
          .then((created) => {
            activeConversationIdRef.current = created.id
            setActiveConversationId(created.id)
            setConversationTitle(created.title || title.slice(0, 80))
            localStorage.setItem(CONVERSATION_ID_KEY, created.id)
            void mutateConversations()
            return created.id
          })
          .catch(() => null)
          .finally(() => {
            pendingConversationRef.current = null
          })
      }
      return pendingConversationRef.current
    },
    [mutateConversations],
  )

  const runChat = useCallback(
    async (prompt: string) => {
      submitLockRef.current = true
      await ensureConversation(prompt)
      sendMessage({ text: prompt })
    },
    [ensureConversation, sendMessage],
  )

  const runExecute = useCallback(
    async (prompt: string, turnId: string) => {
      activeExecuteTurnRef.current = turnId
      if (!operatorSessionRef.current) {
        operatorSessionRef.current = await createOperatorSession(prompt)
      }

      try {
        resetExecuteJob()
        await submitJob(prompt, buildOperatorJobPayload(operatorSessionRef.current, prompt))
      } catch (err) {
        if (isBackendUnavailableError(err)) {
          try {
            const sessionId = operatorSessionRef.current ?? (await createOperatorSession(prompt))
            if (sessionId) operatorSessionRef.current = sessionId
            if (!sessionId) throw new Error("Could not create operator session")
            const plan = await runSyncOperatorTask(sessionId, prompt)
            setInlineTurns((prev) =>
              prev.map((turn) =>
                turn.id === turnId
                  ? { ...turn, status: "completed", executePlan: plan, executeError: null }
                  : turn,
              ),
            )
            activeExecuteTurnRef.current = null
            return
          } catch (fallbackErr) {
            setInlineTurns((prev) =>
              prev.map((turn) =>
                turn.id === turnId
                  ? {
                      ...turn,
                      status: "completed",
                      executePlan: {
                        findings: fallbackInsightSections,
                        steps: fallbackActionPlanSteps,
                        suggestedActions: fallbackSuggestedActionsList,
                      },
                      executeError: describeOperatorJobError(fallbackErr),
                    }
                  : turn,
              ),
            )
            activeExecuteTurnRef.current = null
            return
          }
        }
        setInlineTurns((prev) =>
          prev.map((turn) =>
            turn.id === turnId
              ? { ...turn, status: "failed", executeError: describeOperatorJobError(err) }
              : turn,
          ),
        )
        activeExecuteTurnRef.current = null
      }
    },
    [resetExecuteJob, submitJob],
  )

  const runFind = useCallback(async (prompt: string, turnId: string) => {
    try {
      const response = await searchApi.search(prompt)
      setInlineTurns((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: "completed",
                findResults: response.results,
                findSuggestions: response.suggestions,
                findError: null,
              }
            : turn,
        ),
      )
    } catch {
      setInlineTurns((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? { ...turn, status: "failed", findError: "Search failed. Try again." }
            : turn,
        ),
      )
    }
  }, [])

  const submitPrompt = useCallback(
    async (rawPrompt: string) => {
      const prompt = rawPrompt.trim()
      if (!prompt || routing || submitLockRef.current) return
      if (!user) {
        toast.error("Sign in to use Gravitre AI")
        return
      }

      await ensureSelectedOrg()
      const engine = await resolveEngine(prompt, mode)
      setInput("")

      if (engine === "chat") {
        await runChat(prompt)
        return
      }

      const turnId = `turn-${Date.now()}`
      setInlineTurns((prev) => [
        ...prev,
        {
          id: turnId,
          prompt,
          engine,
          status: "running",
        },
      ])

      if (engine === "execute") {
        await runExecute(prompt, turnId)
      } else {
        await runFind(prompt, turnId)
      }
    },
    [mode, resolveEngine, routing, runChat, runExecute, runFind, user],
  )

  useEffect(() => {
    if (initialPromptSentRef.current || !initialPrompt.trim()) return
    initialPromptSentRef.current = true
    void submitPrompt(initialPrompt)
  }, [initialPrompt, submitPrompt])

  const handleSelectConversation = useCallback(
    async (id: string) => {
      setActiveConversationId(id)
      activeConversationIdRef.current = id
      localStorage.setItem(CONVERSATION_ID_KEY, id)
      try {
        const { messages: stored } = await conversationsApi.getMessages(id)
        setMessages(stored.map(conversationMessageToUI))
        const selected = conversations.find((c) => c.id === id)
        setConversationTitle(selected?.title || "Gravitre AI")
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          localStorage.removeItem(CONVERSATION_ID_KEY)
          setActiveConversationId(null)
          activeConversationIdRef.current = null
          setMessages([])
        }
        toast.error("Could not load conversation")
      }
    },
    [conversations, setMessages],
  )

  const handleNewConversation = useCallback(() => {
    setMessages([])
    setInlineTurns([])
    setActiveConversationId(null)
    activeConversationIdRef.current = null
    pendingConversationRef.current = null
    operatorSessionRef.current = null
    localStorage.removeItem(CONVERSATION_ID_KEY)
    resetExecuteJob()
    setConversationTitle("Gravitre AI")
    inputRef.current?.focus()
    void mutateConversations()
  }, [mutateConversations, resetExecuteJob, setMessages])

  const handleDeleteConversation = useCallback(
    async (id: string) => {
      await conversationsApi.delete(id)
      if (activeConversationId === id) handleNewConversation()
      void mutateConversations()
    },
    [activeConversationId, handleNewConversation, mutateConversations],
  )

  const handleArchiveConversation = useCallback(
    async (id: string) => {
      await conversationsApi.archive(id)
      if (activeConversationId === id) handleNewConversation()
      void mutateConversations()
    },
    [activeConversationId, handleNewConversation, mutateConversations],
  )

  const handleRenameConversation = useCallback(
    async (id: string, title: string) => {
      await conversationsApi.update(id, { title })
      if (activeConversationId === id) setConversationTitle(title)
      void mutateConversations()
    },
    [activeConversationId, mutateConversations],
  )

  const handleBulkDeleteConversations = useCallback(
    async (ids: string[]) => {
      await conversationsApi.bulkDelete(ids)
      if (activeConversationId && ids.includes(activeConversationId)) handleNewConversation()
      void mutateConversations()
    },
    [activeConversationId, handleNewConversation, mutateConversations],
  )

  const isChatBusy = status === "submitted" || status === "streaming"
  const showConversationsSkeleton = Boolean(user) && conversationsLoading && !conversationsData
  const showConversationsError = Boolean(user) && Boolean(conversationsError) && !conversationsLoading

  useEffect(() => {
    if (!user || hydrationDoneRef.current || conversationsLoading) return
    const storedId = localStorage.getItem(CONVERSATION_ID_KEY)
    if (storedId) {
      hydrationDoneRef.current = true
      void handleSelectConversation(storedId)
      return
    }
    hydrationDoneRef.current = true
  }, [user, conversationsLoading, handleSelectConversation])

  const handleToggleLayoutBlock = useCallback((blockId: ResultBlockId, enabled: boolean) => {
    setLayoutEnabledBlocks((current) => {
      if (enabled) {
        if (current.includes(blockId)) return current
        return [...current, blockId]
      }
      return current.filter((id) => id !== blockId)
    })
    if (enabled) {
      setLayoutBlockOrder((current) => (current.includes(blockId) ? current : [...current, blockId]))
    }
  }, [])

  const latestExecuteTurn = useMemo(
    () => [...inlineTurns].reverse().find((turn) => turn.engine === "execute") ?? null,
    [inlineTurns],
  )

  const showLanding =
    messages.length === 0 &&
    inlineTurns.length === 0 &&
    !isChatBusy &&
    !routing &&
    !initialPrompt.trim()

  const showPinnedLayout =
    layoutEnabledBlocks.length > 0 && latestExecuteTurn == null && inlineTurns.length === 0

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    event.preventDefault()
    void submitPrompt(input)
  }

  return (
    <div className="flex h-full min-h-0">
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelect={(id) => void handleSelectConversation(id)}
        onNew={handleNewConversation}
        onDelete={(id) => void handleDeleteConversation(id)}
        onArchive={(id) => void handleArchiveConversation(id)}
        onRename={(id, title) => void handleRenameConversation(id, title)}
        onBulkDelete={(ids) => void handleBulkDeleteConversations(ids)}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((open) => !open)}
        isLoading={showConversationsSkeleton}
        loadError={showConversationsError ? conversationsError : undefined}
        onRetry={() => void mutateConversations()}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-14 items-center justify-between border-b border-border bg-card/40 px-4 md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen((open) => !open)}
              className="h-8 w-8 text-muted-foreground"
              aria-label={sidebarOpen ? "Hide history" : "Show history"}
            >
              {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
            </Button>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-foreground">{conversationTitle}</p>
              <p className="truncate text-xs text-muted-foreground">
                {activeMode.badge} · results stay on this page
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-1.5">
            <AiLayoutPanelPicker
              enabledBlocks={layoutEnabledBlocks}
              onToggleBlock={handleToggleLayoutBlock}
            />
            <div className="hidden flex-wrap gap-1.5 sm:flex">
            {AI_MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMode(m.id)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide transition-colors",
                  mode === m.id
                    ? cn("ring-1", m.ring, "text-foreground")
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                {m.label}
              </button>
            ))}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto max-w-3xl space-y-6">
            {showLanding ? (
              <AiLanding
                mode={mode}
                onModeChange={setMode}
                input={input}
                onInputChange={setInput}
                routing={routing}
                routedTo={routedTo}
                onSubmit={() => void submitPrompt(input)}
              />
            ) : null}

            {!showLanding
              ? messages.map((message) => {
              const text = normalizeChatText(message)
              const isUser = message.role === "user"
              return (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}
                >
                  {!isUser ? (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-500">
                      <Sparkles className="h-4 w-4 text-white" />
                    </div>
                  ) : null}
                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-4 py-3 text-sm",
                      isUser
                        ? "bg-primary text-primary-foreground"
                        : "border border-border bg-card text-foreground",
                    )}
                  >
                    {isUser ? (
                      <p className="whitespace-pre-wrap">{text}</p>
                    ) : (
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{text || "…"}</ReactMarkdown>
                      </div>
                    )}
                  </div>
                </motion.div>
              )
            })
              : null}

            {!showLanding
              ? inlineTurns.map((turn) => (
              <div key={turn.id} className="space-y-4">
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl bg-primary px-4 py-3 text-sm text-primary-foreground">
                    <p className="whitespace-pre-wrap">{turn.prompt}</p>
                    <p className="mt-1 text-[10px] uppercase tracking-wide opacity-70">
                      {getModeMeta(turn.engine).badge}
                    </p>
                  </div>
                </div>

                {turn.engine === "execute" ? (
                  <AiExecuteResults
                    plan={turn.executePlan ?? null}
                    job={turn.executeJob ?? null}
                    isProcessing={turn.status === "running" && executeWorking}
                    error={turn.executeError ?? (turn.status === "running" ? executeHookError : null)}
                    blockOrder={layoutBlockOrder}
                    enabledBlocks={layoutEnabledBlocks}
                    onReorderBlocks={setLayoutBlockOrder}
                  />
                ) : null}

                {turn.engine === "find" ? (
                  <AiFindResults
                    results={turn.findResults ?? []}
                    suggestions={turn.findSuggestions ?? []}
                    isSearching={turn.status === "running"}
                    onSuggestionSelect={(query) => void submitPrompt(query)}
                  />
                ) : null}

                {turn.findError ? (
                  <p className="text-sm text-destructive">{turn.findError}</p>
                ) : null}
              </div>
            ))
              : null}

            {showPinnedLayout ? (
              <AiExecuteResults
                plan={null}
                job={null}
                isProcessing={false}
                error={null}
                blockOrder={layoutBlockOrder}
                enabledBlocks={layoutEnabledBlocks}
                onReorderBlocks={setLayoutBlockOrder}
              />
            ) : null}

            {routing ? (
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Reading your intent…
              </div>
            ) : null}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {!showLanding ? (
        <div className="border-t border-border bg-background/95 px-4 py-4 backdrop-blur md:px-8">
          <div className="mx-auto max-w-3xl">
            <div
              className={cn(
                "rounded-2xl border bg-card p-2 shadow-sm focus-within:ring-2",
                activeMode.id === "execute" && "focus-within:border-emerald-500/50 focus-within:ring-emerald-500/20",
                activeMode.id === "chat" && "focus-within:border-blue-500/50 focus-within:ring-blue-500/20",
                activeMode.id === "find" && "focus-within:border-amber-500/50 focus-within:ring-amber-500/20",
                activeMode.id === "auto" && "focus-within:border-foreground/30 focus-within:ring-foreground/15",
              )}
            >
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                rows={2}
                disabled={routing}
                placeholder="Ask, delegate, or search — results appear here…"
                className="w-full resize-none bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground/70"
              />
              <div className="flex items-center justify-between px-2 pb-1">
                <p className="text-xs text-muted-foreground">{activeMode.blurb}</p>
                <div className="flex items-center gap-2">
                  {isChatBusy ? (
                    <Button variant="outline" size="sm" className="h-8" onClick={() => stop()}>
                      <Square className="mr-1 h-3 w-3" />
                      Stop
                    </Button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void submitPrompt(input)}
                    disabled={!input.trim() || routing || isChatBusy}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground disabled:opacity-40"
                    aria-label="Send"
                  >
                    <ArrowUp className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        ) : null}
      </div>
    </div>
  )
}

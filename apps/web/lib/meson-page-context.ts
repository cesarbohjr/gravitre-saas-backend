import { APP_ROUTES } from "@/lib/app-routes"

export type ResolvedMesonPage = {
  page: string
  entityId?: string
}

/** Map current route to Meson page-context API parameters. */
export function resolveMesonPageFromPath(pathname: string): ResolvedMesonPage {
  const path = pathname.split("?")[0]?.replace(/\/+$/, "") || "/"

  if (path === "/ai" || path.startsWith("/ai/")) {
    return { page: "ai-chat" }
  }

  if (path === APP_ROUTES.home || path === "/home" || path === "/welcome") {
    return { page: "home" }
  }

  if (path === APP_ROUTES.multiAgentRun || path.startsWith("/multi-agent-run")) {
    return { page: "multi-agent-run" }
  }

  const modelDetail = path.match(/^\/models\/([^/]+)$/)
  if (modelDetail && modelDetail[1] !== "new") {
    return { page: "model-detail", entityId: modelDetail[1] }
  }

  if (path === "/models" || path.startsWith("/models/")) {
    return { page: "model-registry" }
  }

  const agentDetail = path.match(/^\/agents\/([^/]+)$/)
  if (agentDetail && !["new", "create", "swarm"].includes(agentDetail[1] ?? "")) {
    return { page: "agent-detail", entityId: agentDetail[1] }
  }

  const workflowDetail = path.match(/^\/workflows\/([^/]+)/)
  if (workflowDetail && !["new", "failure-predictions"].includes(workflowDetail[1] ?? "")) {
    return { page: "workflow-detail", entityId: workflowDetail[1] }
  }

  if (path.startsWith("/workflows/failure-predictions")) {
    return { page: "failure-alerts" }
  }
  if (path.startsWith("/activity")) {
    return { page: "activity" }
  }

  if (path.startsWith("/workflows")) return { page: "workflows" }
  if (path.startsWith("/connectors")) return { page: "connectors" }
  if (path.startsWith("/agents")) return { page: "agents" }
  if (path.startsWith("/training")) return { page: "training" }
  if (path.startsWith("/multi-agent-run")) return { page: "agents" }
  if (path.startsWith("/intelligence")) return { page: "intelligence" }
  if (path.startsWith("/marketplace")) return { page: "marketplace" }
  if (path.startsWith("/runs")) return { page: "activity" }
  if (path.startsWith("/metrics")) return { page: "intelligence" }
  if (path === "/schedules" || path.startsWith("/schedules/")) {
    return { page: "schedules" }
  }
  const workflowSchedules = path.match(/^\/workflows\/([^/]+)\/schedules$/)
  if (workflowSchedules && workflowSchedules[1]) {
    return { page: "schedules", entityId: workflowSchedules[1] }
  }
  if (path.startsWith("/assignments")) return { page: "assignments" }
  if (path.startsWith("/goals")) return { page: "goals" }

  return { page: "general" }
}

export function shouldShowMesonToolbar(pathname: string): boolean {
  const path = pathname.split("?")[0] ?? ""
  if (path === "/ai" || path.startsWith("/ai/")) return false
  const hiddenPrefixes = ["/login", "/get-started", "/welcome", "/auth/", "/pricing", "/onboarding"]
  return !hiddenPrefixes.some((prefix) => path.startsWith(prefix))
}

/** Route Meson suggestion chips to the most relevant in-app destination. */
export function routeMesonSuggestion(
  pathname: string,
  suggestion: { id: string; label: string },
  navigate: (href: string) => void,
): void {
  const path = pathname.split("?")[0]?.replace(/\/+$/, "") || "/"
  const id = suggestion.id.toLowerCase()
  const label = suggestion.label.toLowerCase()

  const go = (href: string) => navigate(href)

  if (id.includes("multi-agent") || id.includes("swarm") || label.includes("multi-agent")) {
    go(APP_ROUTES.multiAgentRun)
    return
  }
  if (id.includes("marketplace") || label.includes("marketplace") || label.includes("asset pack")) {
    go(APP_ROUTES.marketplace)
    return
  }
  if (id.includes("connector") || label.includes("connector")) {
    go("/connectors")
    return
  }
  if (id.includes("workflow") || label.includes("workflow")) {
    const workflowDetail = path.match(/^\/workflows\/([^/]+)/)
    if (workflowDetail && !["new", "failure-predictions"].includes(workflowDetail[1] ?? "")) {
      go(`/workflows/${workflowDetail[1]}/builder`)
      return
    }
    go("/workflows")
    return
  }
  if (id.includes("failure") || id.includes("alert") || label.includes("failure")) {
    go(`${APP_ROUTES.activity}?tab=failures`)
    return
  }
  if (id.includes("training") || label.includes("training") || id.includes("dataset") || label.includes("dataset")) {
    go("/training")
    return
  }
  if (id.includes("agent") || label.includes("agent")) {
    const agentDetail = path.match(/^\/agents\/([^/]+)/)
    if (agentDetail && !["new", "create", "swarm"].includes(agentDetail[1] ?? "")) {
      if (id.includes("knowledge") || label.includes("knowledge")) {
        go(`/agents/${agentDetail[1]}/knowledge`)
        return
      }
      if (id.includes("chat") || label.includes("chat")) {
        go(`/agents/${agentDetail[1]}/chat`)
        return
      }
    }
    go("/agents")
    return
  }
  if (id.includes("register") || label.includes("register")) {
    go("/models?action=register")
    return
  }
  if (id.includes("deploy") || label.includes("deploy") || id.includes("inference") || label.includes("inference")) {
    const modelDetail = path.match(/^\/models\/([^/]+)$/)
    if (modelDetail && modelDetail[1] !== "new") {
      go(`/models/${modelDetail[1]}`)
      return
    }
    go("/models")
    return
  }
  if (id.includes("model") || label.includes("model") || path.startsWith("/models")) {
    go("/models")
    return
  }
  if (id.includes("learning") || label.includes("learning") || path.startsWith("/intelligence")) {
    go(APP_ROUTES.learning)
    return
  }
  if (id.includes("chat") || label.includes("delegate") || label.includes("summarize")) {
    go(APP_ROUTES.gravitreAi)
    return
  }
  if (path.startsWith("/connectors")) {
    go("/connectors")
    return
  }
  if (path.startsWith("/intelligence")) {
    go(APP_ROUTES.learning)
    return
  }
  if (id.includes("run") || label.includes("run")) {
    go("/runs")
    return
  }
  if (id.includes("schedule") || label.includes("schedule") || path.startsWith("/schedules")) {
    go("/schedules")
  }
}

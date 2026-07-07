/**
 * Canonical docs terminology — keep MDX and marketing aligned with product UI.
 * GIBE = Gravitre Intelligent Business Engine (org-scoped learning + ML catalog).
 */
export const DOCS_COPY = {
  gibe: {
    fullName: "Gravitre Intelligent Business Engine",
    shortName: "GIBE",
    tagline: "Observe → Learn → Recommend → Execute (with approval)",
    description:
      "GIBE is Gravitre's org-scoped learning stack — query clusters, memory promotion, built-in ML models, retrieval rankers, and predictive ops. It learns only from verified signals in your org.",
    route: "/intelligence/learning",
    docsHref: "/docs/guides/how-to/org-learning",
  },
  surfaces: {
    gravitreAi: {
      name: "Gravitre AI",
      route: "/ai",
      executeRoute: "/ai?mode=execute",
      chatRoute: "/ai?mode=chat",
      findRoute: "/ai?mode=find",
      searchRoute: "/search",
    },
    insights: { name: "Insights", route: "/intelligence" },
    learning: { name: "Learning", route: "/intelligence/learning" },
    training: { name: "Training", route: "/training" },
    models: { name: "Models", route: "/models" },
    builtInModels: { name: "Built-in models", route: "/models/built-in" },
  },
  legacyNote:
    "Legacy routes `/command-center`, `/assistant`, and `/operator` redirect to Gravitre AI. `/admin/intelligence` redirects to Learning.",
} as const

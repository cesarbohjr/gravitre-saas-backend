/** Org-scoped intelligence models trainable from Admin → Org Learning → Engine. */
export type OrgLearningModelId =
  | "intent_classifier"
  | "query_clusterer"
  | "memory_promotion_scorer"
  | "retrieval_ranker"

export type OrgLearningModelDefinition = {
  id: OrgLearningModelId
  label: string
  version: string
  description: string
  dataHint: string
}

export const ORG_LEARNING_TRAIN_MODELS: OrgLearningModelDefinition[] = [
  {
    id: "intent_classifier",
    label: "Query intent",
    version: "v2",
    description: "Routes and categorizes logged user queries from product usage.",
    dataHint: "50+ labeled queries",
  },
  {
    id: "query_clusterer",
    label: "Query clusters",
    version: "v3",
    description: "Groups recurring search themes for knowledge-gap detection.",
    dataHint: "40+ distinct normalized queries",
  },
  {
    id: "memory_promotion_scorer",
    label: "Memory promotion",
    version: "v4",
    description: "Learns approval patterns from resolved memory promotion history.",
    dataHint: "15+ resolved promotion candidates",
  },
  {
    id: "retrieval_ranker",
    label: "Retrieval ranker",
    version: "v5",
    description: "Improves RAG ranking from chunk helpfulness feedback.",
    dataHint: "100+ scored chunk outcomes",
  },
]

export const ORG_LEARNING_MODEL_IDS = ORG_LEARNING_TRAIN_MODELS.map((model) => model.id)

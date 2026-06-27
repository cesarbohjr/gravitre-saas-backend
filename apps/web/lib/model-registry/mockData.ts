export interface ModelHealthDimension {
  key: string
  label: string
  value: number
}

export interface ModelHealthMetrics {
  dimensions: ModelHealthDimension[]
  tendency: Record<30 | 60 | 90, number[]>
  knowledgeGrowthPct: number
}

// TODO: replace with real API/data source (e.g. GET /api/models/health aggregate).
export const mockModelHealthMetrics: ModelHealthMetrics = {
  dimensions: [
    { key: "accuracy", label: "Prediction Accuracy", value: 82 },
    { key: "learning", label: "Learning Speed", value: 68 },
    { key: "consistency", label: "Consistency", value: 76 },
    { key: "dataEfficiency", label: "Data Efficiency", value: 54 },
    { key: "adaptability", label: "Adaptability", value: 71 },
    { key: "resourceUsage", label: "Resource Usage", value: 63 },
    { key: "explainability", label: "Explainability", value: 47 },
  ],
  tendency: {
    30: [58, 60, 59, 62, 64, 63, 66, 68, 67, 70, 72, 73],
    60: [49, 52, 51, 55, 57, 56, 60, 62, 64, 67, 70, 73],
    90: [41, 44, 46, 45, 50, 53, 57, 59, 63, 66, 70, 73],
  },
  knowledgeGrowthPct: 12,
}

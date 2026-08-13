import type { TrainingDatasetType } from "@/types/api"

export type DatasetTypeMeta = {
  value: TrainingDatasetType
  label: string
  summary: string
  howToAdd: string
  trainHint: string
}

export const DATASET_TYPE_META: DatasetTypeMeta[] = [
  {
    value: "examples",
    label: "Examples",
    summary: "Input and ideal answer pairs that teach how your agents should respond.",
    howToAdd: "Add pairs one at a time, paste several lines, or load starter examples.",
    trainHint: "Best for fine-tuning assistants on your tone and workflows.",
  },
  {
    value: "documents",
    label: "Documents",
    summary: "Policies, playbooks, and reference text agents should treat as source material.",
    howToAdd: "Paste document text or upload .txt / .md files into a Documents dataset.",
    trainHint: "Use when you want agents to stay faithful to written source material.",
  },
  {
    value: "feedback",
    label: "Feedback",
    summary: "Real chat ratings (helpful / not helpful) turned into training signal.",
    howToAdd: "Import recent feedback from chat, or add corrected examples manually.",
    trainHint: "Closes the loop from live usage back into better answers.",
  },
]

export function datasetTypeMeta(type: TrainingDatasetType | string | undefined): DatasetTypeMeta {
  return DATASET_TYPE_META.find((m) => m.value === type) ?? DATASET_TYPE_META[0]
}

/** Bases the Training worker can actually fine-tune today. */
export const TRAINABLE_BASE_MODELS = [
  { id: "gpt-4.1-mini", label: "GPT-4.1 mini (recommended)" },
  { id: "gpt-4.1", label: "GPT-4.1" },
] as const

export const TRAINING_STEPS = [
  {
    step: "1",
    title: "Collect teaching material",
    body: "Create a dataset: Examples for Q&A pairs, Documents for policies, or Feedback from live chat.",
  },
  {
    step: "2",
    title: "Add records",
    body: "Fill the dataset until you have enough signal. Starter examples help you begin immediately.",
  },
  {
    step: "3",
    title: "Run a training job",
    body: "Queue a fine-tune on a supported base model. Progress appears under Training jobs.",
  },
  {
    step: "4",
    title: "Apply to agents",
    body: "Assign the finished model to an agent, and keep Custom instructions on for day-to-day guidance.",
  },
] as const

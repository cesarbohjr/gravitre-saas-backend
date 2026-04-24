/**
 * FE-10: Default workflow definition for new / inline dry-run (BE-11 schema 2025.1).
 */
export const DEFAULT_WORKFLOW_DEFINITION = {
  schema_version: "2025.1",
  name: "My workflow",
  steps: [
    {
      id: "step_1",
      name: "Retrieve context",
      type: "rag_retrieve",
      config: { query_input_key: "query", top_k: 10 },
    },
    {
      id: "step_2",
      name: "Format result",
      type: "transform",
      config: { template: "Summarize the following: {{steps.step_1.output}}" },
    },
  ],
};

export function getDefaultDefinitionJson(): string {
  return JSON.stringify(DEFAULT_WORKFLOW_DEFINITION, null, 2);
}

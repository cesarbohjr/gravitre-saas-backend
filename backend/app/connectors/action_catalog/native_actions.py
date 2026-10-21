"""Native platform actions with the same canonical ActionSpec as connectors.

These are not OAuth vendors and must not create fake connector cards.
"""
from app.connectors.action_catalog.models import ActionSpec, ActionWorkflowSchema, WorkflowFieldSpec, ParameterSourceRule

GENERATE_IMAGE = ActionSpec(
    id="assistant.generate_image", name="Generate private image", tier="v2", kind="write",
    description="Generate one private draft asset through the reviewed organization provider budget. Does not publish or send it.",
    scopes=("platform:artifacts:write",), requires_approval=True, risk_class="financial",
    input_schema={"type":"object", "properties":{"prompt":{"type":"string","minLength":1,"maxLength":8000}},
                  "required":["prompt"],"additionalProperties":False},
    workflow_schema=ActionWorkflowSchema(intent_label="generate_image", required_fields=(
        WorkflowFieldSpec(label="Image prompt", arg_keys=("prompt",), inferrable=False),)),
    required_parameters=("prompt",), parameter_source_rules=(
        ParameterSourceRule(parameter="prompt", sources=("USER_EXPLICIT",), required_by_api=True, required_from_user=True),),
    availability_requirements=("current_provider_processing_permission", "reviewed_provider_budget", "private_artifact_storage"),
    provider_constraints={"provider":"openai", "n":1, "size":"1024x1024", "quality":"low", "output_format":"png"},
    governance_classification="human_approved_paid_generation", execution_adapter="assistant.generate_image",
    spec_revision="advanced-providers-v1",
)
NATIVE_ACTION_SPECS = {GENERATE_IMAGE.id: GENERATE_IMAGE}

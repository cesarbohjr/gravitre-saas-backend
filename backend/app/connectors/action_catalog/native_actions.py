"""Native platform actions with the same canonical ActionSpec as connectors.

These are not OAuth vendors and must not create fake connector cards.
"""
from app.connectors.action_catalog.models import ActionSpec, ActionWorkflowSchema, WorkflowFieldSpec, ParameterSourceRule

GENERATE_IMAGE = ActionSpec(
    id="assistant.generate_image", name="Generate private image", tier="v2", kind="write",
    description="Use when the user explicitly requests one private draft image. Generate it through the reviewed organization provider budget; does not publish or send it.",
    scopes=("platform:artifacts:write",), destructive=True, requires_approval=True, risk_class="financial",
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


# Native runtimes are platform actions, never fabricated OAuth connectors.
from app.services.native_runtime.specs import DEFINITIONS as _NATIVE_DEFINITIONS
_NATIVE_WRITES={'run_openhands':'destructive','run_browser_use':'browser_interact','approve_native_action':'browser_interact','export_evaluation_metrics':'security'}
for _name in ('run_openhands','run_browser_use','native_job_status','cancel_native_job','approve_native_action','export_evaluation_metrics','withdraw_evaluation_metrics'):
    _scope='platform:telemetry:export' if 'evaluation_metrics' in _name else 'platform:native:execute' if _name in _NATIVE_WRITES else 'platform:native:read'
    _id='assistant.'+_name
    NATIVE_ACTION_SPECS[_id]=ActionSpec(id=_id,name=_name.replace('_',' '),tier='v2',kind='write' if _name in _NATIVE_WRITES else 'read',
        description=_NATIVE_DEFINITIONS[_name][0],input_schema=_NATIVE_DEFINITIONS[_name][1],
        scopes=(_scope,),destructive=_name in _NATIVE_WRITES,requires_approval=_name in _NATIVE_WRITES,
        risk_class=_NATIVE_WRITES.get(_name,'read'),execution_adapter=_id,spec_revision='native-workers-v1')

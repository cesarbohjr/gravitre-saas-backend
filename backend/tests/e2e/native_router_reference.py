"""Isolated canonical model-router adapter for the native voice reference.

No production route, provider credentials, tenant discovery, or tool execution.
The canonical router is injected only by an authorized test caller.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ReferenceIdentity:
    org_id: str
    session_id: str
    user_id: str

class ReferenceRouterBridge:
    def __init__(self, router, identity: ReferenceIdentity, *, enabled=False, _admitted=False):
        if not enabled:
            raise PermissionError("reference router is disabled")
        if not _admitted:
            raise PermissionError("server-side conversation ownership must be verified")
        if not all((identity.org_id, identity.session_id, identity.user_id)):
            raise PermissionError("server-validated reference identity required")
        self.router = router
        self.identity = identity
        self.generation = 0
        self.closed = False
        self.history = []  # session-local, non-durable reference context
        self.pending_user = None
        self.kernel_context = None

    def cancel(self):
        self.generation += 1
        self.pending_user = None
        self.kernel_context = None

    def close(self):
        self.cancel()
        self.closed = True

    async def reason(self, prompt: str, *, kernel=None, task_state=None):
        if self.closed or not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
            raise ValueError("invalid reference turn")
        generation = self.generation = self.generation + 1
        self.kernel_context = None
        self.pending_user = prompt
        completed = False
        assistant_parts = []
        # The canonical kernel owns retrieval, intelligence and governance.
        # The isolated reference never calls ACT or an execution endpoint.
        if kernel is not None:
            from app.services.cognitive_turn_kernel import CognitiveTurnRequest
            request = CognitiveTurnRequest(
                org_id=self.identity.org_id, user_id=self.identity.user_id,
                conversation_id=self.identity.session_id, message=prompt,
                surface="voice_reference", entry_point="isolated_reference",
                environment_name="nonproduction", spoken_mode=True,
                reasoning_depth="full", task_state=task_state,
                conversation_history=[dict(turn) for turn in self.history],
            )
            context = await kernel.run_pre_act(request)
            if self.closed or generation != self.generation:
                return
            if getattr(context, "skipped", False):
                raise PermissionError("canonical cognition disabled")
            if not getattr(context, "verify", {}).get("passed", False):
                raise PermissionError("canonical verification rejected")
            if not getattr(context, "govern", {}).get("ok", False):
                raise PermissionError("canonical governance rejected")
            self.kernel_context = context
        # Import canonical TaskType, not a duplicate model routing policy.
        from app.services.model_router import TaskType
        prepared = await self.router.prepare_stream(
            TaskType.CONTENT_GENERATION, prompt,
            org_id=self.identity.org_id,
            system_prompt=("You are the isolated voice reference. Respond naturally and briefly. "
                           "You have no tools or permission to execute external actions. "
                           "Never claim that an external action was performed."),
            autonomous_run=False,
            context=[dict(turn) for turn in self.history],
        )
        if self.closed or generation != self.generation:
            return
        stream = self.router.stream(prepared)
        try:
            async for event in stream:
                if self.closed or generation != self.generation:
                    break
                if event.delta:
                    if not isinstance(event.delta, str):
                        raise TypeError("invalid router token")
                    assistant_parts.append(event.delta)
                    yield event.delta
            else:
                completed = True
        finally:
            if completed and not self.closed and generation == self.generation:
                self.history.extend([{"role": "user", "content": prompt},
                                     {"role": "assistant", "content": "".join(assistant_parts)}])
                self.history = self.history[-12:]
            if self.pending_user == prompt:
                self.pending_user = None
            close = getattr(stream, "aclose", None)
            if close is not None:
                await close()

async def admit_reference(router, identity: ReferenceIdentity, *, authenticated_user_id: str,
                          lookup_conversation, enabled=False):
    """Fail-closed reference admission using a server-owned scoped lookup.

    lookup_conversation must execute an authenticated, org-scoped database query
    and return the matching row, or None. It must not trust client-supplied rows.
    """
    if not enabled:
        raise PermissionError("reference disabled")
    if not all((identity.org_id, identity.session_id, identity.user_id)):
        raise PermissionError("invalid session binding")
    if authenticated_user_id != identity.user_id:
        raise PermissionError("authenticated principal mismatch")
    row = await lookup_conversation(identity.org_id, identity.session_id, authenticated_user_id)
    if not isinstance(row, dict) or any(
        row.get(field) != expected for field, expected in (
            ("id", identity.session_id), ("org_id", identity.org_id),
            ("user_id", authenticated_user_id)
        )
    ):
        raise PermissionError("conversation ownership not established")
    return ReferenceRouterBridge(router, identity, enabled=True, _admitted=True)

async def admit_from_authenticated_client(router, identity: ReferenceIdentity, *,
                                         authenticated_user_id: str, client, enabled=False):
    """Use the authenticated request's DB client, not service-role credentials.

    The caller must supply the client from its validated server request context.
    This function does not accept an ownership boolean or client-supplied row.
    """
    from app.core.io_pool import run_io

    async def lookup(org_id, conversation_id, user_id):
        query = (client.table("conversations")
                 .select("id,org_id,user_id")
                 .eq("id", conversation_id)
                 .eq("org_id", org_id)
                 .eq("user_id", user_id)
                 .limit(1))
        response = await run_io(query.execute)
        rows = response.data or []
        return rows[0] if len(rows) == 1 else None

    return await admit_reference(
        router, identity, authenticated_user_id=authenticated_user_id,
        lookup_conversation=lookup, enabled=enabled,
    )

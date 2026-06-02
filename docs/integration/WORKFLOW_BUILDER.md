# Workflow builder persistence (STA-19)

The visual builder at `/workflows/[id]/builder` persists to the backend and runs through the real execute path.

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/workflows/{id}/builder` | Load nodes + edges + workflow meta |
| PUT | `/api/workflows/{id}/builder` | Save graph, compile `workflow_defs.definition`, publish active version |
| POST | `/api/workflows/execute` | Run active version (`{ workflow_id, parameters }`) |

Save compiles the canvas into step definitions (`agent`, `slack_post_message`, `noop`, etc.) and creates a new active `workflow_versions` row.

## Frontend

- `apps/web/lib/workflows/builder-persistence.ts` — load/save/execute helpers
- `apps/web/app/workflows/[id]/builder/page.tsx` — Save + Run wired (UUID workflow ids)

Demo / local ids like `new` still use the in-browser simulation until a workflow is created from `/workflows`.

## Code

- `backend/app/workflows/builder_sync.py`
- `backend/app/routers/workflows.py` — `PUT /{workflow_id}/builder`

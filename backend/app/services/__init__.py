"""Service layer package.

Import concrete modules directly (e.g. ``app.services.tool_service``). Avoid
eager re-exports here — loading execution/tool services during package init
creates a circular import with ``app.connectors.repository``.
"""

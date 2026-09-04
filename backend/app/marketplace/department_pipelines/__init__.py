"""Named department pipelines — assembly of existing Gravitre capability (Katie-style UX)."""

from app.marketplace.department_pipelines.catalog import (
    DEPARTMENT_PIPELINE_IDS,
    get_department_pipeline,
    list_department_pipelines,
)


def __getattr__(name: str):
    if name == "DepartmentPipelineService":
        from app.marketplace.department_pipelines.service import DepartmentPipelineService

        return DepartmentPipelineService
    raise AttributeError(name)

__all__ = [
    "DEPARTMENT_PIPELINE_IDS",
    "DepartmentPipelineService",
    "get_department_pipeline",
    "list_department_pipelines",
]

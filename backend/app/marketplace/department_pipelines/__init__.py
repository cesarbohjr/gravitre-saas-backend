"""Named department pipelines — assembly of existing Gravitre capability (Katie-style UX)."""

from app.marketplace.department_pipelines.catalog import (
    DEPARTMENT_PIPELINE_IDS,
    get_department_pipeline,
    list_department_pipelines,
)
from app.marketplace.department_pipelines.service import DepartmentPipelineService

__all__ = [
    "DEPARTMENT_PIPELINE_IDS",
    "DepartmentPipelineService",
    "get_department_pipeline",
    "list_department_pipelines",
]

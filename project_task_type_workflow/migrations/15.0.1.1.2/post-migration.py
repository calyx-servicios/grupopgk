from typing import Any

from odoo import SUPERUSER_ID, api
from odoo.addons.project_task_type_workflow.hooks import (
    backfill_subtask_projects,
)


def migrate(cr: Any, version: str) -> None:
    """Populate missing subtask project fields at every existing level."""
    backfill_subtask_projects(api.Environment(cr, SUPERUSER_ID, {}))
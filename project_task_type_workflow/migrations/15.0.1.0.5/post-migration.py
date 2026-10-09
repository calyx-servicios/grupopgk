from typing import Any

from odoo import SUPERUSER_ID, api
from odoo.addons.project_task_type_workflow.hooks import (
    initialize_development_permissions,
)


def migrate(cr: Any, version: str) -> None:
    """Populate policies on existing noupdate stages during this upgrade."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    initialize_development_permissions(env)
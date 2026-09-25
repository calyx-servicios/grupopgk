from odoo.api import Environment, SUPERUSER_ID

from .models.project_task_type import CANONICAL_STAGE_XMLIDS


def _get_canonical_stages(env):
    """Return the canonical stage records, resolved from their fixed xmlids."""
    module = "project_task_type_workflow"
    stages = env["project.task.type"]
    for xmlid in CANONICAL_STAGE_XMLIDS:
        stages |= env.ref(f"{module}.{xmlid}", raise_if_not_found=False) or stages
    return stages


def post_init_hook(cr, registry):
    """Link the canonical stages to every existing project's task stages."""
    env = Environment(cr, SUPERUSER_ID, {})
    stages = _get_canonical_stages(env)
    projects = env["project.project"].search([])
    if stages and projects:
        stages.write({"project_ids": [(4, project.id) for project in projects]})

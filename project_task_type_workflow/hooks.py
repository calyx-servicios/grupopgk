from odoo.api import Environment, SUPERUSER_ID

from .models.project_task_type import (
    CANONICAL_STAGE_XMLIDS,
    DEVELOPMENT_STAGE_ROLES,
    WORKFLOW_ROLES,
)


def backfill_subtask_projects(env: Environment) -> None:
    """Fill missing actual/visible projects without moving existing tasks."""
    env["project.task"].flush(["parent_id", "project_id", "display_project_id"])
    env.cr.execute("""
        WITH RECURSIVE inherited_projects AS (
            SELECT id, project_id
              FROM project_task
             WHERE parent_id IS NULL
            UNION ALL
            SELECT child.id, COALESCE(child.project_id, parent.project_id)
              FROM project_task child
              JOIN inherited_projects parent ON child.parent_id = parent.id
        )
        UPDATE project_task task
           SET project_id = COALESCE(task.project_id, inherited.project_id),
               display_project_id = COALESCE(
                   task.display_project_id, inherited.project_id
               )
          FROM inherited_projects inherited
         WHERE task.id = inherited.id
           AND task.parent_id IS NOT NULL
           AND inherited.project_id IS NOT NULL
           AND (task.project_id IS NULL OR task.display_project_id IS NULL)
    """)
    env["project.task"].invalidate_cache([
        "project_id", "display_project_id",
    ])


def initialize_development_permissions(env: Environment) -> None:
    """Seed policies once when upgrading from the version without roles."""
    for xmlid, roles in DEVELOPMENT_STAGE_ROLES.items():
        stage = env.ref(
            f"project_task_type_workflow.{xmlid}",
            raise_if_not_found=False,
        )
        if stage:
            stage.write({
                f"workflow_allow_{role}": role in roles
                for role in WORKFLOW_ROLES
            })


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

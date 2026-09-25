from odoo import api, models

from .project_task_type import CANONICAL_STAGE_XMLIDS


class ProjectProject(models.Model):
    """Auto-link the canonical task-type stages to newly created projects."""

    _inherit = "project.project"

    def _get_canonical_stage_ids(self):
        """Resolve the canonical stages from their fixed xmlids."""
        stages = self.env["project.task.type"]
        for xmlid in CANONICAL_STAGE_XMLIDS:
            stage = self.env.ref(
                f"project_task_type_workflow.{xmlid}", raise_if_not_found=False
            )
            if stage:
                stages |= stage
        return stages

    @api.model
    def create(self, vals):
        project = super().create(vals)
        stages = self._get_canonical_stage_ids()
        if stages:
            stages.write({"project_ids": [(4, project.id)]})
        return project

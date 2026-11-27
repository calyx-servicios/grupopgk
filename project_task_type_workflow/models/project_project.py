from typing import Any, Dict, Set

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .project_task_type import CANONICAL_STAGE_XMLIDS


PROJECT_WORKFLOW_FIELDS = {
    "scrum_master": "workflow_scrum_master_ids",
    "functional": "workflow_functional_ids",
    "developer": "workflow_developer_ids",
    "deployer": "workflow_deployer_ids",
}


class ProjectProject(models.Model):
    """Auto-link the canonical task-type stages to newly created projects."""

    _inherit = "project.project"

    workflow_scrum_master_ids = fields.Many2many(
        "res.users", "project_workflow_scrum_rel", "project_id", "user_id",
        string="Scrum Masters", domain=[("share", "=", False)],
    )
    workflow_functional_ids = fields.Many2many(
        "res.users", "project_workflow_functional_rel", "project_id",
        "user_id", string="Funcionales", domain=[("share", "=", False)],
    )
    workflow_developer_ids = fields.Many2many(
        "res.users", "project_workflow_dev_rel", "project_id", "user_id",
        string="Desarrolladores", domain=[("share", "=", False)],
    )
    workflow_deployer_ids = fields.Many2many(
        "res.users", "project_workflow_deploy_rel", "project_id", "user_id",
        string="Deployers", domain=[("share", "=", False)],
    )
    workflow_configuration_allowed = fields.Boolean(
        compute="_compute_workflow_configuration_allowed",
    )

    @api.depends_context("uid")
    def _compute_workflow_configuration_allowed(self) -> None:
        """Expose configuration permissions without granting task movement."""
        allowed = self.env.su or self.env.user.has_group(
            "project.group_project_manager"
        )
        for project in self:
            project.workflow_configuration_allowed = allowed

    def _get_workflow_pm(self) -> models.Model:
        """Resolve the project PM, preferring the Calyx assignment."""
        self.ensure_one()
        if (
            "calyx_project_manager_id" in self._fields
            and self.calyx_project_manager_id
        ):
            return self.calyx_project_manager_id
        return self.user_id

    def _get_user_workflow_roles(self) -> Set[str]:
        """Resolve all roles of the current user in this project."""
        self.ensure_one()
        roles = set()
        if self.env.user == self._get_workflow_pm():
            roles.add("pm")
        if self.env.user == self.technical_leader_id:
            roles.add("technical_leader")
        for role, field_name in PROJECT_WORKFLOW_FIELDS.items():
            if self.env.user in self[field_name]:
                roles.add(role)
        return roles

    def _check_workflow_assignments(self, vals: Dict[str, Any]) -> None:
        """Prevent ordinary users from granting themselves project roles."""
        protected = set(PROJECT_WORKFLOW_FIELDS.values()) | {
            "user_id", "technical_leader_id", "calyx_project_manager_id",
        }
        if protected.intersection(vals) and not (
            self.env.su
            or self.env.user.has_group("project.group_project_manager")
        ):
            raise AccessError(_(
                "Solo los administradores de Proyectos pueden modificar "
                "las asignaciones de roles del proyecto."
            ))

    @api.constrains(*PROJECT_WORKFLOW_FIELDS.values())
    def _check_workflow_internal_users(self) -> None:
        """Reject portal users even when assigned through RPC or import."""
        for project in self:
            for field_name in PROJECT_WORKFLOW_FIELDS.values():
                if any(project[field_name].mapped("share")):
                    raise ValidationError(_(
                        "Los roles del circuito requieren usuarios internos."
                    ))

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
    def create(self, vals: Dict[str, Any]) -> models.Model:
        """Protect explicit role assignments and link canonical stages."""
        self._check_workflow_assignments(vals)
        project = super().create(vals)
        stages = self._get_canonical_stage_ids()
        if stages:
            stages.write({"project_ids": [(4, project.id)]})
        return project

    def write(self, vals: Dict[str, Any]) -> bool:
        """Protect every role source, including the existing PM and leader."""
        self._check_workflow_assignments(vals)
        return super().write(vals)

from typing import Any, Dict, List, Set

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


WORKFLOW_ROLES = {
    "pm": "PM",
    "technical_leader": "Líder Técnico",
    "scrum_master": "Scrum Master",
    "functional": "Funcional",
    "developer": "Dev",
    "deployer": "Deployer",
}

DEVELOPMENT_STAGE_ROLES = {
    "stage_pendiente_development": (
        "pm", "technical_leader", "scrum_master", "functional",
    ),
    "stage_estimacion": (
        "pm", "technical_leader", "scrum_master", "functional",
    ),
    "stage_desestimada": ("pm", "technical_leader", "scrum_master"),
    "stage_lista_para_hacer": ("pm", "technical_leader", "scrum_master"),
    "stage_desarrollo": ("developer", "technical_leader"),
    "stage_suspendida": ("pm", "technical_leader"),
    "stage_deploy_staging": ("deployer", "technical_leader"),
    "stage_deploy_failed_staging": ("developer", "technical_leader"),
    "stage_pruebas": ("functional",),
    "stage_testing_failed": ("developer", "technical_leader"),
    "stage_testing_ok": ("functional",),
    "stage_uat_cliente": ("functional",),
    "stage_deploy_produccion": ("deployer", "technical_leader"),
    "stage_deploy_failed_produccion": ("developer", "technical_leader"),
    "stage_revision_general_funcional": ("functional",),
    "stage_finalizada_development": ("pm", "technical_leader"),
}

# Canonical stages seeded by data/project_task_type_data.xml, auto-linked to every
# project so they're selectable regardless of which projects created them first.
CANONICAL_STAGE_XMLIDS = [
    "stage_pendiente_functional",
    "stage_en_curso",
    "stage_finalizada_functional",
    "stage_pendiente_development",
    "stage_estimacion",
    "stage_desestimada",
    "stage_lista_para_hacer",
    "stage_desarrollo",
    "stage_suspendida",
    "stage_deploy_staging",
    "stage_deploy_failed_staging",
    "stage_pruebas",
    "stage_testing_failed",
    "stage_testing_ok",
    "stage_uat_cliente",
    "stage_deploy_produccion",
    "stage_deploy_failed_produccion",
    "stage_revision_general_funcional",
    "stage_finalizada_development",
]


class ProjectTaskType(models.Model):
    """Classify which task types (Gestión/Funcional, Desarrollo) may use each stage."""

    _inherit = "project.task.type"

    task_type_scope = fields.Selection(
        selection=[
            ("functional", "Gestión/Funcional"),
            ("development", "Desarrollo"),
        ],
        string="Tipo de tarea habilitado",
        help="Determina para qué tipo de tarea está disponible este estado.",
    )
    workflow_allow_pm = fields.Boolean(string="PM")
    workflow_allow_technical_leader = fields.Boolean(string="Líder Técnico")
    workflow_allow_scrum_master = fields.Boolean(string="Scrum Master")
    workflow_allow_functional = fields.Boolean(string="Funcional")
    workflow_allow_developer = fields.Boolean(string="Dev")
    workflow_allow_deployer = fields.Boolean(string="Deployer")
    workflow_configuration_allowed = fields.Boolean(
        compute="_compute_workflow_configuration_allowed",
    )

    @api.depends_context("uid")
    def _compute_workflow_configuration_allowed(self) -> None:
        """Expose policy editing rights to the native stage form."""
        allowed = self.env.su or self.env.user.has_group(
            "project.group_project_manager"
        )
        for stage in self:
            stage.workflow_configuration_allowed = allowed

    def _get_workflow_roles(self) -> Set[str]:
        """Return the roles explicitly allowed to leave this stage."""
        self.ensure_one()
        return {
            role for role in WORKFLOW_ROLES
            if self[f"workflow_allow_{role}"]
        }

    def _check_workflow_configuration(self, vals: Dict[str, Any]) -> None:
        """Reserve workflow policy changes for project administrators."""
        protected = {f"workflow_allow_{role}" for role in WORKFLOW_ROLES}
        protected.add("task_type_scope")
        if protected.intersection(vals) and not (
            self.env.su
            or self.env.user.has_group("project.group_project_manager")
        ):
            raise AccessError(_(
                "Solo los administradores de Proyectos pueden configurar "
                "los permisos del circuito."
            ))

    @api.model_create_multi
    def create(self, vals_list: List[Dict[str, Any]]) -> models.Model:
        """Check policy administration before creating stages."""
        for vals in vals_list:
            self._check_workflow_configuration(vals)
        return super().create(vals_list)

    def write(self, vals: Dict[str, Any]) -> bool:
        """Check policy administration before updating stages."""
        self._check_workflow_configuration(vals)
        return super().write(vals)

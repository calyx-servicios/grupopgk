from typing import Any, Dict, Set

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .project_task_type import WORKFLOW_ROLES

# xmlids of the canonical "Pendiente" stage per task type (see
# data/project_task_type_data.xml), used to detect a backward move to it.
PENDIENTE_STAGE_XMLIDS = {
    "functional": "project_task_type_workflow.stage_pendiente_functional",
    "development": "project_task_type_workflow.stage_pendiente_development",
}


class ProjectTask(models.Model):
    """Classify tasks by type to restrict their available stages."""

    _inherit = "project.task"

    task_type = fields.Selection(
        selection=[
            ("unclassified", "Sin clasificar"),
            ("functional", "Gestión/Funcional"),
            ("development", "Desarrollo"),
        ],
        string="Tipo de tarea",
        default="unclassified",
        required=True,
        tracking=True,
        help="Determina el circuito de estados disponible y el responsable "
        "jerárquico máximo de la tarea.",
    )
    max_responsible_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsable jerárquico máximo",
        compute="_compute_max_responsible_id",
        help="PM para tareas de Gestión/Funcional, Líder Técnico para tareas de Desarrollo.",
    )

    @api.onchange("project_id", "task_type")
    def _onchange_task_type_stage_domain(self):
        """Offer only stages enabled for the selected task type in the UI."""
        domain = [("project_ids", "=", self.project_id.id)] if self.project_id else []
        domain += [("task_type_scope", "=", self.task_type)]
        return {"domain": {"stage_id": domain}}

    @api.depends("task_type", "project_id.user_id", "project_id.technical_leader_id")
    def _compute_max_responsible_id(self):
        """Identify the top hierarchical responsible according to the task type."""
        for task in self:
            if task.task_type == "functional":
                task.max_responsible_id = task.project_id.user_id
            elif task.task_type == "development":
                task.max_responsible_id = task.project_id.technical_leader_id
            else:
                task.max_responsible_id = False

    def _get_pendiente_stage(self, task_type):
        """Return the canonical "Pendiente" stage for a given task type."""
        xmlid = PENDIENTE_STAGE_XMLIDS.get(task_type)
        if not xmlid:
            return self.env["project.task.type"]
        return self.env.ref(xmlid, raise_if_not_found=False) or self.env["project.task.type"]

    def _get_authorized_users(self):
        """Return the project PM and technical leader allowed to reopen a task."""
        self.ensure_one()
        project = self.project_id
        if not project:
            return self.env["res.users"]
        return project._get_workflow_pm() | project.technical_leader_id

    def _check_reopen_to_pendiente(self, vals):
        """Block moving a started task back to "Pendiente" unless done by its PM."""
        if not vals.get("stage_id"):
            return
        new_stage = self.env["project.task.type"].browse(vals["stage_id"])
        blocked_tasks = self.env["project.task"]
        for task in self:
            if task.task_type != "functional" or new_stage == task.stage_id:
                continue
            pendiente_stage = task._get_pendiente_stage(task.task_type)
            if not pendiente_stage or new_stage != pendiente_stage:
                continue
            if task.stage_id.sequence <= pendiente_stage.sequence:
                continue
            if self.env.user not in task._get_authorized_users():
                blocked_tasks |= task
        if blocked_tasks:
            raise UserError(_(
                "Solo el PM o el Líder Técnico del proyecto pueden volver a "
                "mover a «Pendiente» "
                "las siguientes tareas ya iniciadas: %s"
            ) % ", ".join(blocked_tasks.mapped("name")))

    def _workflow_stage(self, xmlid: str) -> models.Model:
        """Resolve special stages by identity, never by translated names."""
        return self.env.ref(
            f"project_task_type_workflow.{xmlid}",
            raise_if_not_found=False,
        ) or self.env["project.task.type"]

    def _workflow_move_error(
        self, destination: models.Model, roles: Set[str],
    ) -> None:
        """Report the denied movement without mutating any task."""
        self.ensure_one()
        labels = ", ".join(
            _(label) for role, label in WORKFLOW_ROLES.items()
            if role in roles
        ) or _("Ningún rol configurado")
        raise UserError(_(
            "No tiene permiso para mover la tarea «%(task)s» desde "
            "«%(origin)s» hacia «%(destination)s». "
            "Roles habilitados: %(roles)s."
        ) % {
            "task": self.display_name,
            "origin": self.stage_id.name or _("Sin etapa"),
            "destination": destination.name or _("Sin etapa"),
            "roles": labels,
        })

    def _check_development_move(
        self, destination: models.Model, vals: Dict[str, Any],
    ) -> None:
        """Authorize one move against the original project and assignees."""
        self.ensure_one()
        target_type = vals.get("task_type", self.task_type)
        target_project = self.env["project.project"].browse(
            vals.get("project_id", self.project_id.id)
        )
        if not destination:
            self._workflow_move_error(destination, set())
        if (
            destination.task_type_scope != target_type
            or target_project not in destination.project_ids
        ):
            raise ValidationError(_(
                "La etapa de destino no está habilitada para el tipo "
                "de tarea y el proyecto seleccionados."
            ))

        roles = (
            self.project_id._get_user_workflow_roles()
            if self.project_id else set()
        )
        leaders = {"pm", "technical_leader"}
        if self.task_type != "development":
            if not roles.intersection(leaders):
                self._workflow_move_error(destination, leaders)
            return
        if destination == self._workflow_stage("stage_suspendida"):
            if (
                not roles.intersection(leaders)
                and self.env.user not in self.user_ids
            ):
                raise UserError(_(
                    "Solo el PM, el Líder Técnico o un responsable "
                    "actual pueden suspender la tarea «%s»."
                ) % self.display_name)
            return
        if destination == self._get_pendiente_stage("development"):
            if not roles.intersection(leaders):
                self._workflow_move_error(destination, leaders)
            return

        permitted = (
            self.stage_id._get_workflow_roles()
            if self.stage_id else set()
        )
        if not roles.intersection(permitted):
            self._workflow_move_error(destination, permitted)
        if self.stage_id == self._workflow_stage("stage_pruebas"):
            testing_stages = (
                self._workflow_stage("stage_testing_ok")
                | self._workflow_stage("stage_testing_failed")
            )
            if destination not in testing_stages:
                raise UserError(_(
                    "Desde Pruebas solo se puede mover a Testing OK o "
                    "Testing Failed, salvo las excepciones de retorno "
                    "a Pendiente o pase a Suspendida."
                ))

    def _check_development_workflow(self, vals: Dict[str, Any]) -> None:
        """Validate the complete batch before any state is written."""
        for task in self:
            target_type = vals.get("task_type", task.task_type)
            if "development" not in (task.task_type, target_type):
                continue
            if (
                task.task_type == "development"
                and "project_id" in vals
                and vals["project_id"] != task.project_id.id
                and self.env.user not in task._get_authorized_users()
            ):
                raise UserError(_(
                    "Solo el PM o el Líder Técnico pueden cambiar el "
                    "proyecto de la tarea de Desarrollo «%s»."
                ) % task.display_name)
            if (
                task.task_type == "development"
                and target_type != "development"
                and self.env.user not in task._get_authorized_users()
            ):
                raise UserError(_(
                    "Solo el PM o el Líder Técnico pueden sacar la tarea "
                    "«%s» del circuito de Desarrollo."
                ) % task.display_name)
            if "stage_id" not in vals:
                continue
            destination = self.env["project.task.type"].browse(
                vals["stage_id"]
            ).exists()
            if destination == task.stage_id:
                continue
            task._check_development_move(destination, vals)

    def write(self, vals: Dict[str, Any]) -> bool:
        """Enforce development permissions and preserve functional reopening."""
        self._check_development_workflow(vals)
        self._check_reopen_to_pendiente(vals)
        return super().write(vals)

    @api.constrains("task_type", "stage_id")
    def _check_stage_matches_task_type(self):
        """Block moving a task to a stage outside its task type's allowed set."""
        for task in self:
            if task.task_type == "unclassified" or not task.stage_id:
                continue
            if task.stage_id.task_type_scope != task.task_type:
                raise ValidationError(_(
                    "El estado «%(stage)s» no está habilitado para el tipo de "
                    "tarea «%(task_type)s»."
                ) % {
                    "stage": task.stage_id.name,
                    "task_type": dict(
                        task._fields["task_type"].selection
                    )[task.task_type],
                })

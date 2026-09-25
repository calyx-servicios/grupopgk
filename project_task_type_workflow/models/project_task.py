from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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

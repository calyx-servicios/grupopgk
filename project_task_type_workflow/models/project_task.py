from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

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

    def _get_authorized_pm(self):
        """Return the user allowed to reopen this task's project to "Pendiente"."""
        self.ensure_one()
        project = self.project_id
        if "calyx_project_manager_id" in project._fields and project.calyx_project_manager_id:
            return project.calyx_project_manager_id
        return project.user_id

    def _check_reopen_to_pendiente(self, vals):
        """Block moving a started task back to "Pendiente" unless done by its PM."""
        if not vals.get("stage_id") or self.env.su:
            return
        if self.env.user.has_group("project.group_project_manager"):
            return
        new_stage = self.env["project.task.type"].browse(vals["stage_id"])
        blocked_tasks = self.env["project.task"]
        for task in self:
            if task.task_type not in ("functional", "development"):
                continue
            pendiente_stage = task._get_pendiente_stage(task.task_type)
            if not pendiente_stage or new_stage != pendiente_stage:
                continue
            if task.stage_id.sequence <= pendiente_stage.sequence:
                continue
            if task._get_authorized_pm() != self.env.user:
                blocked_tasks |= task
        if blocked_tasks:
            raise UserError(_(
                "Solo el PM del proyecto puede volver a mover a «Pendiente» "
                "las siguientes tareas ya iniciadas: %s"
            ) % ", ".join(blocked_tasks.mapped("name")))

    def write(self, vals):
        """Restrict reopening an in-progress task back to "Pendiente" to its PM."""
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

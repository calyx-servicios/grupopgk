from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.float_utils import float_compare


class ProjectTask(models.Model):
    """Enforce the Configuraciones task hierarchy and its hour caps."""

    _inherit = "project.task"

    config_level = fields.Integer(
        string="Nivel de Configuración",
        compute="_compute_config_level",
        store=True,
        recursive=True,
    )
    config_available_hours = fields.Float(
        string="Horas disponibles de la bolsa",
        compute="_compute_config_available_hours",
    )
    @api.depends(
        "is_calyx_sale_root",
        "parent_id",
        "parent_id.config_level",
    )
    def _compute_config_level(self):
        """Compute hierarchy depth for Calyx roots and their descendants."""
        for task in self:
            if task.is_calyx_sale_root:
                task.config_level = 1
            elif task.parent_id.config_level:
                task.config_level = task.parent_id.config_level + 1
            else:
                task.config_level = 0

    @api.depends("config_level", "hours_cap", "parent_id")
    def _compute_config_available_hours(self):
        """Show the remaining root allowance on levels three and four."""
        for task in self:
            root = task._get_configuration_root()
            if root and task.config_level in (3, 4):
                task.config_available_hours = (
                    root.hours_cap - root._get_total_consumed_hours()
                )
            else:
                task.config_available_hours = 0.0

    def _get_configuration_root(self):
        """Return the Calyx root task containing this task, if any."""
        self.ensure_one()
        task = self
        while task and not task.is_calyx_sale_root:
            task = task.parent_id
        return task or self.env["project.task"]

    def _is_configuration_manager(self, project):
        """Check project PM or project-manager group membership."""
        if self.env.su or self.env.user.has_group("project.group_project_manager"):
            return True
        manager = (
            project.calyx_project_manager_id
            if "calyx_project_manager_id" in project._fields
            else self.env["res.users"]
        )
        return bool(manager and manager == self.env.user)

    @api.model_create_multi
    def create(self, vals_list):
        """Restrict creation of module and activity levels to project PMs."""
        Task = self.env["project.task"]
        for values in vals_list:
            parent = Task.browse(values.get("parent_id")).exists()
            if parent.config_level in (1, 2):
                if not self._is_configuration_manager(parent.project_id):
                    raise AccessError(_(
                        "Solo el PM del proyecto puede crear módulos y "
                        "tareas de actividad en Configuraciones."
                    ))
            if parent.config_level == 2 and float_compare(
                values.get("hours_cap", 0.0),
                0.0,
                precision_digits=2,
            ) <= 0:
                raise ValidationError(_(
                    "La tarea de nivel 3 debe tener un tope de horas mayor "
                    "que cero."
                ))
        tasks = super().create(vals_list)
        tasks._check_configuration_hierarchy()
        return tasks

    def write(self, values):
        """Protect hierarchy caps and validate structural changes."""
        hierarchy_tasks = self.filtered("config_level")
        if "hours_cap" in values and hierarchy_tasks:
            privileged = self.env.su or self.env.user.has_group(
                "project_hours_request.group_project_hours_request_contratos"
            )
            approved_root_request = bool(
                self.env.context.get("hours_request_workflow")
                and hierarchy_tasks.filtered(lambda task: task.config_level == 1)
            )
            if not privileged and not approved_root_request:
                raise AccessError(_(
                    "El tope de horas de Configuraciones solo puede ajustarlo "
                    "Contratos."
                ))
        if "parent_id" in values and hierarchy_tasks:
            target_parent = self.env["project.task"].browse(
                values.get("parent_id")
            ).exists()
            if target_parent.config_level and not self._is_configuration_manager(
                target_parent.project_id
            ):
                raise AccessError(_(
                    "Solo el PM del proyecto puede reorganizar tareas de "
                    "Configuraciones."
                ))
        result = super().write(values)
        if {"parent_id", "hours_cap"}.intersection(values):
            self._check_configuration_hierarchy()
            roots = self.env["project.task"]
            for task in self:
                roots |= task._get_configuration_root()
            lines = self.env["account.analytic.line"].search([
                ("task_id", "child_of", roots.ids),
            ]) if roots else self.env["account.analytic.line"]
            lines._validate_configuration_caps()
        return result

    @api.constrains("parent_id", "is_calyx_sale_root", "config_level", "hours_cap")
    def _check_configuration_hierarchy(self):
        """Reject depth five and invalid level-three hour caps."""
        for task in self:
            if task.config_level > 4:
                raise ValidationError(_(
                    "No se pueden crear subtareas dentro del nivel 4 de "
                    "Configuraciones."
                ))
            if task.config_level in (1, 2, 3) and task.hours_cap < 0:
                raise ValidationError(_(
                    "El tope de horas no puede ser negativo."
                ))
            if task.config_level == 3 and float_compare(
                task.hours_cap,
                0.0,
                precision_digits=2,
            ) <= 0:
                raise ValidationError(_(
                    "La tarea de nivel 3 debe tener un tope de horas mayor "
                    "que cero."
                ))
            if task.config_level == 4 and task.hours_cap:
                raise ValidationError(_(
                    "Las subtareas de nivel 4 no tienen un tope propio."
                ))
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProjectTask(models.Model):
    """Representa la bolsa de horas de una línea de venta Calyx."""

    _inherit = "project.task"

    is_calyx_sale_root = fields.Boolean(
        string="Tarea raíz Calyx",
        copy=False,
        index=True,
    )
    calyx_budget_hours = fields.Float(
        string="Horas contratadas",
        copy=False,
        readonly=True,
    )
    calyx_allocated_hours = fields.Float(
        string="Horas asignadas",
        compute="_compute_calyx_hours",
    )
    calyx_remaining_hours = fields.Float(
        string="Horas restantes",
        compute="_compute_calyx_hours",
    )

    @api.depends(
        "calyx_budget_hours",
        "child_ids.active",
        "child_ids.planned_hours",
    )
    def _compute_calyx_hours(self):
        """Calcula asignado y restante desde las tareas hijas activas."""
        for task in self:
            allocated = sum(task.child_ids.filtered("active").mapped("planned_hours"))
            task.calyx_allocated_hours = allocated
            task.calyx_remaining_hours = task.calyx_budget_hours - allocated

    def write(self, values):
        """Impide editar manualmente la raíz contractual Calyx."""
        protected = {
            "active",
            "calyx_budget_hours",
            "is_calyx_sale_root",
            "parent_id",
            "planned_hours",
            "project_id",
            "sale_line_id",
            "user_ids",
        }
        roots = self.filtered("is_calyx_sale_root")
        technical = bool(
            self.env.su and self.env.context.get("calyx_sale_project_generation")
        )
        if roots and protected.intersection(values) and not technical:
            raise AccessError("La tarea raíz Calyx no puede editarse directamente.")
        return super().write(values)

    def unlink(self):
        """Impide eliminar manualmente la raíz contractual Calyx."""
        roots = self.filtered("is_calyx_sale_root")
        technical = bool(
            self.env.su and self.env.context.get("calyx_sale_project_generation")
        )
        if roots and not technical:
            raise AccessError("La tarea raíz Calyx no puede eliminarse.")
        return super().unlink()

    @api.constrains("is_calyx_sale_root", "parent_id")
    def _check_calyx_sale_root(self):
        """Evita convertir una raíz Calyx en subtarea."""
        invalid = self.filtered(lambda task: task.is_calyx_sale_root and task.parent_id)
        if invalid:
            raise ValidationError("Una tarea raíz Calyx no puede tener tarea padre.")

from odoo import _, api, models
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    """Bloquea partes de horas sobre la tarea raíz contractual Calyx."""

    _inherit = "account.analytic.line"

    @api.model
    def _check_calyx_sale_root(self, values):
        """Rechaza partes apuntadas a una raíz contractual."""
        task = self.env["project.task"].browse(values.get("task_id"))
        if task.is_calyx_sale_root:
            raise UserError(_("No se pueden cargar horas en la tarea raíz Calyx."))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._check_calyx_sale_root(values)
        return super().create(vals_list)

    def write(self, values):
        if values.get("task_id"):
            self._check_calyx_sale_root(values)
        return super().write(values)

from odoo import models


class SaleOrderLine(models.Model):
    """Seed Calyx root task caps from the confirmed contract budget."""

    _inherit = "sale.order.line"

    def _calyx_prepare_root_task_values(self, project):
        """Include the contracted budget as the root task's global cap."""
        values = super()._calyx_prepare_root_task_values(project)
        values["hours_cap"] = self.contrated_hours
        return values
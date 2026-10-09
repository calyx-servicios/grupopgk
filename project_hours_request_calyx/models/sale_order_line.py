from typing import Any, Dict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class SaleOrderLine(models.Model):
    """Reserve part of a Calyx service line for UAT without repricing it."""

    _inherit = "sale.order.line"

    uat_support_hours = fields.Float(string="Horas UAT/Soporte")

    @api.constrains(
        "uat_support_hours", "contrated_hours", "product_id", "order_id",
    )
    def _check_uat_support_hours(self) -> None:
        """Keep the commercial reservation within contracted hours."""
        for line in self:
            if line.uat_support_hours < 0:
                raise ValidationError(_("UAT/Soporte no puede ser negativo."))
            if not line.uat_support_hours:
                continue
            if not line._calyx_uses_sale_project_flow():
                raise ValidationError(_(
                    "La previsión UAT requiere un servicio de venta Calyx."
                ))
            if float_compare(
                line.uat_support_hours, line.contrated_hours,
                precision_digits=2,
            ) > 0:
                raise ValidationError(_(
                    "UAT/Soporte es parte de las horas contratadas y no "
                    "puede superar su total."
                ))

    def _calyx_prepare_root_task_values(self, project: Any) -> Dict[str, Any]:
        """Copy the quotation reservation without using task estimates."""
        values = super()._calyx_prepare_root_task_values(project)
        values["calyx_uat_budget_hours"] = self.uat_support_hours
        values["calyx_uat_quote_snapshot"] = True
        return values

    def write(self, values: Dict[str, Any]) -> Any:
        """Freeze the quoted reservation after confirming a Calyx order."""
        if "uat_support_hours" in values and self.filtered(
            lambda line: line._calyx_uses_sale_project_flow()
            and line.order_id.state in ("sale", "done")
        ):
            raise ValidationError(_(
                "No puede cambiar la previsión UAT de una venta confirmada."
            ))
        return super().write(values)
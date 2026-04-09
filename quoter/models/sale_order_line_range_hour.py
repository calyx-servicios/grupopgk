# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderLineRangeHour(models.Model):
    _name = "sale.order.line.range.hour"
    _description = "Horas por rango en línea de pedido (cotizador)"
    _order = "area_range_sequence, id"

    sale_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Línea de pedido",
        required=True,
        ondelete="cascade",
        index=True,
    )

    area_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rango del área",
        required=True,
        ondelete="cascade",
        index=True,
    )

    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )

    hours = fields.Float(string="Horas", default=0.0)

    _sql_constraints = [
        (
            "uniq_sale_line_area_range",
            "UNIQUE(sale_line_id, area_range_id)",
            "Ya hay horas cargadas para ese rango en esta línea.",
        )
    ]

    @api.constrains("area_range_id", "sale_line_id")
    def _check_range_belongs_to_line_area(self):
        for row in self:
            area = row.sale_line_id.quoter_tab_area_id
            if not area or not row.area_range_id:
                continue
            # El rango debe estar disponible para el área de la pestaña.
            if row.area_range_id not in area.area_range_ids:
                raise ValidationError(_("El rango debe pertenecer a los rangos del área de la línea."))


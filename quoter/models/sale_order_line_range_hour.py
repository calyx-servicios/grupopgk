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

    def _quoter_skip_hours_policy_for_line(self, line):
        Line = self.env["sale.order.line"]
        if not line:
            return True
        if self.env["quoter.hours.policy"]._quoter_skip_strict_hours_validation():
            return True
        return not Line._quoter_is_real_db_id(line.id)

    def _quoter_enforce_hours_policy(self):
        Policy = self.env["quoter.hours.policy"]
        for row in self:
            line = row.sale_line_id
            if not line or self._quoter_skip_hours_policy_for_line(line):
                continue
            if line.quoter_is_adjustment_line:
                Policy.validate_adjustment_hours_nonzero(
                    row.hours,
                    row.area_range_id.display_name if row.area_range_id else None,
                )
            elif line._quoter_manual_ranges_mode() or line._quoter_manual_total_mode():
                Policy.validate_hours_non_negative(row.hours, _("Horas"))
            elif (row.hours or 0.0) < 0.0:
                raise ValidationError(_("Las horas no pueden ser negativas."))

    @api.constrains("hours", "sale_line_id")
    def _check_hours_policy(self):
        self._quoter_enforce_hours_policy()

    _sql_constraints = [
        (
            "uniq_sale_line_area_range",
            "UNIQUE(sale_line_id, area_range_id)",
            "Ya hay horas cargadas para ese rango en esta línea.",
        )
    ]

    def write(self, vals):
        if "hours" in vals:
            self._quoter_enforce_hours_policy_on_vals(vals)
        res = super().write(vals)
        if "hours" in vals:
            self.mapped("sale_line_id").filtered(
                "quoter_is_adjustment_line"
            )._quoter_validate_adjustment_hours_balance()
        return res

    def _quoter_enforce_hours_policy_on_vals(self, vals):
        if self.env["quoter.hours.policy"]._quoter_skip_strict_hours_validation():
            return
        hours = float(vals.get("hours", 0.0))
        for row in self:
            line = row.sale_line_id
            if not line or self._quoter_skip_hours_policy_for_line(line):
                continue
            Policy = self.env["quoter.hours.policy"]
            if line.quoter_is_adjustment_line:
                Policy.validate_adjustment_hours_nonzero(
                    hours,
                    row.area_range_id.display_name if row.area_range_id else None,
                )
            elif line._quoter_manual_ranges_mode() or line._quoter_manual_total_mode():
                Policy.validate_hours_non_negative(hours, _("Horas"))

    @api.model_create_multi
    def create(self, vals_list):
        Policy = self.env["quoter.hours.policy"]
        if not Policy._quoter_skip_strict_hours_validation():
            for vals in vals_list:
                if "hours" not in vals:
                    continue
                hours = float(vals.get("hours", 0.0))
                line = False
                if vals.get("sale_line_id"):
                    line = self.env["sale.order.line"].browse(vals["sale_line_id"])
                if not line or self._quoter_skip_hours_policy_for_line(line):
                    continue
                if line.quoter_is_adjustment_line:
                    Policy.validate_adjustment_hours_nonzero(hours)
                elif line._quoter_manual_ranges_mode() or line._quoter_manual_total_mode():
                    Policy.validate_hours_non_negative(hours, _("Horas"))
        rows = super().create(vals_list)
        rows.mapped("sale_line_id").filtered(
            "quoter_is_adjustment_line"
        )._quoter_validate_adjustment_hours_balance()
        return rows

    @api.constrains("area_range_id", "sale_line_id")
    def _check_range_belongs_to_line_area(self):
        for row in self:
            area = row.sale_line_id.quoter_tab_area_id
            if not area or not row.area_range_id:
                continue
            # El rango debe estar disponible para el área de la pestaña.
            if row.area_range_id not in area.area_range_ids:
                raise ValidationError(_("El rango debe pertenecer a los rangos del área de la línea."))


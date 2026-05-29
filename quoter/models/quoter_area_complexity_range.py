# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import api, fields, models


class QuoterAreaComplexityRange(models.Model):
    _name = "quoter.area.complexity.range"
    _description = "Categoría de recursos reusable para áreas"
    _order = "sequence, id"

    name = fields.Char(
        string="Nombre",
        required=True,
        translate=True,
        help="Ej.: Rango 1, Rango 2…",
    )

    sequence = fields.Integer(default=10)

    _sql_constraints = [
        (
            "quoter_area_range_name_uniq",
            "UNIQUE(name)",
            "Ya existe un rango con ese nombre.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        areas = self.env["quoter.professional.area"].search(
            [("area_range_ids", "in", self.ids)]
        )
        areas.line_ids._sync_range_hour_lines()
        areas._sync_range_rate_products()
        areas._sync_product_level_range_hour_lines()
        return res

    def unlink(self):
        areas = self.env["quoter.professional.area"].search(
            [("area_range_ids", "in", self.ids)]
        )
        res = super().unlink()
        areas.line_ids._sync_range_hour_lines()
        # Al borrar el rango, el M2M del área se limpia sin pasar por area.write:
        # hay que sincronizar productos «Tarifa/h» aquí.
        areas._sync_range_rate_products()
        areas._sync_product_level_range_hour_lines()
        return res

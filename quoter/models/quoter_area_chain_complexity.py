# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class QuoterAreaChainComplexityIncrease(models.Model):
    _name = "quoter.area.chain.complexity.increase"
    _description = "Aumento % cadena por nivel de complejidad"
    _order = "complexity_level_sequence, complexity_level_id, id"

    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área",
        required=True,
        ondelete="cascade",
        index=True,
    )
    complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel de complejidad",
        required=True,
        ondelete="restrict",
        index=True,
    )
    complexity_level_sequence = fields.Integer(
        related="complexity_level_id.sequence",
        store=True,
        readonly=True,
    )
    level_name = fields.Char(
        related="complexity_level_id.name",
        string="Nivel",
        readonly=True,
    )
    increase_percent = fields.Float(
        string="% de aumento",
        default=0.0,
        help="Porcentaje sumado a las horas calculadas por rol y producto "
        "cuando en la cotización se elige este nivel de complejidad.",
    )

    _sql_constraints = [
        (
            "uniq_chain_complexity_increase_area_level",
            "UNIQUE(area_id, complexity_level_id)",
            "Solo puede definirse un aumento por nivel de complejidad en el área.",
        ),
    ]

    def unlink(self):
        areas = self.mapped("area_id")
        res = super().unlink()
        areas._chain_clear_stale_test_complexity_level()
        return res

    @api.constrains("increase_percent")
    def _check_increase(self):
        for rec in self:
            if (rec.increase_percent or 0.0) < 0.0:
                raise ValidationError(
                    _("El porcentaje de aumento no puede ser negativo.")
                )

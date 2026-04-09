# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


class QuoterComplexityLevel(models.Model):
    _name = "quoter.complexity.level"
    _description = "Nivel de complejidad (bajo, medio, alto, etc.)"
    _order = "name"

    name = fields.Char(
        string="Nombre",
        required=True,
        translate=True,
        help="Ejemplo: Bajo, Medio, Alto.",
    )

    color = fields.Integer(
        string="Color",
        default=0,
        help="Color para mostrar en pedidos de venta y vistas.",
    )

    area_ids = fields.Many2many(
        comodel_name="quoter.professional.area",
        relation="quoter_professional_area_complexity_level_rel",
        column1="complexity_level_id",
        column2="area_id",
        string="Áreas",
        help="Áreas que utilizan este nivel (compartido entre varias).",
    )

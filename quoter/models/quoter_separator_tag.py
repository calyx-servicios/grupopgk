# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


class QuoterLineSeparatorTag(models.Model):
    _name = "quoter.line.separator.tag"
    _description = "Etiqueta separadora (líneas de cotización)"
    _order = "name"

    name = fields.Char(
        string="Etiqueta",
        required=True,
        translate=True,
        help="Se usará como separador visual en líneas del pedido de venta.",
    )

    color = fields.Integer(
        string="Color",
        default=0,
        help="Índice de color para la vista (paleta estándar de Odoo).",
    )

    area_ids = fields.Many2many(
        comodel_name="quoter.professional.area",
        relation="quoter_professional_area_separator_tag_rel",
        column1="separator_tag_id",
        column2="area_id",
        string="Áreas",
        help="Áreas que reutilizan esta etiqueta.",
    )

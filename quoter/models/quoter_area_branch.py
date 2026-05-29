# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class QuoterAreaBranch(models.Model):
    _name = "quoter.area.branch"
    _description = "Rama de complejidad"
    _order = "sequence, id"

    name = fields.Char(
        string="Nombre",
        required=True,
        translate=True,
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )
    color = fields.Integer(
        string="Color",
        default=0,
        help="Color para mostrar ramas en etiquetas y selectores.",
    )
    selectable = fields.Boolean(
        string="Seleccionable",
        default=True,
        help="Si está desactivado, la rama se usa solo como fallback técnico.",
    )

    @api.constrains("selectable")
    def _check_unique_branch_not_selectable(self):
        default_branch = self.env.ref("quoter.quoter_area_branch_unique", raise_if_not_found=False)
        for rec in self:
            if default_branch and rec.id == default_branch.id and rec.selectable:
                raise ValidationError(
                    _("La rama «Rama única» es técnica y no puede marcarse como seleccionable.")
                )

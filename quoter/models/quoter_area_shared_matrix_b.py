# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class QuoterAreaSharedMatrixB(models.Model):
    _name = "quoter.area.shared.matrix.b"
    _description = "Tabla B compartida (productos varios)"
    _order = "area_range_sequence, id"

    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área",
        required=True,
        ondelete="cascade",
    )
    area_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rol del área",
        required=True,
        ondelete="restrict",
        index=True,
    )
    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )
    factor = fields.Float(
        string="Factor tabla B",
        default=0.0,
        help="Factor B compartido para productos marcados con «B común».",
    )

    _sql_constraints = [
        (
            "uniq_area_shared_b_range",
            "UNIQUE(area_id, area_range_id)",
            "Ya existe un factor B compartido para ese rol.",
        )
    ]

    @api.constrains("area_range_id", "area_id")
    def _check_range_in_area(self):
        for row in self:
            if row.area_range_id not in row.area_id.area_range_ids:
                raise ValidationError(
                    _("El rol debe pertenecer a los roles configurados en el área.")
                )

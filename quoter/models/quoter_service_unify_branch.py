# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class QuoterServiceLineUnifyBranchHour(models.Model):
    _name = "quoter.service.line.unify.branch.hour"
    _description = "Horas por rama (producto con unifica valor)"
    _order = "branch_id, id"

    line_id = fields.Many2one(
        comodel_name="quoter.service.line",
        string="Línea de servicio",
        required=True,
        ondelete="cascade",
    )
    branch_id = fields.Many2one(
        comodel_name="quoter.area.branch",
        string="Rama",
        required=True,
        ondelete="restrict",
    )
    hours = fields.Float(string="Horas", default=0.0)

    _sql_constraints = [
        (
            "uniq_line_branch",
            "UNIQUE(line_id, branch_id)",
            "Ya hay horas definidas para esa rama en esta línea.",
        )
    ]

    @api.constrains("hours")
    def _check_hours_non_negative(self):
        for row in self:
            if (row.hours or 0.0) < 0.0:
                raise ValidationError(_("Las horas no pueden ser negativas."))

    @api.constrains("branch_id", "line_id")
    def _check_branch_in_area(self):
        for row in self:
            area = row.line_id.area_id
            if not area or not row.branch_id:
                continue
            if row.branch_id not in area._effective_branch_ids():
                raise ValidationError(
                    _("La rama debe pertenecer a las ramas configuradas en el área.")
                )

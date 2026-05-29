# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class QuoterServiceLineManualTotalCompat(models.Model):
    _inherit = "quoter.service.line"

    manual_total_load = fields.Boolean(
        string="Horas totales manual",
        default=False,
        help=(
            "Permite editar horas totales en la cotización. Al cambiar el total, "
            "se redistribuye proporcionalmente entre los rangos."
        ),
    )

    @api.onchange("manual_load", "manual_total_load")
    def _onchange_manual_modes_exclusive_compat(self):
        for line in self:
            if line.manual_load and line.manual_total_load:
                line.manual_load = False

    @api.constrains("manual_load", "manual_total_load")
    def _check_manual_modes_exclusive_compat(self):
        for line in self:
            if line.manual_load and line.manual_total_load:
                raise ValidationError(_("Seleccione solo un modo manual: rangos o total."))

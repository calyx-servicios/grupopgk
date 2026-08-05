# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

PARAM_VOL_MIN = "vol_min"
PARAM_HOURS_BELOW = "hours_below"
PARAM_HOURS_BASE = "hours_base"
PARAM_MIN_EXCESS = "min_excess"
PARAM_MINUTES_LINEAR = "minutes_linear"

FORMULA_LABEL_VOLUME = "VOLUMEN"
FORMULA_PARAM_SYMBOL = "nº"

FORMULA_KIND_LINEAR_LABEL = "=(VOLUMEN×nº)/60"
FORMULA_KIND_THRESHOLD_LABEL = (
    "=SI(VOLUMEN<nº;nº;(nº+((VOLUMEN-nº)×nº)/60))"
)


class QuoterFormulaProductConfigParam(models.Model):
    _name = "quoter.formula.product.config.param"
    _description = "Parámetro editable de fórmula por rol"
    _order = "sequence, id"

    range_id = fields.Many2one(
        comodel_name="quoter.formula.product.config.range",
        string="Rol",
        required=True,
        ondelete="cascade",
        index=True,
    )
    code = fields.Selection(
        selection=[
            (PARAM_VOL_MIN, "Umbral de volumen"),
            (PARAM_HOURS_BELOW, "Horas si VOLUMEN < umbral"),
            (PARAM_HOURS_BASE, "Horas piso"),
            (PARAM_MIN_EXCESS, "Minutos / unidad excedente"),
            (PARAM_MINUTES_LINEAR, "Minutos / unidad (lineal)"),
        ],
        string="Parámetro",
        required=True,
    )
    value = fields.Float(string="Valor", default=1.0, required=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        (
            "uniq_range_param_code",
            "UNIQUE(range_id, code)",
            "Cada parámetro solo puede definirse una vez por rol.",
        )
    ]

    @api.constrains("value")
    def _check_value_non_negative(self):
        for rec in self:
            if (rec.value or 0.0) < 0.0:
                raise ValidationError(_("Los parámetros no pueden ser negativos."))

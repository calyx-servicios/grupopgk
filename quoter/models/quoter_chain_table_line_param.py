# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

CHAIN_PARAM_N = "param_n"
CHAIN_PARAM_VALOR = "param_valor"

CHAIN_LABEL_PARENT = "Último valor fijo en cadena"
CHAIN_LABEL_EMPLOYEES = "cantidad de empleados"
CHAIN_PARAM_SYMBOL = "nº"


class QuoterChainTableLineParam(models.Model):
    _name = "quoter.chain.table.line.param"
    _description = "Parámetro de fórmula cadena"
    _order = "sequence, id"

    chain_line_id = fields.Many2one(
        comodel_name="quoter.chain.table.line",
        string="Celda",
        required=True,
        ondelete="cascade",
        index=True,
    )
    code = fields.Selection(
        selection=[
            (CHAIN_PARAM_N, "Coeficiente (nº)"),
            (CHAIN_PARAM_VALOR, "Valor umbral"),
        ],
        string="Parámetro",
        required=True,
    )
    value = fields.Float(string="Valor", default=1.0, required=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        (
            "uniq_chain_line_param_code",
            "UNIQUE(chain_line_id, code)",
            "Cada parámetro solo puede definirse una vez por celda.",
        ),
    ]

    @api.constrains("value")
    def _check_value_non_negative(self):
        for rec in self:
            if (rec.value or 0.0) < 0.0:
                raise ValidationError(_("Los parámetros no pueden ser negativos."))

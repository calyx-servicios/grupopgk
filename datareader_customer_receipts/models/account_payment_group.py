from odoo import models, fields, api


class AccountPaymentGroup(models.Model):
    _inherit = "account.payment.group"

    is_datareader_op = fields.Boolean(
        string="OP de DataReader",
        default=False,
        help="Indica si esta orden de pago proviene de DataReader Customer Receipts"
    )
    datareader_op_date = fields.Date(
        string="Fecha de OP",
        help="Fecha de la orden de pago que viene de DataReader"
    )


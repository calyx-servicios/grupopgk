from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move"

    personal_pay_transaction_ids = fields.One2many(
        comodel_name="personal.pay.transaction", inverse_name="move_id"
    )

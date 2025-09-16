from odoo import models, fields

class AccountPaymentReceiptbook(models.Model):
    _inherit = 'account.payment.receiptbook'

    is_automatic_receiptbook = fields.Boolean(string="Cobranza Automática", default=False)

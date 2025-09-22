from odoo import models, fields, _

class AccountPaymentReceiptbook(models.Model):
    _inherit = 'account.payment.receiptbook'

    is_automatic_receiptbook = fields.Boolean(string=_('Automatic ReceiptBook'), default=False)

from odoo import models, fields, api, _

class AccountPaymentReceiptbook(models.Model):
    _inherit = 'account.payment.receiptbook'

    is_automatic_receiptbook = fields.Boolean(string=_('Automatic ReceiptBook'), default=False)
    is_datareader_receiptbook = fields.Boolean(
        string=_('DataReader ReceiptBook'), 
        default=False,
        help=_('If checked, this receiptbook will be used for DataReader payment receipts with RE-D prefix')
    )

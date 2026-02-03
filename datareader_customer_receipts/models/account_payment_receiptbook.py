from odoo import models, fields, _

class AccountPaymentReceiptbook(models.Model):
    _inherit = 'account.payment.receiptbook'

    is_automatic_receiptbook = fields.Boolean(string="Cobranza Automática", default=False)
    is_datareader_receiptbook = fields.Boolean(
        string='Libro de recepciones para Cobranza Automática', 
        default=False,
        help=_('Receiptbook for DataReader payment receipts with RE-D prefix')
    )
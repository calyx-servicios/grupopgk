from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    journal_payment_id = fields.Many2one('account.journal', string='Payment Journal')
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Payment Method')
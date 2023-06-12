from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    journal_id = fields.Many2one('account.journal', string='Payment Journal')
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Payment Method')
    available_payment_method_line_ids = fields.Many2many('account.payment.method.line',
        compute='_compute_payment_method_line_fields')

    @api.depends('journal_id')
    def _compute_payment_method_line_fields(self):
        for purchase in self:
            purchase.available_payment_method_line_ids = purchase.journal_id._get_available_payment_method_lines('outbound')

    def _prepare_invoice(self):
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()
        invoice_vals.update({
            'journal_payment_id': self.journal_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
        })
        return invoice_vals
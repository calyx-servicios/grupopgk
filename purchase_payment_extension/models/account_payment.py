from odoo import models, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.depends('available_payment_method_line_ids')
    def _compute_payment_method_line_id(self):
        for rec in self:
            for to_pay_move_line in rec.payment_group_id.to_pay_move_line_ids:
                move_line = self.env['account.move.line'].browse(to_pay_move_line.id.origin)
                if move_line:
                    move_id = move_line.move_id
                    if move_id.move_type in ['in_invoice','in_refund']:
                        if move_id.journal_payment_id:
                            rec.journal_id = move_id.journal_payment_id.id
                        if move_id.payment_method_line_id:
                            rec.payment_method_line_id = move_id.payment_method_line_id.id
                            rec.hide_payment_method_line = False
                else:
                    return super(AccountPayment, self)._compute_payment_method_line_id()

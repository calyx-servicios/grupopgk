from odoo import models,api,fields, _
from datetime import date
from odoo.exceptions import UserError
import re
import base64

class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_send_ids = fields.Many2many('account.invoice.send', 'account_move_account_invoice_send_rel', string='Invoice Sends')

    def action_invoice_sent(self):
        res = super().action_invoice_sent()
        template_id = self.env.ref('invoice_without_detail.email_template_invoice_without_detail')
        if template_id:
            res['context']['default_template_id'] = template_id.id
        return res

    def create_template_report_invoice(self):
        return self.env.ref('invoice_without_detail.action_invoce_without_details').report_action(self)

    
    def action_invoice_print(self):
        """ Print the invoice and mark it as sent, so that we can see more
            easily the next step of the workflow
        """
        if any(not move.is_invoice(include_receipts=True) for move in self):
            raise UserError(_("Only invoices could be printed."))

        self.filtered(lambda inv: not inv.is_move_sent).write({'is_move_sent': True})
        if self.env.ref('invoice_without_detail.email_template_invoice_without_detail').id == self.invoice_send_ids[0].template_id.id:
            return self.env.ref('invoice_without_detail.action_invoce_without_details').report_action(self)
        elif self.user_has_groups('account.group_account_invoice'):
            return self.env.ref('account.account_invoices').report_action(self)
        else:
            return self.env.ref('account.account_invoices_without_payment').report_action(self)
    


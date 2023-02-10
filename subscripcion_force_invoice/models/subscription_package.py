from odoo import _, models, fields
from odoo.exceptions import UserError


class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'
    
    def force_invoice(self):
        if self.plan_id.limit_choice == 'custom' and self.invoice_count >= self.plan_id.limit_count:
            raise UserError(_('The number of invoices cannot exceed the number of times to renew the subscription.'))
        elif self.plan_id.limit_choice == 'ones' and self.invoice_count >= 1:
            raise UserError(_('The number of invoices cannot exceed the number of times to renew the subscription.'))
        this_products_line = []
        for rec in self.product_line_ids:
            rec_list = [0, 0, {'product_id': rec.product_id.id,
                            'quantity': rec.product_qty,
                            'price_unit': rec.unit_price,
                            'analytic_account_id': rec.analytic_account_id.id}]
            this_products_line.append(rec_list)
        move = self.env['account.move'].create(
            {
                'move_type': 'out_invoice',
                'date': fields.Date.today(),
                'invoice_date': self.next_invoice_date,
                'state': 'draft',
                'sale_type_id': self.sale_order.type_id.id,
                'partner_id': self.partner_invoice_id.id,
                'currency_id': self.partner_invoice_id.currency_id.id,
                'invoice_line_ids': this_products_line,
                'subscription_id': self.id,
            })
        if move:
            self.start_date = fields.Date.today()
        return {
            'name': 'Force Invoice',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id
        }
        
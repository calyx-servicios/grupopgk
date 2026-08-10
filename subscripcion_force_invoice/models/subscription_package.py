from odoo import _, api, models, fields
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'

    # En el modulo base el campo es compute(store=False) y sin inverse, por eso
    # la fecha que asigna create_invoice_forced solo vivia en cache y se perdia.
    # Como computado almacenado y editable el valor asignado se persiste hasta
    # que cambie alguna dependencia.
    next_invoice_date = fields.Date(store=True, readonly=False,
                                    compute='_compute_next_invoice_date')

    @api.depends('start_date', 'plan_id.renewal_time')
    def _compute_next_invoice_date(self):
        # El compute del modulo base recorre un search en vez de self, dejando
        # sin asignar los registros fuera de la etapa 'progress'.
        for sub in self:
            if sub.start_date:
                sub.next_invoice_date = sub.start_date + relativedelta(
                    days=sub.plan_id.renewal_time)
            else:
                sub.next_invoice_date = False

    def force_invoice(self):
        invoice_count = self.env['account.move'].search_count([('subscription_id', '=', self.id)])        
        if self.plan_id.limit_choice == 'custom' and invoice_count >= self.plan_id.limit_count:
            raise UserError(_('The number of invoices cannot exceed the number of times to renew the subscription.'))
        elif self.plan_id.limit_choice == 'ones' and invoice_count >= 1:
            raise UserError(_('The number of invoices cannot exceed the number of times to renew the subscription.'))
        move = self.create_invoice_forced()
        return {
            'name': 'Force Invoice',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id
        }
    
    def create_invoice_forced(self):
        this_products_line = []
        for rec in self.product_line_ids:
            rec_list = [0, 0, {'product_id': rec.product_id.id,
                            'quantity': rec.product_qty,
                            'price_unit': rec.unit_price,
                            'analytic_account_id': rec.analytic_account_id.id,
                            'display_type': rec.display_type}]
            this_products_line.append(rec_list)
        move = self.env['account.move'].with_company(self.company_id.id).create(
            {
                'move_type': 'out_invoice',
                'date': fields.Date.today(),
                'invoice_date': fields.Date.today(),
                'state': 'draft',
                'sale_type_id': self.sale_order.type_id.id,
                'partner_id': self.partner_invoice_id.id,
                'currency_id': self.partner_invoice_id.currency_id.id,
                'invoice_line_ids': this_products_line,
                'subscription_id': self.id,
                'company_id': self.company_id.id,
                'partner': self.sale_order.partner.id
            })
        if move:
            today_date = fields.Date.today()
            renewal_value = int(self.plan_id.renewal_value)
            if self.plan_id.renewal_period in ['days','weeks']:
                if self.plan_id.renewal_period == 'days':
                    self.next_invoice_date = today_date + relativedelta(
                        days=renewal_value)
                else:
                    self.next_invoice_date = today_date + relativedelta(
                        days=(renewal_value * 7))
            elif self.plan_id.renewal_period == 'months':
                self.next_invoice_date = today_date + relativedelta(
                    months=renewal_value)
            else:
                self.next_invoice_date = today_date + relativedelta(
                    years=renewal_value)
        return move


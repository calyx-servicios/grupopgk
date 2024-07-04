from odoo import _, models, fields
from dateutil.relativedelta import relativedelta
import datetime


class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'
    
    def close_limit_cron(self):
        """ It Checks renew date, close date. It will send mail when renew date """
        pending_subscriptions = self.env['subscription.package'].search(
            [('stage_category', '=', 'progress')])
        today_date = fields.Date.today()
        pending_subscription = False
        close_subscription = False
        for pending_subscription in pending_subscriptions:
            pending_subscription.close_date = pending_subscription.start_date + relativedelta(
                days=pending_subscription.plan_id.days_to_end)
            difference = (
                                 pending_subscription.close_date - pending_subscription.start_date).days / 10
            renew_date = pending_subscription.close_date - relativedelta(
                days=difference)
            if today_date == renew_date:
                self.env.ref(
                    'subscription_package.mail_template_subscription_renew').send_mail(
                    pending_subscription.id, force_send=True)
                pending_subscription.write({'to_renew': True})
                if pending_subscription.plan_id.invoice_mode == 'draft_invoice':
                    this_products_line = []
                    for rec in pending_subscription.product_line_ids:
                        rec_list = [0, 0, {'product_id': rec.product_id.id,
                                           'quantity': rec.product_qty,
                                           'price_unit': rec.unit_price,
                                           'analytic_account_id': rec.analytic_account_id.id}]
                        this_products_line.append(rec_list)
                        self.env['account.move'].create(
                            {
                                'move_type': 'out_invoice',
                                'date': fields.Date.today(),
                                'invoice_date': fields.Date.today(),
                                'state': 'draft',
                                'partner_id': pending_subscription.partner_invoice_id.id,
                                'currency_id': pending_subscription.partner_invoice_id.currency_id.id,
                                'invoice_line_ids': this_products_line,
                                'subscription_id': pending_subscription.id,
                            })
                    pending_subscription.write({'to_renew': False,
                                                'start_date': datetime.datetime.today()})
        close_subscriptions = self.env['subscription.package'].search(
            [('stage_category', '=', 'progress'), ('to_renew', '=', True)])
        for close_subscription in close_subscriptions:
            close_subscription.close_date = close_subscription.start_date + relativedelta(
                days=close_subscription.plan_id.days_to_end)
            if today_date == close_subscription.close_date:
                close_subscription.set_close()
        return dict(pending=pending_subscription, closed=close_subscription)

    def next_invoice_or_close(self):
        subscriptions = self.env['subscription.package'].search([('stage_category', '=', 'progress')])
        today_date = fields.Date.today()
        for pending_subscription in subscriptions.filtered(lambda s: s.to_renew == False):
            if pending_subscription.next_invoice_date == today_date:
                invoice_count = self.env['account.move'].search_count([('subscription_id', '=', pending_subscription.id)])
                if pending_subscription.plan_id.limit_choice == 'custom' and invoice_count >= pending_subscription.plan_id.limit_count:
                    pending_subscription.set_close()
                elif pending_subscription.plan_id.limit_choice == 'ones' and invoice_count >= 1:
                    pending_subscription.set_close()
                else:
                    pending_subscription.create_invoice_forced()
                
        for close_subscription in subscriptions.filtered(lambda s: s.to_renew == True):
            if close_subscription.close_date == today_date:
                close_subscription.set_close()

    def button_sale_order(self):
        """Button to create sale order"""
        this_products_line = []
        for rec in self.product_line_ids:
            rec_list = [0, 0, {'product_id': rec.product_id.id,
                               'product_uom_qty': rec.product_qty,
                               'price_unit': rec.unit_price,
                               'analytic_account_id': rec.analytic_account_id.id}]
            this_products_line.append(rec_list)
        orders = self.env['sale.order'].search([('subscription_id', '=', self.id), ('invoice_status', '=', 'no')])
        if orders:
            for order in orders:
                order.action_confirm()
        so_id = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'partner_invoice_id': self.partner_id.id,
            'partner_shipping_id': self.partner_id.id,
            'is_subscription': True,
            'subscription_id': self.id,
            'date_of_issue': datetime.date.today(),
            'analytic_account_id': self.analytic_account_id.id,
            'order_line': this_products_line
        })
        self.sale_order = so_id
        return {
            'name': _('Sales Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'domain': [('id', '=', so_id.id)],
            'view_mode': 'tree,form'
        }

    def next_date_invoice(self):
        # Traigo todas las suscripciones
        subscriptions = self.env['subscription.package'].search([('stage_category', '=', 'progress'), ('to_renew', '=', False)])
        # Busco las facturas asociadas a cada suscripcion
        for subscription in subscriptions:
            invoices = self.env['account.move'].search([('subscription_id', '=', subscription.id)])
            if invoices:
                # Obtengo la fecha de la última factura
                last_invoice_date = invoices[0].invoice_date
                if last_invoice_date:
                    # Agrego 30 días a la fecha de la última factura
                    next_invoice_date = last_invoice_date + relativedelta(days=30)
                    # Asigno la nueva fecha al campo next_invoice_date de la suscripción
                    subscription.next_invoice_date = next_invoice_date


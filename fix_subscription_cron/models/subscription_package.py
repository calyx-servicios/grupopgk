from odoo import _, models, fields
from dateutil.relativedelta import relativedelta
import datetime


class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'

    def _get_related_sale_orders(self, subscription):
        return self.env['sale.order'].sudo().search([('subscription_id', '=', subscription.id)])

    def _get_related_invoice(self, subscription, today_date=False):
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '!=', 'cancel'),
            ('subscription_id', '=', subscription.id),
        ]
        if today_date:
            domain.append(('invoice_date', '=', today_date))
        return self.env['account.move'].sudo().search(domain, order='invoice_date desc, id desc', limit=1)

    def _already_invoiced_current_period(self, subscription, today_date):
        return bool(self._get_related_invoice(subscription, today_date=today_date))

    def _link_invoice_to_subscription(self, subscription, invoice):
        values = {}
        if not invoice.subscription_id:
            values['subscription_id'] = subscription.id
        if not invoice.invoice_origin:
            sale_orders = self._get_related_sale_orders(subscription)
            if sale_orders:
                values['invoice_origin'] = ', '.join(sale_orders.mapped('name'))
        if values:
            invoice.sudo().write(values)

    def _link_invoice_to_sale_order(self, subscription, invoice):
        sale_order = subscription.sale_order
        if not sale_order:
            return
        sale_lines = sale_order.order_line.filtered(lambda l: not l.display_type)
        for line in invoice.invoice_line_ids.filtered(lambda l: not l.display_type and l.product_id):
            matches = sale_lines.filtered(lambda l: l.product_id.id == line.product_id.id)
            if matches:
                line.sudo().write({'sale_line_ids': [(6, 0, matches.ids)]})

    def _sync_subscription_cycle(self, subscription, invoice_date):
        if not invoice_date:
            return
        # next_invoice_date es compute(store=False), por eso avanzamos start_date.
        subscription.sudo().write({'start_date': invoice_date})
        subscription._compute_invoice_count()

    def _create_and_sync_invoice(self, subscription, today_date):
        before_invoice = self._get_related_invoice(subscription)
        before_invoice_id = before_invoice.id if before_invoice else 0
        subscription.with_context(
            allowed_company_ids=[subscription.company_id.id]
        ).with_company(subscription.company_id).create_invoice_forced()

        latest_invoice = self._get_related_invoice(subscription)
        if latest_invoice and latest_invoice.id != before_invoice_id:
            self._link_invoice_to_subscription(subscription, latest_invoice)
            self._link_invoice_to_sale_order(subscription, latest_invoice)
            self._sync_subscription_cycle(subscription, latest_invoice.invoice_date or today_date)
            return latest_invoice

        # Evita avanzar sin actualizar campos si la factura ya existia para el periodo.
        latest_today_invoice = self._get_related_invoice(subscription, today_date=today_date)
        if latest_today_invoice:
            self._link_invoice_to_subscription(subscription, latest_today_invoice)
            self._link_invoice_to_sale_order(subscription, latest_today_invoice)
            self._sync_subscription_cycle(subscription, latest_today_invoice.invoice_date or today_date)
            return latest_today_invoice
        return self.env['account.move']

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
        subscriptions = self.env['subscription.package'].sudo().search([('stage_category', '=', 'progress')])
        today_date = fields.Date.today()
        for pending_subscription in subscriptions.filtered(lambda s: s.to_renew == False):
            if pending_subscription.next_invoice_date == today_date:
                invoice_count = self.env['account.move'].sudo().search_count([('subscription_id', '=', pending_subscription.id)])
                if pending_subscription.plan_id.limit_choice == 'custom' and invoice_count >= pending_subscription.plan_id.limit_count:
                    pending_subscription.set_close()
                elif pending_subscription.plan_id.limit_choice == 'ones' and invoice_count >= 1:
                    pending_subscription.set_close()
                else:
                    if self._already_invoiced_current_period(pending_subscription, today_date):
                        latest_invoice = self._get_related_invoice(pending_subscription, today_date=today_date)
                        self._link_invoice_to_subscription(pending_subscription, latest_invoice)
                        self._link_invoice_to_sale_order(pending_subscription, latest_invoice)
                        self._sync_subscription_cycle(pending_subscription, latest_invoice.invoice_date or today_date)
                        continue
                    self._create_and_sync_invoice(pending_subscription, today_date)

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
            latest_invoice = self.env['account.move'].search(
                [('subscription_id', '=', subscription.id), ('move_type', '=', 'out_invoice')],
                order='invoice_date desc, id desc',
                limit=1
            )
            if latest_invoice and latest_invoice.invoice_date:
                # Agrego 30 días a la fecha de la última factura
                next_invoice_date = latest_invoice.invoice_date + relativedelta(days=30)
                # Asigno la nueva fecha al campo next_invoice_date de la suscripción
                subscription.next_invoice_date = next_invoice_date

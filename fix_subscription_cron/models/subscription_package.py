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
                                           'analytic_acccount_id': rec.analytic_account_id.id}]
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
from odoo import models, fields, api


class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'

    @api.depends('invoice_count')
    def _compute_invoice_count(self):
        """ Calculate Invoice count based on subscription package """
        for rec in self:
            invoice_count = rec.env['account.move'].search_count([
                ('subscription_id', '=', rec.id)
            ])
            rec.invoice_count = invoice_count or 0

from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    show_on_sale_order = fields.Boolean('Show on Sale Order Lines', default=False)

    
    def action_archive(self):
        for account in self:
            # Verificar si tiene suscripciones activas
            subscriptions = self.env['subscription.package'].search([
                ('stage_category', 'in', ['draft', 'progress'])
            ])

            active_subscriptions = []

            for subscription in subscriptions:
                for line in subscription.product_line_ids:
                    if line.analytic_account_id == account:
                        active_subscriptions.append(subscription.name)

            if active_subscriptions:
                subscription_names = '\n'.join(active_subscriptions)
                raise UserError(_(
                    'No se puede archivar la cuenta analítica porque tiene las siguientes suscripciones activas asociadas:\n%s'
                ) % subscription_names)

        # Llamar al método original para archivar
        return super(AccountAnalyticAccount, self).action_archive()


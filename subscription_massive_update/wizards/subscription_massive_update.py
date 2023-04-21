from odoo import models, fields, _
from odoo.exceptions import UserError


class SubscriptionMassiveUpdate(models.TransientModel):
    _name = 'subscription.massive_update'
    _description = 'Wizard massive update'


    subscriptions_ids = fields.Many2many('subscription.package', string='Subscriptions')
    percentage = fields.Float('Percentage to raise')

    def update(self):
        for subscription in self.subscriptions_ids:
            original_price = subscription.total_recurring_price
            percentage = (self.percentage / 100) + 1
            if subscription.product_line_ids:
                changes = _('<table><thead><tr><th>Product</th><th>Original Price</th><th>Current Price</th></tr></thead><tbody>')
                try:
                    for line in subscription.product_line_ids:
                        current_price = line.unit_price
                        new_price = current_price * percentage
                        line.unit_price = new_price
                        changes += _('<tr><td>{}</td><td>{}</td><td>{}</td></tr>').format(line.product_id.display_name, current_price, new_price)
                except Exception as e:
                    raise UserError(_('Error ({}) when trying to update product line in subscription with ID({})').format(e, subscription.id)) 
                changes += '</tbody></table>'
            else:
                changes = ''
            message_body = _('Subscription prices have been updated by <a href=# data-oe-model=res.users data-oe-id={}>{}</a> with a {}% increase. The total price of subscription {} has been changed from {} to {}. The following changes were made to product lines: {}').format(
            self.env.user.id, self.env.user.name, self.percentage, subscription.display_name, original_price, subscription.total_recurring_price, changes)
            subscription.message_post(body=message_body)

    def massive_update(self, window_title, ids):
        wiz = self.create({
            'subscriptions_ids': ids,
        })
        return wiz.open_wizard(window_title)

    def open_wizard(self, title):
        view = self.env.ref('subscription_massive_update.wizard_massive_update_form')
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': self._name,
            'target': 'new',
            'view_id': view.id,
            'view_mode': 'form',
            'res_id': self.id,
            'context': self.env.context,
        }
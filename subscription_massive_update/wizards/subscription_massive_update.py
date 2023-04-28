from odoo import models, fields, _
from odoo.exceptions import UserError


class SubscriptionMassiveUpdate(models.TransientModel):
    _name = 'subscription.massive_update'
    _description = 'Wizard massive update'


    subscriptions_ids = fields.Many2many('subscription.package', string='Subscriptions')
    fields_to_update = fields.Selection([
        ('price', 'Price'),
        ('plan', 'Plan'),
        ('date', 'Date'),
        ('plan_and_date', 'Plan and Date'),
    ], string='Fields to Update')
    percentage = fields.Float('Percentage to raise')
    date = fields.Date('Next Invoice Date')
    subscriptions_plan_id = fields.Many2one('subscription.package.plan', string='Subscription Plan')

    def update(self):
        for subscription in self.subscriptions_ids:
            if self.fields_to_update == 'price':
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
            elif self.fields_to_update == 'plan':
                old_plan_name = subscription.plan_id.name
                subscription.plan_id = self.subscriptions_plan_id.id
                message_body = _('Subscription plan has been updated by <a href=# data-oe-model=res.users data-oe-id={}>{}</a>. The plan of subscription {} has been changed from {} to {}.').format(
                self.env.user.id, self.env.user.name, subscription.display_name, old_plan_name, subscription.plan_id.name)
                subscription.message_post(body=message_body)
            elif self.fields_to_update == 'date':
                old_date = subscription.next_invoice_date
                subscription.next_invoice_date = self.date
                message_body = _('Subscription next invoice date has been updated by <a href=# data-oe-model=res.users data-oe-id={}>{}</a>. The next invoice date of subscription {} has been changed from {} to {}.').format(
                self.env.user.id, self.env.user.name, subscription.display_name, old_date, subscription.next_invoice_date)
                subscription.message_post(body=message_body)
            elif self.fields_to_update == 'plan_and_date':
                old_plan_name = subscription.plan_id.name
                old_date = subscription.next_invoice_date
                subscription.plan_id = self.subscriptions_plan_id.id
                subscription.next_invoice_date = self.date
                message_body = _('Subscription plan and next invoice date have been updated by <a href=# data-oe-model=res.users data-oe-id={}>{}</a>. The plan of subscription {} has been changed from {} to {}. The next invoice date of subscription {} has been changed from {} to {}.').format(
                self.env.user.id, self.env.user.name, subscription.display_name, old_plan_name, subscription.plan_id.name, subscription.display_name, old_date, subscription.next_invoice_date)
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
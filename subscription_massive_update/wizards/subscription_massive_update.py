from odoo import models, fields, _
from odoo.exceptions import UserError


class SubscriptionMassiveUpdate(models.TransientModel):
    _name = 'subscription.massive_update'
    _description = 'Wizard massive update'

    subscriptions_ids = fields.Many2many(comodel_name='subscription.package', string='Subscriptions')
    percentage = fields.Float('Percentage to raise')
    
    def update(self):
        percentage = (self.percentage / 100) + 1
        for subscription in self.subscriptions_ids:
            try:
                for line in subscription.product_line_ids:
                    current_price = line.unit_price
                    line.unit_price = current_price * percentage
            except Exception as e:
                raise UserError(_('Error ({}) when is trying to update line with ID({}) in subscription id({})').format(e, line.id, subscription.id))
                

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
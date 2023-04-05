from odoo import models, fields, _


class ManageCurrencyId(models.TransientModel):
    _name = 'manage.currencies.ids'
    _description = 'Manage Currencies IDS'


    analytics_line_ids = fields.Many2many(
        'account.analytic.line', string='Account Analytic Line', required=True)
    currency_action = fields.Selection([
        ('consolidated', 'Consolidate Currency'),
        ('update_currency', 'Update Currency')
    ], string='Select the action')
    currency_id = fields.Many2one(
        'res.currency', string='Currency Origin')
    new_currency = fields.Many2one(
        'res.currency', string='New Currency')
    amount_rate = fields.Float(string='Amount rate')

    def update_currency(self, window_title, ids):
        wiz = self.create({
            'analytics_line_ids': ids,
        })
        return wiz.open_wizard(window_title)

    def open_wizard(self, title):
        view = self.env.ref('account_analytic_currency.view_manage_currencies_ids_form')
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

    def update_currency_id(self):
        for record in self.analytics_line_ids:
            if record.move_id and record.currency_id != record.move_id.currency_id:
                record.currency_id = record.move_id.currency_id.id
        return {
            'type': 'ir.actions.act_window_close'
        }

    def consolidate_currency(self):
        records = self.analytics_line_ids.filtered(lambda x: x.currency_id.id == self.currency_id.id)
        for record in records:
            amount = record.amount
            record.currency_id = self.new_currency
            record.amount = amount * self.amount_rate
        return {
            'type': 'ir.actions.act_window_close'
        }
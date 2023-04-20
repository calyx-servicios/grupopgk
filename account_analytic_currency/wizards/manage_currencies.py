from odoo import models, fields


class ManageCurrencyId(models.TransientModel):
    _name = 'manage.currencies.ids'
    _description = 'Manage Currencies IDS'


    analytics_line_ids = fields.Many2many(
        'account.analytic.line', string='Account Analytic Line', required=True)

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
            record.update_currency_id()
        return {
            'type': 'ir.actions.act_window_close'
        }
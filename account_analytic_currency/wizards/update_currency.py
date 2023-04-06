from odoo import models, fields, _


class UpdateCurrencyId(models.TransientModel):
    _name = 'update.currency.id'
    _description = 'Update Currency ID for selected records'
    
    analytics_line_ids = fields.Many2many('account.analytic.line', string='Account Analytic Line')

    def update_currency(self, window_title, ids):
        wiz = self.create({
            'analytics_line_ids': ids,
        })
        return wiz.open_wizard(window_title)

    def open_wizard(self, title):
        view = self.env.ref('account_analytic_currency.view_update_currency_id_form')
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
        return {'type': 'ir.actions.act_window_close'}

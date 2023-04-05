from odoo import models, fields, api, _


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'


    currency_id = fields.Many2one('res.currency', string="Currency", store=True, readonly=True, compute='_compute_currency_id')


    @api.depends('move_id.currency_id', 'company_id.currency_id')
    def _compute_currency_id(self):
        for record in self:
            if record.move_id:
                record.currency_id = record.move_id.currency_id.id
            else:
                record.currency_id = record.company_id.currency_id.id

    def manage_currency(self):
        manage_currency_obj = self.env['manage.currencies.ids']
        active_ids = self.env.context.get('active_ids', [])
        return manage_currency_obj.update_currency(_('Manage Currencies'), active_ids)

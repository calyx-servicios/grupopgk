from odoo import fields, models


class AccountConsolidationData(models.Model):
    _name = 'account.consolidation.data'
    _description = 'Consolidation Data View'


    name = fields.Char(string='Name')
    group = fields.Char(string='Group')
    mother_group = fields.Char(string='Mother Group')
    sector_group = fields.Char(string='Sector Group')
    grandma_account = fields.Char(string='Grandmother Account')
    mother_account = fields.Char(string='Mother Account')
    company = fields.Char(string='Company')
    daughter_account = fields.Many2one('account.analytic.line', string='Daughter Account')
    description = fields.Char(string='Description')
    account_id = fields.Char(string='Account ID')
    currency_origin = fields.Char(string='Target Currency')
    currency = fields.Char(string='Currency')
    rate = fields.Float(string='Rate')
    amount = fields.Float(string='Amount')


    def open_line_analytic_form(self):
        self.ensure_one()
        line_analytic_id = self.daughter_account
        if line_analytic_id:
            return {
                'name': 'Line Analytic Form',
                'type': 'ir.actions.act_window',
                'res_model': 'account.analytic.line',
                'res_id': line_analytic_id.id,
                'view_mode': 'form',
            }
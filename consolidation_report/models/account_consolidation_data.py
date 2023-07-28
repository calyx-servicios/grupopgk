from odoo import fields, models


class AccountConsolidationData(models.Model):
    _name = 'account.consolidation.data'
    _description = 'Consolidation Data View'


    name = fields.Char(string='Name')
    main_group = fields.Many2one('account.analytic.group', string='Main Group')
    business_group = fields.Many2one('account.analytic.group', string='Business ID')
    sector_account_group = fields.Many2one('account.analytic.account', string='Sector ID')
    managment_account_group = fields.Many2one('account.analytic.account', string='Managment ID')
    company = fields.Char(string='Company')
    daughter_account = fields.Many2one('account.analytic.line', string='Analytic Account Line')
    description = fields.Char(string='Description')
    account_id = fields.Char(string='Account ID')
    currency_origin = fields.Many2one('res.currency', string='Target Currency')
    currency = fields.Many2one('res.currency', string='Currency')
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
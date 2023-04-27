from odoo import models, fields


class AccountConsolidationCompany(models.Model):
    _name = 'account.consolidation.company'
    _description = 'Companies and currencies for consolidation report'

    account_consolidation_report_id = fields.Many2one('account.consolidation.report', string='Consolidation Report')
    company_id = fields.Many2one('res.company', string='Company')
    currency_id = fields.Many2one('res.currency', string='Currency Origin')
    new_currency = fields.Many2one('res.currency', string='New Currency')
    rate = fields.Float(String='Rate')


    _sql_constraints = [
        ('company_unique', 'unique(account_consolidation_report_id, company_id)', 'Company already exists in consolidation report!'),
    ]
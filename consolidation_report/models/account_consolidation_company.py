from odoo import models, fields, api


class AccountConsolidationCompany(models.Model):
    _name = 'account.consolidation.company'
    _description = 'Companies and currencies for consolidation report'

    account_consolidation_report_id = fields.Many2one(
        'account.consolidation.period',
        string='Consolidation Period'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Target Currency'
    )
    new_currency = fields.Many2one(
        'res.currency',
        string='New Currency'
    )
    rate = fields.Float(
        string='Rate'
    )
    historical_rate = fields.Boolean(
        string='Use historical price'
    )
    is_main_currency = fields.Boolean(
        compute='_compute_is_main_currency',
        string='is main currency?'
    )

    @api.depends('company_id.currency_id', 'new_currency')
    def _compute_is_main_currency(self):
        for record in self:
            record.is_main_currency = bool(
                record.new_currency
                and record.company_id.currency_id == record.new_currency
            )

    _sql_constraints = [
        (
            'company_unique',
            'unique(account_consolidation_report_id, company_id)',
            'Company already exists in consolidation report!',
        ),
    ]

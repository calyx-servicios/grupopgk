from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    datareader_tolerance_journal_id = fields.Many2one(related='company_id.datareader_tolerance_journal_id', readonly=False)
    datareader_tolerance_analytic_account_id = fields.Many2one(related='company_id.datareader_tolerance_analytic_account_id', readonly=False)


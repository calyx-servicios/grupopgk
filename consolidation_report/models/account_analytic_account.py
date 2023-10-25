from odoo import models, fields, api


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    is_sector_group = fields.Boolean(string='Is Sector?', store=True)
    is_management_group = fields.Boolean(compute='_compute_is_management_group', string='Is Management?', store=True)

    @api.depends('parent_id')
    def _compute_is_management_group(self):
        for account in self:
            if account.parent_id and account.parent_id.is_sector_group:
                account.is_management_group = True
            else:
                account.is_management_group = False
    
 
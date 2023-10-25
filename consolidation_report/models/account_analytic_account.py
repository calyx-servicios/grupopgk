from odoo import models, fields, api


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    is_sector_group = fields.Boolean(string='Is Sector?', store=True)
    is_management_group = fields.Boolean(compute='_compute_is_management_group', string='Is Management?', store=True)

    #@api.depends('parent_id', 'group_id')
    #def _compute_is_sector_group(self):
    #    for account in self:
    #        if not account.parent_id and account.group_id.is_business_group == True:
    #            account.is_sector_group = True
    #        else:
    #            account.is_sector_group = False

    @api.depends('parent_id')
    def _compute_is_management_group(self):
        for account in self:
            if account.parent_id and account.parent_id.is_sector_group:
                account.is_management_group = True
            else:
                account.is_management_group = False
    
    @api.onchange('is_sector_group')
    def _onchange_is_sector_group(self):
        if self.is_sector_group:
            self.write({'is_sector_group': True})
        else:
            self.write({'is_sector_group': False})
from odoo import models, fields, api

class AccountAnalyticGroup(models.Model):
    _inherit = 'account.analytic.group'

    is_business_group = fields.Boolean(compute='_compute_is_business_group', String='Is Business?', store=True)
    
    @api.depends('parent_prin_group')
    def _compute_is_business_group(self):
        for group in self:
            if group.parent_id.id == group.parent_prin_group.id and group.parent_id:
                group.is_business_group = True
            else:
                group.is_business_group = False
from odoo import models, fields, api


class AccountAnalyticGroup(models.Model):
    _inherit = 'account.analytic.group'

    is_business_group = fields.Boolean(
        compute='_compute_is_business_group',
        string='Is Business?',
        store=True
    )

    @api.depends('parent_prin_group')
    def _compute_is_business_group(self):
        for group in self:
            group.is_business_group = bool(
                group.parent_id and group.parent_id == group.parent_prin_group
            )

from odoo import models, fields, api


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    is_sector_group = fields.Boolean(
        string='Is Sector?',
        store=True,
        copy=False
    )
    is_management_group = fields.Boolean(
        compute='_compute_is_management_group',
        string='Is Management?',
        store=True,
        copy=False
    )

    sector_account_id = fields.Many2one(
        'account.analytic.account',
        string='Sector',
        compute='_compute_sector_account_id',
        store=True,
        readonly=True,
        copy=False
    )

    @api.depends('parent_id', 'parent_id.is_sector_group')
    def _compute_is_management_group(self):
        for account in self:
            account.is_management_group = bool(
                account.parent_id and account.parent_id.is_sector_group
            )

    @api.depends('is_sector_group', 'parent_id', 'parent_id.sector_account_id')
    def _compute_sector_account_id(self):
        """Cada cuenta mira solo a su padre: la profundidad la resuelve la
        cadena de dependencias, sin importar cuantos niveles haya."""
        for account in self:
            account.sector_account_id = (
                account if account.is_sector_group
                else account.parent_id.sector_account_id
            )

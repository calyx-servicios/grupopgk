from odoo import models, fields, api

class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    move_company_id = fields.Many2one('res.company', string='Company', related='move_id.company_id', store=True)
    bussines_group_id = fields.Many2one('account.analytic.group', string='Business ID', compute='_compute_bussines_group_id', store=True)
    sector_account_id = fields.Many2one('account.analytic.account', string='Sector ID', compute='_compute_sector_account_id', store=True)
    managment_account_id = fields.Many2one('account.analytic.account', string='Managment ID', compute='_compute_managment_account_id', store=True)
    is_sector_group = fields.Boolean(string="Is Sector Group", related='account_id.is_sector_group')
    consolidation_line = fields.Boolean(string='Consolidation line', default=False)

    @api.depends('account_id')
    def _compute_managment_account_id(self):
        account_analytic_obj = self.env['account.analytic.account']
        for line in self:
            managment_account_ids = account_analytic_obj.search([
                ('is_management_group', '=', True),
                ('parent_id', '!=', False),
                ('group_id', '!=', False)
            ])
            if line.account_id:
                account_id = managment_account_ids.filtered(lambda account: account.id == line.account_id.id)
                if not account_id:
                    for mangment_account in managment_account_ids:
                        if line.account_id.id == mangment_account.id:
                            line.managment_account_id = mangment_account.id
                            break
                        else:
                            line.managment_account_id = line.account_id.parent_id.id
                else:
                    line.managment_account_id = account_id.id
            else:
                line.managment_account_id = False

    @api.depends('account_id')
    def _compute_bussines_group_id(self):
        account_analytic_group_obj = self.env['account.analytic.group']
        for line in self:
            if line.account_id.group_id:
                groups_ids = account_analytic_group_obj.search([('is_business_group', '=', True)])
                if line.account_id.group_id.id in groups_ids.ids:
                    line.bussines_group_id = line.account_id.group_id.id
                else:
                    group = groups_ids.children_ids.filtered(lambda group: group.id == line.account_id.group_id.id)
                    if group:
                        line.bussines_group_id = group.parent_id.id
                    else:
                        line.bussines_group_id = False
            else:
                line.bussines_group_id = False

    @api.depends('account_id')
    def _compute_sector_account_id(self):
        account_analytic_obj = self.env['account.analytic.account']
        for line in self:
            sector_account_ids = account_analytic_obj.search([
                ('is_sector_group', '=', True),
                ('parent_id', '=', False),
                ('group_id', '!=', False)
            ])
            if line.account_id:
                account_id = sector_account_ids.filtered(lambda account: account.id == line.account_id.id)
                if not account_id:
                    if not line.account_id.is_management_group:
                        for sector_account in sector_account_ids:
                            if line.account_id.parent_id.id in sector_account.child_ids.ids:
                                line.sector_account_id = sector_account.id
                                break
                            else:
                                line.sector_account_id = False
                    else:
                        line.sector_account_id = line.account_id.parent_id.id
                else:
                    line.sector_account_id = account_id.id
            else:
                line.sector_account_id = False

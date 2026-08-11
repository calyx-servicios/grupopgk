from odoo import models, fields, api


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    move_company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='move_id.company_id',
        store=True
    )
    bussines_group_id = fields.Many2one(
        'account.analytic.group',
        string='Business ID',
        compute='_compute_bussines_group_id',
        store=True
    )
    sector_account_id = fields.Many2one(
        'account.analytic.account',
        string='Sector ID',
        related='account_id.sector_account_id',
        store=True,
        readonly=True
    )
    managment_account_id = fields.Many2one(
        'account.analytic.account',
        string='Managment ID',
        compute='_compute_managment_account_id',
        store=True
    )
    is_sector_group = fields.Boolean(
        string="Is Sector Group",
        related='account_id.is_sector_group'
    )
    consolidation_line = fields.Boolean(
        string='Consolidation line',
        default=False
    )
    is_indirect_expense = fields.Boolean(
        string='Indirect Expense',
        default=False,
        store=True,
    )
    source_analytic_line_id = fields.Many2one(
        'account.analytic.line',
        string="Línea Analítica Origen",
        index=True
    )
    consolidation_data_line_ids = fields.One2many(
        'account.consolidation.data',
        'source_analytic_line_id',
        string='Líneas de consolidación',
        help='Filas del informe de consolidación que provienen de esta línea analítica.',
    )
    has_consolidation_data_lines = fields.Boolean(
        string='Tiene líneas en informe',
        compute='_compute_has_consolidation_data_lines',
        store=False,
    )

    @api.depends('consolidation_data_line_ids')
    def _compute_has_consolidation_data_lines(self):
        for line in self:
            line.has_consolidation_data_lines = bool(line.consolidation_data_line_ids)

    @api.depends('account_id', 'account_id.is_management_group', 'account_id.parent_id')
    def _compute_managment_account_id(self):
        account_analytic_obj = self.env['account.analytic.account']
        managment_account_ids = account_analytic_obj.search([
            ('is_management_group', '=', True),
            ('parent_id', '!=', False),
            ('group_id', '!=', False)
        ])
        managment_ids_set = set(managment_account_ids.ids)
        for line in self:
            account = line.account_id
            if not account:
                line.managment_account_id = False
                continue
            if account.id in managment_ids_set:
                line.managment_account_id = account.id
                continue
            # si la cuenta no es una gerencia, la gerencia es su padre: vale
            # tanto para la linea original como para su contrapartida
            line.managment_account_id = account.parent_id.id

    @api.depends(
        'account_id',
        'account_id.group_id',
        'account_id.group_id.parent_id',
        'account_id.group_id.is_business_group',
        'account_id.group_id.parent_id.is_business_group',
    )
    def _compute_bussines_group_id(self):
        account_analytic_group_obj = self.env['account.analytic.group']
        groups_ids = account_analytic_group_obj.search([('is_business_group', '=', True)])
        for line in self:
            group = line.account_id.group_id
            if not group:
                line.bussines_group_id = False
                continue
            if group.id in groups_ids.ids:
                line.bussines_group_id = group.id
                continue
            child = groups_ids.children_ids.filtered(lambda g: g.id == group.id)
            line.bussines_group_id = child.parent_id.id if child else False

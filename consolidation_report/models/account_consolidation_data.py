from odoo import fields, models


class AccountConsolidationData(models.Model):
    _name = 'account.consolidation.data'
    _description = 'Consolidation Data View'

    name = fields.Char(
        string='Name'
    )
    consolidation_period_id = fields.Many2one(
        'account.consolidation.period',
        string='Período',
        index=True,
    )
    main_group = fields.Many2one(
        'account.analytic.group',
        string='Main Group'
    )
    business_group = fields.Many2one(
        'account.analytic.group',
        string='Business ID'
    )
    sector_account_group = fields.Many2one(
        'account.analytic.account',
        string='Sector ID'
    )
    managment_account_group = fields.Many2one(
        'account.analytic.account',
        string='Managment ID'
    )
    company = fields.Many2many(
        'res.company',
        string='Company'
    )
    daughter_account = fields.Many2one(
        'account.analytic.line',
        string='Analytic Account Line'
    )
    daughter_account_id = fields.Integer(
        related='daughter_account.id',
        string='ID Línea',
        store=True,
        readonly=True,
        help='ID de la línea analítica mostrada (para pruebas).',
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        related='daughter_account.account_id',
        string='Analytic Account',
        store=True,
        readonly=True,
        help='Cuenta analítica de la línea mostrada. La contrapartida que anula '
             'un movimiento en el lugar comparte cuenta con el original, de modo '
             'que al agrupar por esta columna ambas quedan en una sola fila.',
    )
    source_analytic_line_id = fields.Many2one(
        'account.analytic.line',
        string='Línea analítica origen',
        ondelete='set null',
        help='Línea analítica de la que proviene esta fila del informe (para filtros).',
    )
    origin_line_id = fields.Integer(
        related='source_analytic_line_id.id',
        string='ID Origen',
        store=True,
        readonly=True,
        help='ID de la línea analítica de origen (para pruebas).',
    )
    description = fields.Char(
        string='Description'
    )
    account_id = fields.Char(
        string='Account ID'
    )
    currency_origin = fields.Many2one(
        'res.currency',
        string='Target Currency'
    )
    currency = fields.Many2one(
        'res.currency',
        string='Currency'
    )
    rate = fields.Float(
        string='Rate'
    )
    amount = fields.Float(
        string='Amount'
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        compute='_compute_project',
        store=True
    )

    def _compute_project(self):
        pass

    def open_line_analytic_form(self):
        self.ensure_one()
        line_analytic_id = self.daughter_account
        if line_analytic_id:
            return {
                'name': 'Line Analytic Form',
                'type': 'ir.actions.act_window',
                'res_model': 'account.analytic.line',
                'res_id': line_analytic_id.id,
                'view_mode': 'form',
            }

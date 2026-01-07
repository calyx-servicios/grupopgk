from odoo import models, fields, _

class ResCompany(models.Model):
    _inherit = 'res.company'

    datareader_tolerance_journal_id = fields.Many2one(
        'account.journal',
        string=_('Diario para Tolerancia'),
        domain="[('company_id', '=', id), ('active', '=', True)]",
        help=_('Diario usado para registrar las diferencias de tolerancia')
    )
    datareader_tolerance_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string=_('Cuenta Analítica para Tolerancia'),
        help=_('Cuenta analítica donde se registrará la diferencia cuando se aplique la tolerancia')
    )


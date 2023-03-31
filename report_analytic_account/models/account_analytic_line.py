from odoo import models, fields, api
from odoo.osv import expression
from collections import defaultdict
from odoo.exceptions import ValidationError

class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    group_parent_id = fields.Many2one('account.analytic.group', related='group_id.parent_id', store=True, readonly=True, compute_sudo=True)
    account_mother_id = fields.Many2one('account.analytic.account', related='account_id.parent_id', store=True, readonly=True, compute_sudo=True)
    balance = fields.Monetary(compute='_compute_debit_credit_balance', string='Balance',  groups='account.group_account_readonly')
    debit = fields.Monetary(compute='_compute_debit_credit_balance', string='Debit', groups='account.group_account_readonly')
    credit = fields.Monetary(compute='_compute_debit_credit_balance', string='Credit', groups='account.group_account_readonly')


    @api.depends('amount')
    def _compute_debit_credit_balance(self):
        Curr = self.env['res.currency']
        domain = [
            ('account_id', 'in', self.ids),
            ('company_id', 'in', [False] + self.env.companies.ids)
        ]
        if self._context.get('from_date', False):
            domain.append(('date', '>=', self._context['from_date']))
        if self._context.get('to_date', False):
            domain.append(('date', '<=', self._context['to_date']))
        if self._context.get('tag_ids'):
            tag_domain = expression.OR([[('tag_ids', 'in', [tag])] for tag in self._context['tag_ids']])
            domain = expression.AND([domain, tag_domain])

        user_currency = self.env.company.currency_id
        credit_groups = self.read_group(
            domain=domain + [('amount', '>=', 0.0)],
            fields=['account_id', 'currency_id', 'amount'],
            groupby=['account_id', 'currency_id'],
            lazy=False,
        )
        data_credit = defaultdict(float)
        for l in credit_groups:
            data_credit[l['account_id'][0]] += Curr.browse(l['currency_id'][0])._convert(
                l['amount'], user_currency, self.env.company, fields.Date.today())

        debit_groups = self.read_group(
            domain=domain + [('amount', '<', 0.0)],
            fields=['account_id', 'currency_id', 'amount'],
            groupby=['account_id', 'currency_id'],
            lazy=False,
        )
        data_debit = defaultdict(float)
        for l in debit_groups:
            data_debit[l['account_id'][0]] += Curr.browse(l['currency_id'][0])._convert(
                l['amount'], user_currency, self.env.company, fields.Date.today())

        for account in self:
            account.debit = abs(data_debit.get(account.id, 0.0))
            account.credit = data_credit.get(account.id, 0.0)
            account.balance = account.credit - account.debit
    
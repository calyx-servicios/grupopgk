from odoo import models, fields, api
from odoo.osv import expression
from collections import defaultdict
from odoo.exceptions import ValidationError

class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    group_parent_id = fields.Many2one('account.analytic.group', related='group_id.parent_id', store=True, readonly=True, compute_sudo=True)
    account_mother_id = fields.Many2one('account.analytic.account', related='account_id.parent_id', store=True, readonly=True, compute_sudo=True)
    balance = fields.Monetary(related='account_id.balance', string='Balance',  groups='account.group_account_readonly')
    debit = fields.Monetary(related='account_id.debit', string='Debit', groups='account.group_account_readonly')
    credit = fields.Monetary(related='account_id.credit', string='Credit', groups='account.group_account_readonly')

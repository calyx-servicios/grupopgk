from odoo import models, fields, api
from odoo.osv import expression
from collections import defaultdict
from odoo.exceptions import ValidationError


class AccountAnalyticGroup(models.Model):
    _inherit = 'account.analytic.group'

    parent_prin_group = fields.Many2one('account.analytic.group', string="Parent prin", ondelete='cascade', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    parent_prin_group_id = fields.Many2one('account.analytic.group', related='group_id.parent_prin_group', store=True, readonly=True, compute_sudo=True)
    group_parent_id = fields.Many2one('account.analytic.group', related='group_id.parent_id', store=True, readonly=True, compute_sudo=True)
    balance = fields.Monetary(related='account_id.balance', string='Balance',  groups='account.group_account_readonly')
    debit = fields.Monetary(related='account_id.debit', string='Debit', groups='account.group_account_readonly')
    credit = fields.Monetary(related='account_id.credit', string='Credit', groups='account.group_account_readonly')    
    grandma_account_id = fields.Many2one('account.analytic.account', string='Grandma analytical account', compute='_compute_grandma_account_id', store=True,)
    mother_account_id = fields.Many2one('account.analytic.account', string='Mother analytical account', compute='_compute_mother_account_id', store=True,)
    move_company_id = fields.Many2one('res.company', string='Compañía', related='move_id.company_id', store=True)

    @api.depends('account_id.parent_id')
    def _compute_grandma_account_id(self):
        for line in self:
            grandma_account = line.account_id.parent_id
            while grandma_account.parent_id:
                grandma_account = grandma_account.parent_id
            line.grandma_account_id = grandma_account

    @api.depends('grandma_account_id')
    def _compute_mother_account_id(self):
        for line in self:
            mother_account = line.account_id.parent_id
            if mother_account == line.grandma_account_id:
                line.mother_account_id = mother_account
            else:
                mother_account = self.env['account.analytic.account'].search([('id', '=', mother_account.id), ('parent_id', '=', line.grandma_account_id.id)])
                line.mother_account_id = mother_account
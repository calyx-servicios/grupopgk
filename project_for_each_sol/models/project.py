from odoo import api, fields, models, _


class Project(models.Model):
    _inherit = "project.project"
    
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", copy=False, ondelete='set null',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", check_company=False,
        help="Analytic account to which this project is linked for financial management. "
             "Use an analytic account to record cost and revenue on your project.")
    
class Task(models.Model):
    _inherit = "project.task"
    
    analytic_account_id = fields.Many2one('account.analytic.account', ondelete='set null',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", check_company=False,
        help="Analytic account to which this task is linked for financial management. "
             "Use an analytic account to record cost and revenue on your task. "
             "If empty, the analytic account of the project will be used.")
from odoo import fields, models

class AccountMove(models.Model):
    _inherit = "account.move"
    
    salary = fields.Boolean("Salary", default=False)
from odoo import models, fields, _

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    

    partner = fields.Many2one("res.users", string="Partner", domain="[('is_partner', '=', True)]")
    is_active = fields.Boolean('Active employee?', default=False, store = True)
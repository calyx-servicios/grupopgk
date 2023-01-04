from odoo import models, fields, _

class Project(models.Model):
    _inherit = 'project.project'
    

    partner = fields.Many2one("res.users", string="Partner", domain="[('is_partner', '=', True)]")
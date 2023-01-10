from odoo import models, fields, _

class ResUsers(models.Model):
    _inherit = 'res.users'

    is_partner = fields.Boolean('Is a Partner?')

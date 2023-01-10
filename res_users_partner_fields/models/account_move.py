from odoo import models, fields, _

class AccountMove(models.Model):
    _inherit = 'account.move'
    

    partner = fields.Many2one("res.users", string="Partner", domain="[('is_partner', '=', True)]")

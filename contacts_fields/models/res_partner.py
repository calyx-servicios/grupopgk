from odoo import fields, models


class Partner(models.Model):
    _inherit = "res.partner"

    is_parent = fields.Boolean("Is company parent", default=False)


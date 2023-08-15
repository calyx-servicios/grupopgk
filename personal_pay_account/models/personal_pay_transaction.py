from odoo import fields, models


class PersonalPayTransaction(models.Model):
    _name = "personal.pay.transaction"
    _description = "Personal Pay Transaction"

    move_id = fields.Many2one(comodel_name="account.move")
    name = fields.Char()

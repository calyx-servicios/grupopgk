from odoo import fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    calendar_id = fields.Many2one("calendar.holidays.timesheets", string="Holidays")
    color = fields.Integer()
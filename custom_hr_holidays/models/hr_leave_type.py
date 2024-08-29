from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = "hr.leave.type"

    assign_start_date = fields.Selection([
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday')
    ], string="Assign Start Date")

    consecutive_days = fields.Boolean(string="Consecutive Days", default=True)
    first_end = fields.Boolean(string="First end", default=False)
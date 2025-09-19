from odoo import _, fields, models

class OverdueReminderStart(models.TransientModel):
    _inherit = "overdue.reminder.start"

    partner_ids = fields.Many2many(
        "res.partner",
        string="Customers",
        domain=[("customer_rank", ">", 0)]
    )
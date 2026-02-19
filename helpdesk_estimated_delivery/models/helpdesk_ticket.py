from odoo import fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    estimated_delivery_date = fields.Date(
        string="Fecha de entrega estimada",
        help="Fecha estimada de resolución/entrega del ticket",
        tracking=True,
    )

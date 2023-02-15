from odoo import fields, models

class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"
    
    days_to_months = fields.Integer("Days to months")


from odoo import api, models, fields, _

class SaleOrder(models.Model):
    _inherit = "sale.order"

    date_of_issue = fields.Datetime(string='Date of issue', readonly=False, required=True)

    
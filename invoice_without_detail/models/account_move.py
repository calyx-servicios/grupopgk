from odoo import models,api,fields, _
from datetime import date
from odoo.exceptions import UserError
import re
import base64

class AccountMove(models.Model):
    _inherit = 'account.move'

    def create_template_report_invoice(self):
        return self.env.ref('invoice_without_detail.action_invoce_without_details').report_action(self)

    

    


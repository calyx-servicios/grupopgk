from odoo import models,api,fields, _
from datetime import date
from odoo.exceptions import UserError
import re
import base64

class AccountMove(models.Model):
    _inherit = 'account.move'

    voucher_ids = fields.One2many('stock.picking.voucher','picking_id','Vouchers',copy=False,compute="def_voucher_ids")
    
    def def_voucher_ids(self):
        for rec in self:
            if rec.sale_order_ids:
                voucher_ids = rec.sale_order_ids.picking_ids.voucher_ids.ids
                rec.voucher_ids = [(6,0, voucher_ids)]
            else:
                rec.voucher_ids = False
                
    def create_template_report_invoice(self):
        return self.env.ref('invoice_without_detail.action_invoce_without_details').report_action(self)

    

    


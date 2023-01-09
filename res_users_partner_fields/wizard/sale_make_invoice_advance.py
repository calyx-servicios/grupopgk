from odoo import models, _


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"
    
    def _prepare_invoice_values(self, order, name, amount, so_line):
        res = super(SaleAdvancePaymentInv, self)._prepare_invoice_values(order, name, amount, so_line)
        if order.partner:
            res['partner'] = order.partner
        return res
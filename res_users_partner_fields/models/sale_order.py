from odoo import models, fields, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    

    partner = fields.Many2one("res.users", string="Partner", domain="[('is_partner', '=', True)]")
    
    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        if self.partner:
            res['partner'] = self.partner.id
        return res
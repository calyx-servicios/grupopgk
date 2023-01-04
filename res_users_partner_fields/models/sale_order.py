from odoo import models, fields, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    partner = fields.Many2one("res.users", string="Partner", domain="[('is_partner', '=', True)]")
    
    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        if self.partner:
            res['partner'] = self.partner.id
        return res

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()

        for rec in self:
            if rec.project_ids:
                for project in rec.project_ids:
                    project.partner = rec.partner
        return res
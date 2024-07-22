from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    oc_salary = fields.Boolean("Salary", default=False)


    def _prepare_invoice(self):
        res = super(PurchaseOrder, self)._prepare_invoice()
        res['salary'] = self.oc_salary
        return res


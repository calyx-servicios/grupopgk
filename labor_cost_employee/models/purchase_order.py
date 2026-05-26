from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    salary = fields.Boolean("Salary", default=False)

    def _sync_oc_salary(self):
        if "oc_salary" not in self._fields:
            return
        for order in self:
            if order.oc_salary != order.salary:
                order.oc_salary = order.salary

    @api.onchange("salary")
    def _onchange_salary(self):
        self._sync_oc_salary()

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sync_oc_salary()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if "salary" in vals:
            self._sync_oc_salary()
        return res

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals["salary"] = self.salary
        return invoice_vals

from odoo import models, api


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.order_id.oc_salary and self.order_id.partner_id:
            # Traigo empleado asociado al partner
            employee = self.order_id.partner_id.associated_employee_id
            if employee and employee.department_id:
                # Recorrer las líneas de la oc y asignar la cuenta analítica del empleado
                for line in self:
                    line.account_analytic_id = employee.department_id.analytic_account

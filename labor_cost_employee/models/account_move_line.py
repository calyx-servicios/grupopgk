from odoo import fields, models, api

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.move_id.salary and self.move_id.partner_id:
            # Traigo empleado asociado al partner
            employee = self.move_id.partner_id.associated_employee_id
            if employee and employee.department_id:
                # Recorrer las líneas de la factura y asignar la cuenta analítica del empleado
                for line in self:
                    line.analytic_account_id = employee.department_id.analytic_account
from odoo import fields, models, api, _

class LaborCostEmployee(models.Model):
    _name = "labor.cost.employee"
    _description = _("Labor cost per employee")

    name = fields.Char("Period")
    employee_id = fields.Many2one("hr.employee", string="Employee")
    cost = fields.Float(string="Cost", digits=(16,2))
    calculation = fields.Text(string="Calculation")

    def open_labor_cost_form(self):
        return {
            'name': self._description,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'labor.cost.employee',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
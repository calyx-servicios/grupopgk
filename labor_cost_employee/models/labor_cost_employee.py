from odoo import fields, models, _

class LaborCostEmployee(models.Model):
    _name = "labor.cost.employee"
    _description = _("Labor cost per employee")
    
    name = fields.Char("Period")
    employee_id = fields.Many2one("hr.employee", string="Employee")
    cost = fields.Float(string="Cost", digits=(16,2))


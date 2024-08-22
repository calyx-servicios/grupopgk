from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

class Employee(models.Model):
    _inherit = 'hr.employee'

    vacation_days = fields.Integer(
        string="Vacation Days",
        compute="_compute_vacation_days",
        store=True
    )

    @api.depends('contract_id.date_start')
    def _compute_vacation_days(self):
        today = fields.Date.today()
        for employee in self:
            if employee.is_active and employee.contract_id:
                if not employee.contract_id.date_end:
                    start_date = employee.contract_id.date_start
                    if start_date:
                        years_of_service = relativedelta(today, start_date).years
                        if years_of_service < 5:
                            employee.vacation_days = 14
                        elif 5 <= years_of_service < 10:
                            employee.vacation_days = 21
                        elif 10 <= years_of_service < 20:
                            employee.vacation_days = 28
                        else:
                            employee.vacation_days = 35
                    else:
                        employee.vacation_days = 0
                else:
                    employee.vacation_days = 0
            else:
                employee.vacation_days = 0
            

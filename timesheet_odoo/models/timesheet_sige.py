from odoo import fields, models, api
from datetime import date


class TimesheetSige(models.Model):
    _name = "timesheet.sige"
    _description = "Timesheet Odoo"

    def set_employee(self):
        user_id = self.env.user.id
        return self.env["hr.employee"].search([("user_id", "=", user_id)])

    name = fields.Char("Name", required=True, readonly=True, copy=False, compute="set_name")
    employee_id = fields.Many2one("hr.employee", "Employee", default=set_employee)
    start_of_period = fields.Date("Start of Period", default=lambda self: date.today())
    end_of_period = fields.Date("End of Period", default=lambda self: date.today())
    holidays = fields.Integer("Holidays")
    working_day = fields.Float("Working Day", related="employee_id.resource_calendar_id.hours_per_day")
    days_to_register = fields.Integer("Days to register")
    required_hours = fields.Float("Required Hours")
    register_hours = fields.Float("Register Hours")
    pending_hours = fields.Float("Pending Hours")
    chargeability = fields.Float("Chargeability", default=100)
    company_id = fields.Many2one("res.company", "Company", default=lambda self: self.env.company)
    timesheet_ids = fields.One2many("account.analytic.line", "timesheet_id", string="Timesheet")
    
    @api.depends("employee_id", "start_of_period")
    def set_name(self):
        for rec in self:
            if rec.employee_id and rec.start_of_period:
                rec.name = str(rec.start_of_period.year) + str(rec.start_of_period.month).zfill(2) + ' - ' + rec.employee_id.name
            else:
                rec.name = '/'


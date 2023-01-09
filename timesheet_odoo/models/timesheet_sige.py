from odoo import fields, models


class TimesheetSige(models.Model):
    _name = "timesheet.sige"
    _description = "Timesheet Odoo"

    employee = fields.Many2one("hr.employee", "Employee")
    start_of_period = fields.Date("Start of Period")
    end_of_period = fields.Date("End of Period")
    holidays = fields.Integer("Holidays")
    working_day = fields.Float("Working Day", related="employee.resource_calendar_id.hours_per_day")
    days_to_register = fields.Integer("Days to register")
    required_hours = fields.Float("Required Hours")
    pending_hours = fields.Float("Pending Hours")
    chargeability = fields.Float("Chargeability")
    company = fields.Many2one("res.company", "Company")
    timesheet = fields.One2many("account.analytic.line", "timesheet_id", string="Timesheet")
from odoo import fields, models, api
from datetime import date
from dateutil.relativedelta import relativedelta


class TimesheetSige(models.Model):
    _name = "timesheet.sige"
    _description = "Timesheet Odoo"

    def set_employee(self):
        user_id = self.env.user.id
        return self.env["hr.employee"].search([("user_id", "=", user_id)])
    
    def set_last_day(self):
        return date.today()  + relativedelta(day=31)
    

    name = fields.Char("Name", required=True, readonly=True, copy=False, compute="set_name")
    employee_id = fields.Many2one("hr.employee", "Employee", default=set_employee)
    start_of_period = fields.Date("Start of Period", default=lambda self: date.today().replace(day=1))
    end_of_period = fields.Date("End of Period", default=set_last_day)
    holidays = fields.Integer("Holidays", compute="_compute_holidays")
    working_day = fields.Float("Working Day", related="employee_id.resource_calendar_id.hours_per_day")
    days_to_register = fields.Integer("Days to register", compute="_compute_days_to_register")
    required_hours = fields.Float("Required Hours", compute="_compute_required_hours")
    register_hours = fields.Float("Register Hours", compute="_compute_register_hour")
    pending_hours = fields.Float("Pending Hours", compute="_compute_pending_hours")
    chargeability = fields.Float("Chargeability", compute="_compute_chargeability")
    company_id = fields.Many2one("res.company", "Company", default=lambda self: self.env.company)
    timesheet_ids = fields.One2many("account.analytic.line", "timesheet_id", string="Timesheet")

    @api.depends("employee_id", "start_of_period")
    def set_name(self):
        for rec in self:
            if rec.employee_id and rec.start_of_period:
                rec.name = str(rec.start_of_period.year) + str(rec.start_of_period.month).zfill(2) + ' - ' + rec.employee_id.name
            else:
                rec.name = '/'

    @api.depends("days_to_register", "working_day")
    def _compute_required_hours(self):
        self.required_hours = self.days_to_register * self.working_day

    @api.depends("start_of_period", "end_of_period")
    def _compute_days_to_register(self):
        self.days_to_register = self._get_total_days(self.start_of_period.day, self.end_of_period.day, True)

    @api.depends("timesheet_ids", "required_hours")
    def _compute_pending_hours(self):
        total_required = self.required_hours
        for odt in self.timesheet_ids:
            total_required -= odt.unit_amount
        self.pending_hours = total_required

    @api.depends("timesheet_ids", "pending_hours")
    def _compute_register_hour(self):
        total = 0
        for line in self.timesheet_ids:
            total += line.unit_amount
        self.register_hours = total

    @api.depends("timesheet_ids")
    def _compute_chargeability(self):
        factured = 0
        for odt in self.timesheet_ids:
            if odt.project_id.allow_billable:
                factured += odt.unit_amount
        if factured == 0:
            self.chargeability = 0
        else:
            self.chargeability = (factured / self.register_hours) * 100

    def _get_total_days(self, start, end, holidays):
        total_days = 0  
        for i in range(start, end + 1):
            this_date = date(date.today().year, date.today().month, i)
            if this_date.weekday() < 5:
                total_days += 1

        if holidays:
            total_days = total_days - self.holidays

        return total_days


    @api.depends("days_to_register")
    def _compute_holidays(self):
        holidays = self.env['calendar.holidays.timesheets'].search([
            "&", ('start_date', '<=', self.end_of_period),('start_date','>=', self.start_of_period),
            ('company_id', '=', self.company_id.id)
        ])
        #TODO filter by employee_id and type of holidays

        self.holidays = len(holidays)
    
    def _cron_monthly_record_sige(self):
        employees = self.env['hr.employee'].search([
            ('active', '=', True)
        ])
        for employee in employees:
            already_exist = self.search([
                "&", ('start_of_period', '=', date.today().replace(day=1)),('end_of_period','=', date.today()+ relativedelta(day=31)),
                ('employee_id', "=", employee.id)
            ])
            if not already_exist:
                self.create({
                    'employee_id': employee.id,
                })
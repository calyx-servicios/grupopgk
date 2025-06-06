from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import calendar


class TimesheetSige(models.Model):
    _name = "timesheet.sige"
    _description = "Timesheet Odoo"
    _order = "start_of_period desc"

    def set_employee(self):
        user_id = self.env.user.id
        return self.env["hr.employee"].search([("user_id", "=", user_id),('is_active', '=', True)])

    def set_last_day(self):
        start_of_period = self.start_of_period or date.today().replace(day=1)
        return start_of_period  + relativedelta(day=31)

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
    company_id = fields.Many2one("res.company", "Company", related="employee_id.company_id")
    period_id = fields.Many2one("period.sige", "Period")
    timesheet_ids = fields.One2many("account.analytic.line", "timesheet_id", string="Timesheet")
    state = fields.Selection([
        ("open","Open"),
        ("sent","Sent"),
        ("close","Close")
    ], "State", index=True, default="open")
    user_readonly = fields.Boolean(string="¿User readonly?", compute="_compute_user_readonly")

    _sql_constraints = [
        ('unique_period_employee', 'unique(period_id, employee_id)', _('Only one record allowed per period and employee.')),
    ]

    def _compute_user_readonly(self):
        if self.env.user.has_group('timesheet_odoo.group_timesheet_sige_admin'): 
            self.user_readonly = False
        else:
            self.user_readonly = True


    @api.depends("start_of_period")
    def set_name(self):
        for rec in self:
            if rec.start_of_period:
                rec.name = str(rec.start_of_period.year) + str(rec.start_of_period.month).zfill(2)
            else:
                rec.name = '/'

    @api.depends("days_to_register", "working_day")
    def _compute_required_hours(self):
        self.required_hours = self.days_to_register * self.working_day

    @api.depends("start_of_period", "end_of_period")
    def _compute_days_to_register(self):
        self.days_to_register = self._get_total_days(True)

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
            self.chargeability = (factured / self.required_hours) * 100

    def _get_total_days(self, holidays):
        total_days = 0
        for i in range(self.start_of_period.day, self.end_of_period.day + 1):
            this_date = date(self.start_of_period.year, self.start_of_period.month, i)
            if this_date.weekday() < 5:
                total_days += 1

        if holidays:
            total_days = total_days - self.holidays

        return total_days

    @api.depends("days_to_register")
    def _compute_holidays(self):
        holidays = self.env['calendar.holidays.timesheets'].search([
            "&", ('start_date', '<=', self.end_of_period),('start_date','>=', self.start_of_period)
        ])
        total_holidays = 0
        holiday = holidays.filtered(lambda h: h.type == 'holiday')
        if holiday:
            total_holidays = len(holiday)
        non_working_day = holidays.filtered(lambda h: h.type == 'non_work_day' and h.is_holiday == True)
        if non_working_day:
            total_holidays = total_holidays + len(non_working_day)
        special_holidays = holidays.filtered(lambda h: h.type == 'special_holiday')

        for special_holiday in special_holidays:
            if self.employee_id.job_id in special_holiday.jobs_ids:
                total_holidays += 1
        self.holidays = total_holidays

    def send_period(self):
        self.write({
            'state': 'sent'
        })

    def recovery_period(self):
        self.write({
            'state': 'open'
        })
        
    def create_period_sige(self, period):
        all_companies = self.env['res.company'].search([('id', '!=', 5)])
        all_company_ids = set(all_companies.ids)
        env_company_ids = set(company.id for company in self.env.companies if company.id != 5)
        if env_company_ids != all_company_ids:
            raise UserError("Debe seleccionar todas las compañías para poder cerrar y crear un nuevo período.")
        else:
            employees = self.env['hr.employee'].search([
                ('active', '=', True),
                ('is_active', '=', True)
            ])
            end_of_period = period.end_of_period + relativedelta(day=31)
            for employee in employees:
                already_exist = self.search([
                    ('start_of_period', '=', period.start_of_period),('end_of_period','=', end_of_period),
                    ('employee_id', "=", employee.id), ('period_id','=',period.id)
                ])
                if not already_exist:
                    self.create({
                        'employee_id': employee.id,
                        'period_id': period.id,
                        'start_of_period': period.start_of_period,
                        'end_of_period': end_of_period
                    })

    def delete_timesheet_sige(self):

        # Recupera los registros seleccionados en la vista tree
        selected_records= self.env["timesheet.sige"].browse(self.ids)

        # Elimina los registros seleccionados
        for record in selected_records:
            record.unlink()
    
    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        # Filtra los registros para mostrar solo aquellos que tengan un period.sige asociado y exista en la base de datos
        if self.env.context.get('filter_by_period', False):
            period_ids = self.env['period.sige'].search([]).ids
            args += [('period_id', 'in', period_ids)]
        return super(TimesheetSige, self).search(args, offset=offset, limit=limit, order=order, count=count)

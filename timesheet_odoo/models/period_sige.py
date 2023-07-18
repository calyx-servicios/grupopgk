from odoo import fields, models, api, _
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError, UserError

class PeriodSige(models.Model):
    _name = "period.sige"
    _description = "Periods"

    name = fields.Char("Name", readonly=True, copy=False, compute="set_name")
    start_of_period = fields.Date("Start of Period", default=lambda self: date.today().replace(day=1))
    end_of_period = fields.Date("End of Period", compute="_compute_last_day")
    count_employees = fields.Integer("Enabled users", compute="_compute_count_employees")
    sent_periods = fields.Integer("Sent", compute="_compute_sent_periods")
    pending_periods = fields.Integer("To do", compute="_compute_pending_periods")
    employee_ids = fields.Many2many("hr.employee", string="Employees pending", compute="_compute_employee_ids")
    user_id = fields.Many2one('res.users','Current User', default=lambda self: self.env.user)
    has_timesheet_sige_admin = fields.Boolean(string="Has administrator sige?", compute="_compute_has_timesheet_sige_admin", store=False, default=False)
    state = fields.Selection([
        ("open","Open"),
        ("close","Close")
    ], "State", index=True, default="open")

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Period must be unique!')
    ]

    @api.depends('user_id')
    def _compute_has_timesheet_sige_admin(self):
        for record in self:
            user = self.env.user
            group = user.has_group('timesheet_odoo.group_timesheet_sige_admin')

            if group:
                record.has_timesheet_sige_admin = True
            else:
                record.has_timesheet_sige_admin = False

    @api.depends("start_of_period")
    def set_name(self):
        for rec in self:
            if rec.start_of_period:
                rec.name = rec.start_of_period.strftime("%B %Y")
            else:
                rec.name = '/'

    @api.depends("start_of_period")
    def _compute_last_day(self):
        this_date = self.start_of_period.replace(day=6)
        if this_date.weekday() == 6:
            this_date = self.start_of_period.replace(day=8)
        elif this_date.weekday() == 7:
            this_date = self.start_of_period.replace(day=7)
        self.end_of_period = this_date

    @api.depends("start_of_period")
    def _compute_employee_ids(self):
        timesheet_sige = self.env['timesheet.sige'].search([('period_id','=',self.id),('state','=','open')])
        employees = timesheet_sige.mapped("employee_id")
        self.employee_ids = [(6, 0, employees.ids)]

    @api.depends("start_of_period")
    def _compute_count_employees(self):
        employees = self.env['hr.employee'].search([
            ('active', '=', True)
        ])
        self.count_employees = len(employees)

    @api.depends("start_of_period")
    def _compute_sent_periods(self):
        timesheet_sige = self.env['timesheet.sige'].search([
            ('period_id','=',self.id),('state','=','sent')
        ])
        self.sent_periods = len(timesheet_sige)

    @api.depends("start_of_period")
    def _compute_pending_periods(self):
        timesheet_sige = self.env['timesheet.sige'].search([('period_id','=',self.id),('state','=','open')])
        self.pending_periods = len(timesheet_sige)

    @api.model
    def create(self, vals):
        period = self.env["period.sige"].search([("state","=","open")])
        if not period:
            return super(PeriodSige, self).create(vals)
        else:
            raise ValidationError(_("There can only be one open period at a time!"))

    def close_period(self):
        line_obj = self.env["account.analytic.line"]
        ts_obj = self.env["timesheet.sige"]
        if self.state == 'close':
            raise UserError(_('The period is already closed'))
        hours_to_allocate = self.env.ref("timesheet_odoo.hours_to_allocate")
        for employee in self.employee_ids:
            ts_employee = ts_obj.search([('period_id','=',self.id),("employee_id","=", employee.id)])
            if ts_employee.pending_hours != 0:
                values = {
                    "project_id": hours_to_allocate.id,
                    "name": _("Hours to allocate"),
                    "unit_amount": ts_employee.pending_hours,
                    "company_id": hours_to_allocate.analytic_account_id.company_id.ids or [hours_to_allocate.company_id.id],
                    "timesheet_id": ts_employee.id
                }
                line_obj.create(values)

        timesheet = ts_obj.search([('period_id','=',self.id)])
        timesheet.write({'state':'close'})
        self.write({'state':'close'})
        date_new_period = self.start_of_period + relativedelta(months=1)
        vals = {
            "start_of_period": date_new_period,
            "name": date_new_period.strftime("%B %Y")
        }
        new_period_id = self.create(vals)
        ts_obj.create_period_sige(new_period_id)


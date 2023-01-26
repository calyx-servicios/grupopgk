from odoo import fields, models, api, _
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError

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
    state = fields.Selection([
        ("open","Open"),
        ("close","Close")
    ], "State", index=True, default="open")
    
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
        ts_obj = self.env["timesheet.sige"]
        timesheet = ts_obj.search([('period_id','=',self.id)])
        timesheet.write({'state':'close'})
        # for employee in self.employee_ids:
        #     pass #TODO: REIMPUTAR HORAS
        self.write({'state':'close'})
        date_new_period = self.start_of_period + relativedelta(months=1)
        vals = {
            "start_of_period": date_new_period,
            "name": date_new_period.strftime("%B %Y")
        }
        new_period_id = self.create(vals)
        ts_obj.create_period_sige(new_period_id)

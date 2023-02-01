from odoo import models, fields, api
import datetime

class CalendarHolidaysTimesheets(models.Model):
    _name = "calendar.holidays.timesheets"
    _description = "Calendar Holidays Timesheets"
    _order = "start_date desc"
    

    name = fields.Char('Subject')
    description = fields.Html('Description')
    user_id = fields.Many2one('res.users', 'Created by', default=lambda self: self.env.user)
    allday = fields.Boolean('All Day', default=False)
    start_date = fields.Date('Start date', required=True, default=lambda self: fields.Date.today())
    end_date = fields.Date('End date', required=True, default=lambda self: fields.Date.today() + datetime.timedelta(days=1))
    duration = fields.Float('Duration', compute='_compute_duration', store=True, readonly=False)
    partners_ids = fields.Many2many("res.partner", string="Partners")
    analytic_account_ids = fields.Many2many('account.analytic.account', string='Analytics Accounts')
    company_id = fields.Many2one("res.company", "Company", default=lambda self: self.env.company)
    type = fields.Selection([
        ('holiday', 'Holiday'),
        ('special_holiday', 'Special holiday'),
        ('non_working_day', 'Non-working day'),
        ('other', 'Other'),
    ], string='Type', default='holiday')
    is_holiday = fields.Boolean('Count as holiday?')
    jobs_ids = fields.Many2many('hr.job', string='Jobs')

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for event in self:
            event.duration = self._get_duration(event.start_date, event.end_date)
    
    def _get_duration(self, start, end):
        if not start or not end:
            return 0
        duration = (end - start).total_seconds() / 3600
        return round(duration, 2)



from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import calendar
from datetime import timedelta, datetime, date


class HrLeave(models.Model):
    _inherit = "hr.leave"

    job_id = fields.Many2one(
        'hr.job',
        related='employee_id.job_id',
        string='Job Position',
        readonly=True,
        store=True,
        tracking=True
    )

    days_remaining = fields.Integer(string="Days Remaining", compute='_compute_days_remaining')

    today = fields.Date(string="Today", default=lambda self: fields.Date.today(), readonly=True)

    @api.depends('date_from', 'date_to')
    def _compute_days_remaining(self):
        for leave in self:
            if leave.state == 'validate':
                if leave.date_from and leave.date_to:
                    today = date.today()
                    date_to = leave.date_to.date()
                    date_from = leave.date_from.date()
                    if today < date_from:
                        leave.days_remaining = 0
                    elif today <= date_to:
                        leave.days_remaining = (date_to - today).days
                    else:
                        leave.days_remaining = 0
                else:
                    leave.days_remaining = 0
            else: 
                leave.days_remaining = 0


    @api.depends("date_from", "date_to", "employee_id")
    def _compute_number_of_days(self):
        super(HrLeave, self)._compute_number_of_days()
        for holiday in self:
            if holiday.date_from and holiday.date_to:
                # Verificar si consecutive_days es True
                if holiday.holiday_status_id.consecutive_days:
                    delta = holiday.date_to - holiday.date_from
                    holiday.number_of_days = delta.days + 1  # +1 para incluir ambos días
                else:
                    pass
            else:
                pass
            
    @api.model_create_multi
    def create(self, vals_list):
        self.check_start_day(vals_list)
        return super(HrLeave, self).create(vals_list)

    def check_start_day(self, vals_list):
        for vals in vals_list:
            holiday_status_id = vals.get('holiday_status_id')
            date_from = vals.get('date_from')
            
            holiday_status = self.env['hr.leave.type'].search([('id', "=", holiday_status_id)])
            if holiday_status and date_from:
                start_date = holiday_status.assign_start_date
                
                # Obtener el día de la semana de date_from (0=Monday, 6=Sunday)
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d %H:%M:%S').date() 
                day_of_week = date_from_obj.weekday()
                # Mapeo de los días de la semana de inglés a español
                day_map = {
                    'monday': 'lunes',
                    'tuesday': 'martes',
                    'wednesday': 'miércoles',
                    'thursday': 'jueves',
                    'friday': 'viernes',
                    'saturday': 'sábado',
                    'sunday': 'domingo'
                }

                assign_start_day = list(calendar.day_name).index(day_map[start_date.lower()])
                
                result = self.check_date_from(date_from)
                # Verificar si el día de inicio es el mismo que assign_start_date
                if not result and day_of_week != assign_start_day:
                    raise ValidationError(_("The start date of the holiday must be a %s.") % start_date)
                else:
                    pass
    
    def check_date_from(self, date_from):
        # Verificamos que la fecha de inicio si no es lunes que se fije que ese lunes no es feriado.
        # Por ejemplo la fecha de inicio es un martes y el lunes anterior es feriado, en ese caso debe dejar cargar vacaciones
        calendar_holidays = self.env['calendar.holidays.timesheets'].search([])
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d %H:%M:%S').date() - timedelta(days=1)
        all_holiday_dates = []
        for holiday in calendar_holidays:
            holiday_start_date = holiday.start_date.date() if isinstance(holiday.start_date, datetime) else holiday.start_date
            if holiday_start_date == date_from_obj:
                return True

        return False

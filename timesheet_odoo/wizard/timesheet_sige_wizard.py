from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime
from dateutil.relativedelta import relativedelta




# Define the wizard model
class TimesheetSigeWizard(models.TransientModel):
    _name = 'timesheet.sige.wizard'
    _description = 'Wizard to add timesheet.sige records'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    start_of_period = fields.Date(string='Start of Period', required=True)
    end_of_period = fields.Date(string='End of Period', compute='_compute_end_of_period', required=True)
    period_id = fields.Many2one('period.sige', string='Period', required=True)
    employee_ids = fields.Many2many('hr.employee', compute='_compute_employee_ids', store=False)
    state = fields.Selection(related='period_id.state', string='State period')

    @api.depends('period_id')
    def _compute_employee_ids(self):
        # Aqui reviso cuales son los empleados que no tienen creado su timesheet en el periodo, es para cuando ingresan empleados nuevos en un mes que ya se crearon todos los timesheet. 
        for wizard in self:
            all_employee_ids = self.env['hr.employee'].search([('is_active', '=', True)]).ids
            if wizard.period_id:
                existing_timesheets = self.env['timesheet.sige'].search([('period_id', '=', wizard.period_id.id)])
                existing_employee_ids = existing_timesheets.mapped('employee_id.id')
                wizard.employee_ids = [(6, 0, list(set(all_employee_ids) - set(existing_employee_ids)))]
            else:
                wizard.employee_ids = [(6, 0, list(all_employee_ids))]

    @api.depends('period_id')
    def _compute_end_of_period(self):
        for record in self:
            if record.period_id:
                # Obtener el primer día del periodo seleccionado
                start_date = record.period_id.start_of_period 

                # Obtener el último día del periodo seleccionado
                end_date = start_date + relativedelta(months=1, days=-1)
                
                record.end_of_period = end_date
            else:
                record.end_of_period = False

    
    def verificate_start_of_period(self):
        # Aqui verifico que la fecha de inicio sea del mismo mes y año que la fecha de fin y que tambien sea menor
        if self.start_of_period and self.end_of_period:
            start_date = self.start_of_period
            end_date = self.end_of_period
            if start_date < end_date.replace(day=1) or start_date.month != end_date.month or start_date.year != end_date.year:
                raise UserError("La fecha de inicio del período debe ser menor o igual a la fecha de fin y deben estar en el mismo mes y año.")

    def action_create_timesheet(self):
        self.ensure_one()
        self.verificate_start_of_period()
        period_id = self.env.context.get('active_id')
        timesheet_vals = {
            'employee_id': self.employee_id.id,
            'start_of_period': self.start_of_period,
            'end_of_period': self.end_of_period,
            'period_id': self.period_id.id,
        }
        self.env['timesheet.sige'].create(timesheet_vals)

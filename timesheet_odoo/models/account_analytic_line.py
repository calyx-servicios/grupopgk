from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    timesheet_id = fields.Many2one("timesheet.sige", string="Timesheet", ondelete="cascade")
    project_id = fields.Many2one(domain = [('allow_timesheets', '=', True)])
    project_no_facturable = fields.Boolean(compute='_compute_no_facturable')
    
    @api.constrains('timesheet_id', 'unit_amount')
    def _check_timesheet_line(self):
        for record in self:
            if record.timesheet_id:
                if record.unit_amount <= 0 or record.unit_amount % 0.5 != 0:
                    raise ValidationError(_("Hours should be a non-zero multiple of 0.5."))
    
    @api.depends('project_id')
    def _compute_no_facturable(self):
        for record in self:
            if record.project_id and record.project_id.name and 'no facturable' in record.project_id.name.lower():
                record.project_no_facturable = True
            else:
                record.project_no_facturable = False 
    
    def write(self, vals):
        # Verifica si la línea analítica está relacionada con un timesheet
        if self.timesheet_id:
            # Establece la fecha de la línea analítica a timesheet.end_of_period
            vals['date'] = self.timesheet_id.end_of_period 
        return super().write(vals)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('timesheet_id', False):
                timesheet_id = self.env['timesheet.sige'].browse(vals['timesheet_id'])
                vals['date'] = timesheet_id.end_of_period
        return super(AccountAnalyticLine, self).create(vals_list)
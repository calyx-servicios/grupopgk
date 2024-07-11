from odoo import api, models, fields, _
from datetime import date
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    

    partner = fields.Many2one("res.users", string="Partner", domain="[('is_partner', '=', True)]")
    entry_date = fields.Date(string="Entry Date", required=True)
    exit_date = fields.Date(string="Exit Date")
    is_active = fields.Boolean('Active Employee?', compute='_compute_is_active', store=True, default=True)
    
    @api.depends('entry_date', 'exit_date')
    def _compute_is_active(self):
        for record in self:
            if record.entry_date and (not record.exit_date or record.exit_date > date.today()):
                record.is_active = True
            else:
                record.is_active = False

    @api.constrains('entry_date', 'exit_date')
    def _check_dates(self):
        for record in self:
            if record.entry_date and record.exit_date and record.exit_date <= record.entry_date:
                raise ValidationError(_("Exit Date must be greater than Entry Date."))
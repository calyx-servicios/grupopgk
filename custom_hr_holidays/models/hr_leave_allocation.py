from odoo import fields, models, api
from datetime import datetime

class HrLeaveAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    state = fields.Selection(selection_add=[
        ('prescriptas', 'Prescriptas')])

    state_prescriptas = fields.Boolean(string="Is Prescriptas", compute='_compute_state_prescriptas')

    days_by_antiquity = fields.Selection(
        [
            ("14 days", "14 days"),
            ("21 days", "21 days"),
            ("28 days", "28 days"),
            ("35 days", "35 days"),
        ],
        string="Days by antiquity",
    )

    days_remaining = fields.Float(related="holiday_status_id.virtual_remaining_leaves", string="Days Remaining")

    @api.depends("holiday_type", "days_by_antiquity")
    def _compute_from_holiday_type(self):
        super(HrLeaveAllocation, self)._compute_from_holiday_type()

        for holiday in self:
            if holiday.holiday_type == "employee" and holiday.days_by_antiquity:
                antiquity_days = int(holiday.days_by_antiquity.split()[0])
                filtered_employees = self.env["hr.employee"].search(
                    [("vacation_days", "=", antiquity_days), ("is_active", "!=", False)]
                )
                holiday.employee_ids = filtered_employees

                
    @api.depends('date_to')
    def _compute_state_prescriptas(self):
        self.state_prescriptas = False
        today = datetime.today().date()
        for allocation in self:
            if allocation.date_to and allocation.date_to < today:
                allocation.write({'state': 'prescriptas'})
    
    @api.model
    def _cron_update_prescriptas_state(self):
        allocations = self.search([('state', '!=', 'prescriptas'), ('date_to', '<', fields.Date.today())])
        allocations.write({'state': 'prescriptas'})
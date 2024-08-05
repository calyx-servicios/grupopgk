from odoo import fields, models, api
from datetime import datetime

class HrLeaveAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    state = fields.Selection(selection_add=[
        ('prescriptas', 'Prescriptas')])

    state_prescriptas = fields.Boolean(string="Is Prescriptas", compute='_compute_state_prescriptas')

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
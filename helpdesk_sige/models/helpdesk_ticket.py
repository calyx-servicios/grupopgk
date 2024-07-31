from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    all_sige = fields.Boolean(string="ALL SIGE", default=False, compute='_compute_all_sige')


    def charge_manually_hours_sige(self):
        for line in self.timesheet_ids:
            if not line.charge_sige:
                line.write({'charge_sige' : False})

    def _compute_all_sige(self):
        for record in self:
            record.all_sige = all(value.charge_sige for value in record.timesheet_ids)

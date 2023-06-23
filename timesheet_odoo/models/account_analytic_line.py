from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    timesheet_id = fields.Many2one("timesheet.sige", string="Timesheet", ondelete="cascade")

    @api.constrains('timesheet_ids')
    def _check_timesheet_line(self):
        for timesheet in self:
            for line in timesheet.timesheet_ids:
                if line.unit_amount < 0.5:
                    raise ValidationError(_("Hours should not be less than 0.5."))

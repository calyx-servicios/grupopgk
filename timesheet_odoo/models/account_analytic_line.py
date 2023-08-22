from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    timesheet_id = fields.Many2one("timesheet.sige", string="Timesheet", ondelete="cascade")

    @api.constrains('timesheet_id', 'unit_amount')
    def _check_timesheet_line(self):
        for record in self:
            if record.timesheet_id:
                if record.unit_amount <= 0 or record.unit_amount % 0.5 != 0:
                    raise ValidationError(_("Hours should be a non-zero multiple of 0.5."))

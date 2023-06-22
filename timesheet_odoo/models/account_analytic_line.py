from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    timesheet_id = fields.Many2one("timesheet.sige", string="Timesheet", ondelete="cascade")

    @api.constrains('unit_amount')
    def _check_unit_amount(self):
        for line in self:
            if line.unit_amount == 0:
                raise ValidationError(_("Cannot create/update timesheet line with 0 hours."))
            if line.unit_amount % 0.5 != 0:
                raise ValidationError(_("Fraction should be 0.5."))

from odoo import api, models


class TimesheetSige(models.Model):
    _inherit = "timesheet.sige"

    @api.depends(
        "timesheet_ids.unit_amount", "timesheet_ids.uat_rework_event_id",
        "timesheet_ids.project_id.allow_billable", "required_hours",
    )
    def _compute_chargeability(self):
        for sheet in self:
            billable = sum(sheet.timesheet_ids.filtered(
                lambda line: line.project_id.allow_billable and not line.uat_rework_event_id
            ).mapped("unit_amount"))
            sheet.chargeability = (
                billable / sheet.required_hours * 100 if sheet.required_hours else 0
            )

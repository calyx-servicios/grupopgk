from odoo import api, fields, models


class HrTimesheetSwitch(models.TransientModel):
    _inherit = "hr.timesheet.switch"

    hour_type_id = fields.Many2one(
        "timesheet.hour.type",
        string="Tipo de hora",
        required=True,
        domain=[("active", "=", True)],
    )
    activity_date = fields.Date(
        string="Fecha de actividad",
        required=True,
        default=fields.Date.context_today,
    )
    hour_type_in_management_report = fields.Boolean(
        related="hour_type_id.include_in_management_report",
    )

    @api.onchange("date_time")
    def _onchange_date_time_activity_date(self):
        for wizard in self:
            if wizard.date_time:
                date_time = fields.Datetime.to_datetime(wizard.date_time)
                wizard.activity_date = fields.Datetime.context_timestamp(
                    wizard,
                    date_time,
                ).date()

    def _prepare_default_values(self, analytic_line):
        values = super()._prepare_default_values(analytic_line)
        values.update({
            "hour_type_id": analytic_line.hour_type_id.id,
            "activity_date": analytic_line.activity_date,
        })
        return values

    def _prepare_copy_values(self, record):
        values = super()._prepare_copy_values(record)
        values.update({
            "hour_type_id": record.hour_type_id.id,
            "activity_date": record.activity_date,
        })
        return values

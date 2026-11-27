from odoo import fields, models


class TimesheetReclassifyLine(models.Model):
    _inherit = "timesheet.reclassify.line"

    hour_type_id = fields.Many2one(
        "timesheet.hour.type",
        string="Tipo de hora",
        ondelete="restrict",
    )
    activity_date = fields.Date(string="Fecha de actividad")


class TimesheetReclassify(models.Model):
    _inherit = "timesheet.reclassify"

    def _process_done(self):
        self = self.sudo()
        analytic_lines = self.env["account.analytic.line"]
        for request in self:
            for line in request.line_ids:
                if line.analytic_line:
                    if line.unit_amount_reclassify:
                        line.analytic_line.write({
                            "unit_amount": line.unit_amount_reclassify,
                            "hour_type_id": line.hour_type_id.id,
                            "activity_date": line.activity_date,
                        })
                    else:
                        line.analytic_line.unlink()
                elif line.unit_amount_reclassify:
                    new_line = analytic_lines.create({
                        "timesheet_id": request.ticket_id.id,
                        "project_id": line.project_id.id,
                        "unit_amount": line.unit_amount_reclassify,
                        "user_id": request.user_id.id if request.user_id else False,
                        "employee_id": (
                            request.user_id.employee_id.id
                            if request.user_id and request.user_id.employee_id
                            else False
                        ),
                        "name": line.name,
                        "hour_type_id": line.hour_type_id.id,
                        "activity_date": line.activity_date,
                    })
                    line.analytic_line = new_line.id

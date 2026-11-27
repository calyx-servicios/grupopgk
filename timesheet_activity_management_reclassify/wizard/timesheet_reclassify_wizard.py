from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TimesheetReclassifyWizard(models.TransientModel):
    _inherit = "timesheet.reclassify.wizard"

    def _onchange_reclassify_id(self):
        result = super()._onchange_reclassify_id()
        for line in self.reclassify_ids.filtered("analytic_line"):
            line.hour_type_id = line.analytic_line.hour_type_id
            line.activity_date = line.analytic_line.activity_date
        return result

    def reclassify(self):
        sum_unit_amount = sum(self.mapped("reclassify_ids.unit_amount"))
        sum_reclassified = sum(
            self.mapped("reclassify_ids.unit_amount_reclassify")
        )
        if not self.reclassify_ids:
            raise ValidationError(_("There are not lines to reclassify"))
        if sum_unit_amount != sum_reclassified:
            raise ValidationError(_(
                "The quantity of hours to reclassify must be equal to the "
                "quantity of hours."
            ))
        for line in self.reclassify_ids:
            if line.unit_amount_reclassify and (
                not line.hour_type_id or not line.activity_date
            ):
                raise ValidationError(_(
                    "Indique el tipo de hora y la fecha de actividad antes "
                    "de reclasificar."
                ))
        requests = self.env["timesheet.reclassify"].sudo()
        request_lines = self.env["timesheet.reclassify.line"].sudo()
        ticket_id = self.env.context.get("active_id")
        if requests.search_count([
            ("state", "=", "pending"),
            ("ticket_id", "=", ticket_id),
        ]):
            raise ValidationError(_("There is a pending reclassification"))
        request = requests.create({"ticket_id": ticket_id})
        for line in self.reclassify_ids:
            request_lines.create({
                "project_id": line.project_id.id,
                "name": line.name,
                "unit_amount": line.unit_amount,
                "unit_amount_reclassify": line.unit_amount_reclassify,
                "reclassify_id": request.id,
                "analytic_line": (
                    line.analytic_line.id if line.analytic_line else False
                ),
                "hour_type_id": line.hour_type_id.id,
                "activity_date": line.activity_date,
            })
        return {"type": "ir.actions.act_window_close"}


class TimesheetLineReclassifyWizard(models.TransientModel):
    _inherit = "timesheet.line.reclassify.wizard"

    hour_type_id = fields.Many2one(
        "timesheet.hour.type",
        string="Tipo de hora",
        ondelete="restrict",
    )
    activity_date = fields.Date(string="Fecha de actividad")

    @api.constrains("unit_amount_reclassify", "hour_type_id", "activity_date")
    def _check_classification(self):
        for line in self:
            if line.unit_amount_reclassify and (
                not line.hour_type_id or not line.activity_date
            ):
                raise ValidationError(_(
                    "Indique el tipo de hora y la fecha de actividad para "
                    "las horas reclasificadas."
                ))

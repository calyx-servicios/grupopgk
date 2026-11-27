from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TimesheetManagementWeeklyRunWizard(models.TransientModel):
    _name = "timesheet.management.weekly.run.wizard"
    _description = "Reenviar reporte semanal de gestión"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        domain=lambda self: [("id", "in", self.env.companies.ids)],
    )
    week_start = fields.Date(
        string="Lunes de la semana a reportar",
        required=True,
        default=lambda self: self._default_week_start(),
    )

    @api.model
    def _default_week_start(self):
        timezone = pytz.timezone("America/Argentina/Buenos_Aires")
        today = datetime.now(timezone).date()
        monday = today - timedelta(days=today.weekday())
        return monday - timedelta(days=7)

    @api.constrains("week_start")
    def _check_monday(self):
        for wizard in self:
            if wizard.week_start and wizard.week_start.weekday() != 0:
                raise ValidationError(_("La fecha seleccionada debe ser lunes."))

    def action_send(self):
        if not self.env.user.has_group(
            "timesheet_activity_management.group_timesheet_activity_admin"
        ):
            raise UserError(_("No tiene permiso para regenerar este reporte."))
        self.ensure_one()
        if self.company_id not in self.env.companies:
            raise UserError(_("No tiene acceso a la compañía seleccionada."))
        config = self.env["timesheet.management.report.config"].search([
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if not config:
            raise UserError(_(
                "Configure el destinatario semanal para la compañía %s."
            ) % self.company_id.display_name)
        run_model = self.env["timesheet.management.weekly.run"].sudo()
        run = run_model._get_or_create_run(
            self.company_id,
            self.week_start,
            self.week_start + timedelta(days=6),
        )
        run._queue_report(config.sudo(), manual=True)
        return {"type": "ir.actions.act_window_close"}

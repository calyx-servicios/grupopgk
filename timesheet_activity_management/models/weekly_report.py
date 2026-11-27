import base64
import html
import io
import logging
from datetime import datetime, time, timedelta

import pytz
import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)
_ARGENTINA_TZ = pytz.timezone("America/Argentina/Buenos_Aires")


class TimesheetManagementWeeklyRun(models.Model):
    _name = "timesheet.management.weekly.run"
    _description = "Envío semanal de horas de gestión"
    _order = "week_start desc, company_id"

    company_id = fields.Many2one("res.company", required=True, readonly=True)
    week_start = fields.Date(string="Desde", required=True, readonly=True)
    week_end = fields.Date(string="Hasta", required=True, readonly=True)
    state = fields.Selection(
        [
            ("queued", "Correo en cola"),
            ("error", "Error"),
        ],
        default="error",
        required=True,
        readonly=True,
    )
    mail_id = fields.Many2one("mail.mail", string="Último correo", readonly=True)
    generated_at = fields.Datetime(string="Generado", readonly=True)
    manual_resend_count = fields.Integer(
        string="Reenvíos manuales",
        default=0,
        readonly=True,
    )
    error_message = fields.Text(string="Último error", readonly=True)

    _sql_constraints = [
        (
            "timesheet_management_weekly_company_week_unique",
            "unique(company_id, week_start)",
            "Ya existe una ejecución para esta compañía y semana.",
        ),
    ]

    @api.constrains("week_start")
    def _check_week_starts_on_monday(self):
        for run in self:
            if run.week_start and run.week_start.weekday() != 0:
                raise ValidationError(_("El reporte debe comenzar un lunes."))

    @api.model
    def _previous_week_range(self, now=None):
        local_now = now.astimezone(_ARGENTINA_TZ) if now else datetime.now(
            _ARGENTINA_TZ
        )
        this_monday = local_now.date() - timedelta(
            days=local_now.weekday()
        )
        previous_monday = this_monday - timedelta(days=7)
        return previous_monday, this_monday - timedelta(days=1)

    @api.model
    def _report_domain(self, company, week_start, week_end):
        return [
            ("company_id", "=", company.id),
            ("activity_date", ">=", week_start),
            ("activity_date", "<=", week_end),
            ("hour_type_id.include_in_management_report", "=", True),
        ]

    @api.model
    def _render_xlsx(self, lines, week_start, week_end):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Horas de gestión")
        headers = [
            "Fecha de actividad",
            "Empleado",
            "Cliente",
            "Proyecto",
            "Tema",
            "Tipo de hora",
            "Horas",
            "Justificación",
            "PM",
            "Líder técnica",
            "Funcionales",
            "Estado SIGE",
        ]
        header_format = workbook.add_format({"bold": True, "bg_color": "#D9EAF7"})
        for column, title in enumerate(headers):
            worksheet.write_string(0, column, title, header_format)
        for row, line in enumerate(lines, start=1):
            values = [
                (line.activity_date.isoformat() if line.activity_date else ""),
                line.employee_id.name or "",
                line.client_id.name or "",
                line.project_id.name or "",
                line.task_id.name or "",
                line.hour_type_id.name or "",
            ]
            for column, value in enumerate(values):
                worksheet.write_string(row, column, str(value))
            worksheet.write_number(row, 6, line.unit_amount)
            worksheet.write_string(row, 7, line.name or "")
            worksheet.write_string(
                row,
                8,
                line.project_manager_id.name or "",
            )
            worksheet.write_string(
                row,
                9,
                line.technical_leader_id.name or "",
            )
            worksheet.write_string(
                row,
                10,
                ", ".join(line.functional_user_ids.mapped("name")),
            )
            worksheet.write_string(row, 11, dict(
                line._fields["timesheet_state"].selection
            ).get(line.timesheet_state, ""))
        total_row = len(lines) + 1
        worksheet.write_string(total_row, 5, "Total horas", header_format)
        worksheet.write_number(
            total_row,
            6,
            sum(lines.mapped("unit_amount")),
            header_format,
        )
        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, max(len(lines), 1), len(headers) - 1)
        worksheet.set_column(0, 0, 18)
        worksheet.set_column(1, 5, 22)
        worksheet.set_column(6, 6, 12)
        worksheet.set_column(7, 7, 50)
        worksheet.set_column(8, 10, 24)
        worksheet.set_column(11, 11, 16)
        workbook.close()
        output.seek(0)
        filename = "horas_gestion_%s_%s.xlsx" % (
            week_start.isoformat(),
            week_end.isoformat(),
        )
        return filename, base64.b64encode(output.read())

    def _queue_report(self, config, manual=False):
        self.ensure_one()
        if not config.weekly_report_enabled or not config.operations_director_email:
            raise UserError(_(
                "El envío semanal no está activado o no tiene destinatario "
                "configurado para %s."
            ) % config.company_id.display_name)
        report = self.env["timesheet.management.report"].sudo()
        lines = report.search(
            self._report_domain(
                self.company_id,
                self.week_start,
                self.week_end,
            ),
            order="activity_date, employee_id, project_id, id",
        )
        pending_count = report.search_count([
            ("company_id", "=", self.company_id.id),
            "|",
            ("hour_type_id", "=", False),
            ("activity_date", "=", False),
        ])
        filename, file_data = self._render_xlsx(
            lines,
            self.week_start,
            self.week_end,
        )
        total_hours = sum(lines.mapped("unit_amount"))
        attachment = self.env["ir.attachment"].sudo().create({
            "name": filename,
            "type": "binary",
            "datas": file_data,
            "mimetype": (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            "res_model": self._name,
            "res_id": self.id,
        })
        action = self.env.ref(
            "timesheet_activity_management.action_management_hours_report"
        )
        base_url = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url"
        )
        dashboard_url = "%s/web#action=%s" % (base_url, action.id)
        body = _(
            "<p>Detalle semanal de horas de gestión/reuniones internas "
            "del %(start)s al %(end)s.</p>"
            "<p>Total: <strong>%(hours).2f horas</strong> "
            "en %(count)s líneas.</p>"
            "<p>Las cargas pendientes de clasificación o fecha no se "
            "incluyen en el total semanal: %(pending)s.</p>"
            "<p><a href=\"%(url)s\">Consultar dashboard</a></p>"
            "<p><a href=\"%(pending_url)s\">Consultar pendientes</a></p>"
        ) % {
            "start": self.week_start.isoformat(),
            "end": self.week_end.isoformat(),
            "hours": total_hours,
            "count": len(lines),
            "pending": pending_count,
            "url": html.escape(dashboard_url, quote=True),
            "pending_url": html.escape(
                "%s/web#action=%s" % (
                    base_url,
                    self.env.ref(
                        "timesheet_activity_management."
                        "action_management_hours_pending"
                    ).id,
                ),
                quote=True,
            ),
        }
        mail = self.env["mail.mail"].sudo().create({
            "email_to": config.operations_director_email,
            "subject": _(
                "Horas de gestión: %(start)s a %(end)s"
            ) % {
                "start": self.week_start.isoformat(),
                "end": self.week_end.isoformat(),
            },
            "body_html": body,
            "attachment_ids": [(4, attachment.id)],
            "auto_delete": False,
        })
        self.sudo().write({
            "state": "queued",
            "mail_id": mail.id,
            "generated_at": fields.Datetime.now(),
            "manual_resend_count": (
                self.manual_resend_count + 1
                if manual and self.mail_id
                else self.manual_resend_count
            ),
            "error_message": False,
        })
        return mail

    @api.model
    def _get_or_create_run(self, company, week_start, week_end):
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            [
                company.id,
                int(week_start.strftime("%Y%m%d")),
            ],
        )
        run = self.search([
            ("company_id", "=", company.id),
            ("week_start", "=", week_start),
        ], limit=1)
        return run or self.create({
            "company_id": company.id,
            "week_start": week_start,
            "week_end": week_end,
        })

    @api.model
    def _cron_send_weekly_management_reports(self):
        local_now = datetime.now(_ARGENTINA_TZ)
        if local_now.weekday() != 0 or local_now.time() < time(8, 0):
            return
        week_start, week_end = self._previous_week_range(local_now)
        configs = self.env["timesheet.management.report.config"].sudo().search([
            ("weekly_report_enabled", "=", True),
        ])
        for config in configs:
            run = self.sudo()._get_or_create_run(
                config.company_id,
                week_start,
                week_end,
            )
            if run.state == "queued" and run.mail_id:
                continue
            try:
                with self.env.cr.savepoint():
                    run._queue_report(config)
            except Exception as error:
                _logger.exception(
                    "No se pudo generar el reporte semanal de gestión para "
                    "la compañía %s y la semana %s.",
                    config.company_id.display_name,
                    week_start,
                )
                run.sudo().write({
                    "state": "error",
                    "error_message": str(error),
                })

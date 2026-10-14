import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TimesheetManagementReportConfig(models.Model):
    _name = "timesheet.management.report.config"
    _description = "Configuración del reporte semanal de gestión"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    weekly_report_enabled = fields.Boolean(
        string="Enviar reporte semanal",
        default=False,
    )
    operations_director_email = fields.Char(
        string="Correo del Director de Operaciones",
    )

    _sql_constraints = [
        (
            "timesheet_management_config_company_unique",
            "unique(company_id)",
            "Ya existe una configuración para esta compañía.",
        ),
    ]

    @api.constrains("weekly_report_enabled", "operations_director_email")
    def _check_recipient(self):
        for config in self:
            address = (config.operations_director_email or "").strip()
            if config.weekly_report_enabled and not address:
                raise ValidationError(_(
                    "Configure el correo del Director de Operaciones antes "
                    "de activar el envío semanal."
                ))
            if address and not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                address,
            ):
                raise ValidationError(_("Ingrese una dirección de correo válida."))

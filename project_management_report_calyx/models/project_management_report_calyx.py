# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, models

from odoo.addons.project_management_report_pgk.models.project_management_report import (
    BOOL,
    DATE,
    HOURS,
    INTEGER,
    MONEY_PES,
    MONEY_PROJECT,
    PERCENT,
    TEXT,
)

REPORT_TITLE = "Informe Gestión de Proyectos – Tecnología (CALYX)"

# 35 columnas en orden. Las propias de Tecnología salen de la plantilla de
# exportación "Contratos_CALYX" (ver README):
#   Área -> x_area (Studio), PM -> x_PM (Studio),
#   Fecha go live original/real -> expected_go_live_date / real_go_live_date.
COLUMNS = [
    ("company", "Compañía / Nombre mostrado", TEXT),
    ("area", "Área", TEXT),
    ("partner", "Socio", TEXT),
    ("customer", "Cliente", TEXT),
    ("parent_account", "Cuenta analítica / Cuenta analítica madre", TEXT),
    ("name", "Nombre mostrado", TEXT),
    ("pm", "PM", TEXT),
    ("total_project_amount", "Importe total proyecto", MONEY_PROJECT),
    ("project_currency", "Moneda del proyecto", TEXT),
    ("teorical_advance", "Avance teórico", PERCENT),
    ("real_advance", "Avance real", PERCENT),
    ("forward_deviation", "Desvío de avance", PERCENT),
    ("real_billing", "Facturación realizada", MONEY_PES),
    ("billing_deviation", "Desvío de facturación - Calyx", MONEY_PES),
    ("contrated_hours", "Horas contratadas", HOURS),
    ("billing_hours", "Horas facturadas", HOURS),
    ("total_timesheet_time", "Tiempo total del parte de horas", INTEGER),
    ("left_hours", "Horas remanentes", HOURS),
    ("advance_billing", "Horas por avance - PGK", HOURS),
    ("advance_deviation_pgk", "Desvío de horas - PGK", HOURS),
    ("deviation_project_hours", "Desvío de horas - Calyx", HOURS),
    ("cost", "Costos", MONEY_PES),
    ("dist_sector", "Dist. Gtos. Sector", MONEY_PES),
    ("dist_management", "Dist. Gtos. Gcia", MONEY_PES),
    ("dist_indirect", "Dist. Gtos. Indirectos", MONEY_PES),
    ("total_cost", "Costos Totales", MONEY_PES),
    ("overbilling_cost_rate", "% Costos sobre ingresos", PERCENT),
    ("achievement_rate", "Realización", PERCENT),
    ("gross_margin", "Margen Bruto", MONEY_PES),
    ("expected_go_live_date", "Fecha go live original", DATE),
    ("real_go_live_date", "Fecha go live real", DATE),
    ("delivery_time_deviation", "Desviación de fecha de entrega", INTEGER),
    ("stage", "Etapa", TEXT),
    ("is_non_billable", "No Facturable", BOOL),
    ("allow_billable", "Facturable", BOOL),
]

# Campos de Studio usados por la plantilla Contratos_CALYX
AREA_FIELD = "x_area"
PM_FIELD = "x_PM"


class ProjectManagementReportCalyx(models.AbstractModel):
    _name = "project.management.report.calyx"
    _inherit = "project.management.report"
    _description = "Informe Gestión de Proyectos CALYX"

    @api.model
    def _get_columns(self):
        return COLUMNS

    @api.model
    def _get_report_title(self):
        return REPORT_TITLE

    @api.model
    def _get_file_prefix(self):
        return "gestion_proyectos_calyx"

    @api.model
    def _get_rows(self, projects, date_from=None, date_to=None):
        """Agrega a las filas PGK las columnas propias de Tecnología.

        Facturación realizada, Tiempo total del parte de horas y Costos ya
        vienen limitados por fecha desde el informe PGK; con ellos se
        recalculan Avance teórico, Desvío de avance y Desvío de facturación -
        Calyx con las mismas fórmulas de `project_contrated_hours`.
        Desvío de horas - Calyx, Avance real y las fechas de go live son
        siempre el valor del proyecto.
        """
        rows = super()._get_rows(projects, date_from, date_to)
        has_area = AREA_FIELD in projects._fields
        has_pm = PM_FIELD in projects._fields
        for row in rows:
            project = row["_project"]
            currency = project.currency_id
            timesheet_time = float(row["total_timesheet_time"] or 0)
            contrated_hours = float(project.contrated_hours or 0)
            real_advance = project.real_advance or 0.0

            # _compute_teorical_advance / _compute_forward_deviation
            teorical_advance = (
                timesheet_time / contrated_hours if contrated_hours > 0 else 0.0
            )
            forward_deviation = (
                real_advance - teorical_advance if teorical_advance else 0.0
            )
            # _compute_billing_deviation (campo Monetary: redondeo de la moneda)
            billing_deviation = row["real_billing"] - (
                (project.total_project_amount or 0.0) * real_advance
            )
            if currency:
                billing_deviation = currency.round(billing_deviation)

            row.update({
                "area": (project[AREA_FIELD].display_name or "") if has_area else "",
                "pm": (project[PM_FIELD] or "") if has_pm else "",
                "teorical_advance": teorical_advance,
                "real_advance": real_advance,
                "forward_deviation": forward_deviation,
                "billing_deviation": billing_deviation,
                "deviation_project_hours": project.deviation_project_hours or 0.0,
                "expected_go_live_date": project.expected_go_live_date or None,
                "real_go_live_date": project.real_go_live_date or None,
                "delivery_time_deviation": project.delivery_time_deviation or 0,
            })
        return rows

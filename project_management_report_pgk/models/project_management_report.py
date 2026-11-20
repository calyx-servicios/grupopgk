# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import csv
import io
from collections import defaultdict

import xlsxwriter

from odoo import _, api, fields, models

REPORT_TITLE = "Informe Gestión de Proyectos – Servicios Profesionales (PGK)"

# Tipos de columna -> formato de Excel
TEXT = "text"
BOOL = "bool"
DATE = "date"
HOURS = "hours"
INTEGER = "integer"
PERCENT = "percent"
MONEY_PES = "money_pes"          # monto ya expresado en PES
MONEY_PROJECT = "money_project"  # monto en la moneda del proyecto

# 27 columnas en orden: las 25 de la plantilla "Gestión de Proyectos PGK -
# Contratos" más Costos Totales (21) y Margen Bruto (24).
COLUMNS = [
    ("company", "Compañía / Nombre mostrado", TEXT),
    ("partner", "Socio", TEXT),
    ("customer", "Cliente", TEXT),
    ("parent_account", "Cuenta analítica / Cuenta analítica madre", TEXT),
    ("name", "Nombre mostrado", TEXT),
    ("total_project_amount", "Importe total proyecto", MONEY_PROJECT),
    ("project_currency", "Moneda del proyecto", TEXT),
    ("real_billing", "Facturación realizada", MONEY_PES),
    ("billing_multyply_advance", "Facturación por avance - PGK", MONEY_PROJECT),
    ("teorical_billing", "Desvío de facturación - PGK", MONEY_PES),
    ("contrated_hours", "Horas contratadas", HOURS),
    ("billing_hours", "Horas facturadas", HOURS),
    ("total_timesheet_time", "Tiempo total del parte de horas", INTEGER),
    ("left_hours", "Horas remanentes", HOURS),
    ("advance_billing", "Horas por avance - PGK", HOURS),
    ("advance_deviation_pgk", "Desvío de horas - PGK", HOURS),
    ("cost", "Costos", MONEY_PES),
    ("dist_sector", "Dist. Gtos. Sector", MONEY_PES),
    ("dist_management", "Dist. Gtos. Gcia", MONEY_PES),
    ("dist_indirect", "Dist. Gtos. Indirectos", MONEY_PES),
    ("total_cost", "Costos Totales", MONEY_PES),
    ("overbilling_cost_rate", "% Costos sobre ingresos", PERCENT),
    ("achievement_rate", "Realización", PERCENT),
    ("gross_margin", "Margen Bruto", MONEY_PES),
    ("stage", "Etapa", TEXT),
    ("is_non_billable", "No Facturable", BOOL),
    ("allow_billable", "Facturable", BOOL),
]

# Los formatos solo definen cuántos decimales se VEN. En la celda se escribe el
# valor completo de Odoo (sin redondear), visible en la barra de fórmulas.
HOURS_DIGITS = 2
INTEGER_FORMAT = "#,##0"
PERCENT_PRECISION = "Percentage"  # Ajustes > Técnico > Precisión decimal
DATE_FORMAT = "dd/mm/yyyy"

DIST_KEYS = {"gs": "dist_sector", "gg": "dist_management", "gi": "dist_indirect"}


class ProjectManagementReport(models.AbstractModel):
    _name = "project.management.report"
    _description = "Informe Gestión de Proyectos PGK"

    # ------------------------------------------------------------------
    # Definición del informe (se redefine en informes derivados)
    # ------------------------------------------------------------------
    @api.model
    def _get_columns(self):
        """Lista de (clave, título, tipo) en el orden del archivo."""
        return COLUMNS

    @api.model
    def _get_report_title(self):
        return REPORT_TITLE

    @api.model
    def _get_file_prefix(self):
        return "gestion_proyectos_pgk"

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    @api.model
    def _get_cost_and_distributions(self, account_ids, periods=None):
        """Costos y distribuciones de gastos por cuenta analítica, en PES.

        Lee los resultados ya guardados por el informe de consolidación
        (`account.consolidation.data`) para que ambos informes concilien:
        - Costos: filas que no son ingreso ni distribución.
        - Dist. Gtos. Sector / Gcia / Indirectos: según `distribution_type`.
        Los montos de consolidación son negativos para los costos; se
        devuelven con signo invertido (costo positivo).
        Los importes guardados arrastran ruido de punto flotante (p. ej.
        527514.5799999997): se suman como `numeric` (float8 -> numeric conserva
        15 dígitos significativos), así el total es exacto, estable entre
        ejecuciones, y un costo que se compensa da 0 y no 1e-10, que dispararía
        Realización (0,55 / costo).
        `periods` None = todos los períodos consolidados.
        Devuelve {account_id: {'cost': x, 'dist_sector': y, ...}}.
        """
        result = defaultdict(lambda: defaultdict(float))
        if not account_ids or (periods is not None and not periods):
            return result
        self.env["account.consolidation.data"].flush(
            ["analytic_account_id", "distribution_type", "amount",
             "consolidation_period_id", "daughter_account"]
        )
        self.env["account.analytic.line"].flush(["general_account_id"])
        query = """
            SELECT d.analytic_account_id, d.distribution_type,
                   SUM(d.amount::numeric)
              FROM account_consolidation_data d
              LEFT JOIN account_analytic_line l ON l.id = d.daughter_account
              LEFT JOIN account_account ga ON ga.id = l.general_account_id
             WHERE d.analytic_account_id = ANY(%s)
               AND (d.distribution_type IS NOT NULL
                    OR ga.internal_group IS DISTINCT FROM 'income')
        """
        params = [list(account_ids)]
        if periods is not None:
            query += " AND d.consolidation_period_id = ANY(%s)"
            params.append(periods.ids)
        query += " GROUP BY d.analytic_account_id, d.distribution_type"
        self.env.cr.execute(query, params)
        for account_id, dist_type, amount in self.env.cr.fetchall():
            key = DIST_KEYS.get(dist_type, "cost")
            result[account_id][key] -= float(amount or 0)
        return result

    @api.model
    def _get_pes_currency(self):
        return self.env.ref("base.ARS", raise_if_not_found=False) or \
            self.env.company.currency_id

    @api.model
    def _get_rows(self, projects, date_from=None, date_to=None):
        """Arma una fila (dict por clave de COLUMNS) por proyecto."""
        Project = self.env["project.project"]
        billing = projects._get_billing_data(date_from, date_to)
        timesheet = projects._get_timesheet_time(date_from, date_to)
        periods = None
        if date_from or date_to:
            periods = self.env["account.consolidation.period"]._search_in_range(
                date_from, date_to
            )
        costs = self._get_cost_and_distributions(
            projects.analytic_account_id.ids, periods
        )

        rows = []
        for project in projects:
            currency = project.currency_id
            raw_billing, billing_hours = billing[project.id]
            # Mismo valor que el campo Monetary (precisión de la moneda)
            real_billing = currency.round(raw_billing) if currency else raw_billing
            billing_by_advance = project.billing_multyply_advance or 0.0
            teorical_billing = real_billing - billing_by_advance
            if currency:
                teorical_billing = currency.round(teorical_billing)

            amounts = costs.get(project.analytic_account_id.id, {})
            cost = amounts.get("cost", 0.0)
            dist_sector = amounts.get("dist_sector", 0.0)
            dist_management = amounts.get("dist_management", 0.0)
            dist_indirect = amounts.get("dist_indirect", 0.0)
            overbilling_rate, achievement_rate = Project._get_cost_rates(
                real_billing, cost
            )

            rows.append({
                "company": project.company_id.display_name or "",
                "partner": project.partner.display_name or "",
                "customer": project.partner_id.display_name or "",
                "parent_account": project.analytic_account_id.parent_id.display_name or "",
                "name": project.display_name or "",
                "total_project_amount": project.total_project_amount or 0.0,
                "project_currency": project.project_currency_id.name or "",
                "real_billing": real_billing,
                "billing_multyply_advance": billing_by_advance,
                "teorical_billing": teorical_billing,
                "contrated_hours": project.contrated_hours or 0.0,
                "billing_hours": billing_hours or 0.0,
                "total_timesheet_time": timesheet.get(project.id, 0),
                "left_hours": project.left_hours or 0.0,
                "advance_billing": project.advance_billing or 0.0,
                "advance_deviation_pgk": project.advance_deviation_pgk or 0.0,
                "cost": cost,
                "dist_sector": dist_sector,
                "dist_management": dist_management,
                "dist_indirect": dist_indirect,
                "total_cost": cost + dist_sector + dist_management + dist_indirect,
                "overbilling_cost_rate": overbilling_rate,
                "achievement_rate": achievement_rate,
                "gross_margin": real_billing - cost - dist_sector - dist_management,
                "stage": project.stage_id.display_name or "",
                "is_non_billable": bool(project.is_non_billable),
                "allow_billable": bool(project.allow_billable),
                # Para el formato de las columnas en moneda del proyecto
                "_project_currency": project.project_currency_id,
                # Para informes derivados que agregan columnas
                "_project": project,
            })
        return rows

    # ------------------------------------------------------------------
    # Archivos
    # ------------------------------------------------------------------
    @api.model
    def _generate_file(self, wizard):
        """Devuelve (contenido en bytes, nombre de archivo)."""
        projects = wizard._get_projects()
        date_from, date_to = wizard._get_date_range()
        rows = self._get_rows(projects, date_from, date_to)
        header_lines = wizard._get_header_lines()
        stamp = fields.Datetime.context_timestamp(
            wizard, fields.Datetime.now()
        ).strftime("%Y%m%d_%H%M")
        base_name = "%s_%s" % (self._get_file_prefix(), stamp)
        if wizard.file_format == "csv":
            return self._build_csv(rows, header_lines), base_name + ".csv"
        return self._build_xlsx(rows, header_lines), base_name + ".xlsx"

    @api.model
    def _number_format(self, digits):
        return "#,##0" + ("." + "0" * digits if digits > 0 else "")

    @api.model
    def _percent_format(self):
        digits = self.env["decimal.precision"].precision_get(PERCENT_PRECISION)
        return ("0." + "0" * digits if digits > 0 else "0") + "%"

    @api.model
    def _currency_format(self, currency):
        """Formato de moneda con los decimales configurados en la moneda."""
        number_format = self._number_format(currency.decimal_places)
        symbol = (currency.symbol or currency.name or "").replace('"', "")
        if not symbol:
            return number_format
        if currency.position == "after":
            return '%s "%s"' % (number_format, symbol)
        return '"%s" %s' % (symbol, number_format)

    @api.model
    def _build_xlsx(self, rows, header_lines):
        columns = self._get_columns()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Gestión de Proyectos")

        title_fmt = workbook.add_format({"bold": True, "font_size": 14})
        info_fmt = workbook.add_format({"italic": True})
        head_fmt = workbook.add_format({
            "bold": True, "bg_color": "#D9E1F2", "border": 1,
            "text_wrap": True, "valign": "vcenter", "align": "center",
        })
        formats = {
            TEXT: None,
            BOOL: None,
            DATE: workbook.add_format({"num_format": DATE_FORMAT}),
            HOURS: workbook.add_format(
                {"num_format": self._number_format(HOURS_DIGITS)}
            ),
            INTEGER: workbook.add_format({"num_format": INTEGER_FORMAT}),
            PERCENT: workbook.add_format({"num_format": self._percent_format()}),
        }
        pes = self._get_pes_currency()
        formats[MONEY_PES] = workbook.add_format(
            {"num_format": self._currency_format(pes)}
        )
        currency_formats = {}

        def project_money_format(currency):
            if not currency:
                return formats[HOURS]
            if currency.id not in currency_formats:
                currency_formats[currency.id] = workbook.add_format(
                    {"num_format": self._currency_format(currency)}
                )
            return currency_formats[currency.id]

        row_idx = 0
        sheet.write(row_idx, 0, self._get_report_title(), title_fmt)
        row_idx += 1
        for line in header_lines:
            sheet.write(row_idx, 0, line, info_fmt)
            row_idx += 1
        row_idx += 1

        header_row = row_idx
        for col_idx, (_key, label, _kind) in enumerate(columns):
            sheet.write(header_row, col_idx, label, head_fmt)
        sheet.set_row(header_row, 45)

        for row in rows:
            row_idx += 1
            for col_idx, (key, _label, kind) in enumerate(columns):
                value = row[key]
                if kind == TEXT:
                    sheet.write_string(row_idx, col_idx, value)
                elif kind == BOOL:
                    sheet.write_boolean(row_idx, col_idx, value)
                elif kind == DATE:
                    if value:
                        sheet.write_datetime(row_idx, col_idx, value, formats[DATE])
                    else:
                        sheet.write_blank(row_idx, col_idx, None)
                elif kind == MONEY_PROJECT:
                    sheet.write_number(
                        row_idx, col_idx, value,
                        project_money_format(row["_project_currency"]),
                    )
                else:
                    sheet.write_number(row_idx, col_idx, value, formats[kind])

        for col_idx, (_key, _label, kind) in enumerate(columns):
            sheet.set_column(col_idx, col_idx, 32 if kind == TEXT else 20)
        sheet.freeze_panes(header_row + 1, 0)
        sheet.autofilter(header_row, 0, max(row_idx, header_row), len(columns) - 1)
        workbook.close()
        return output.getvalue()

    @api.model
    def _build_csv(self, rows, header_lines):
        columns = self._get_columns()
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow([self._get_report_title()])
        for line in header_lines:
            writer.writerow([line])
        writer.writerow([])
        writer.writerow([label for _key, label, _kind in columns])
        for row in rows:
            values = []
            for key, _label, kind in columns:
                value = row[key]
                if kind == BOOL:
                    value = _("Sí") if value else _("No")
                elif kind == DATE:
                    value = value.strftime("%d/%m/%Y") if value else ""
                elif kind != TEXT:
                    # repr conserva todos los decimales del float
                    value = repr(value)
                values.append(value)
            writer.writerow(values)
        # BOM para que Excel reconozca UTF-8
        return ("﻿" + output.getvalue()).encode("utf-8")

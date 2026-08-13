from odoo import _, models


class SubscriptionTariffControlXlsxReport(models.AbstractModel):
    _name = "report.subscription_massive_update.tariff_ctrl_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Subscription Tariff Control XLSX Report"

    def _write_filters(self, sheet, payload, styles):
        filters = payload.get("filters", {})
        sheet.write("A1", _("Control de Actualizaciones de Tarifa"), styles["title"])
        sheet.write("A3", _("Compañías"), styles["label"])
        sheet.write("B3", filters.get("companies", ""), styles["text"])
        sheet.write("A4", _("Estado"), styles["label"])
        sheet.write("B4", filters.get("state", ""), styles["text"])
        sheet.write("A5", _("Desde"), styles["label"])
        sheet.write("B5", str(filters.get("date_from") or ""), styles["text"])
        sheet.write("A6", _("Hasta"), styles["label"])
        sheet.write("B6", str(filters.get("date_to") or ""), styles["text"])
        sheet.write("A7", _("Tipo actualización"), styles["label"])
        sheet.write("B7", filters.get("update_frequency", ""), styles["text"])
        sheet.write("A8", _("Moneda"), styles["label"])
        sheet.write("B8", filters.get("currency_filter", ""), styles["text"])

    def generate_xlsx_report(self, workbook, data, wizards):
        wizard = wizards[:1]
        payload = (data or {}).get("report_data")
        if not payload and wizard:
            payload = wizard._prepare_report_data()
        payload = payload or {}

        sheet = workbook.add_worksheet(_("Control Tarifas"))
        sheet.set_column("A:A", 16)
        sheet.set_column("B:B", 18)
        sheet.set_column("C:C", 24)
        sheet.set_column("D:D", 16)
        sheet.set_column("E:E", 20)
        sheet.set_column("F:F", 18)
        sheet.set_column("G:G", 28)
        sheet.set_column("H:H", 24)
        sheet.set_column("I:I", 10)
        sheet.set_column("J:L", 14)
        sheet.set_column("M:M", 14)
        sheet.set_column("N:N", 10)
        sheet.set_column("O:O", 16)

        styles = {
            "title": workbook.add_format({"bold": True, "font_size": 14}),
            "section": workbook.add_format({"bold": True, "bg_color": "#D9E1F2"}),
            "header": workbook.add_format({"bold": True, "bg_color": "#BDD7EE", "border": 1}),
            "label": workbook.add_format({"bold": True}),
            "text": workbook.add_format({}),
            "money": workbook.add_format({"num_format": "#,##0.00"}),
            "percent": workbook.add_format({"num_format": "0.00"}),
            "subtotal": workbook.add_format({"bold": True, "bg_color": "#E2F0D9", "border": 1}),
        }

        self._write_filters(sheet, payload, styles)
        row = 10

        sheet.write(row, 0, _("Sección 1 - Suscripciones actualizadas"), styles["section"])
        row += 1
        headers_one = [
            _("Compañía"), _("SO"), _("SUS"), _("Tipo actualización"), _("Fecha cambio"),
            _("Usuario"), _("Producto"), _("Cuenta analítica"), _("Qty"),
            _("P.U. anterior"), _("P.U. nuevo"), _("Subtotal neto"), _("% aplicado"),
            _("Moneda"), _("Comercial"),
        ]
        for col, label in enumerate(headers_one):
            sheet.write(row, col, label, styles["header"])
        row += 1

        for report_row in payload.get("section_one_rows", []):
            sheet.write(row, 0, report_row.get("company", ""))
            sheet.write(row, 1, report_row.get("so", ""))
            sheet.write(row, 2, report_row.get("sus", ""))
            sheet.write(row, 3, report_row.get("update_frequency", ""))
            sheet.write(row, 4, str(report_row.get("change_date") or ""))
            sheet.write(row, 5, report_row.get("user", ""))
            sheet.write(row, 6, report_row.get("product", ""))
            sheet.write(row, 7, report_row.get("analytic_account", ""))
            sheet.write_number(row, 8, report_row.get("qty", 0.0))
            sheet.write_number(row, 9, report_row.get("old_price", 0.0), styles["money"])
            sheet.write_number(row, 10, report_row.get("new_price", 0.0), styles["money"])
            sheet.write_number(row, 11, report_row.get("subtotal_net", 0.0), styles["money"])
            sheet.write_number(row, 12, report_row.get("applied_percentage", 0.0), styles["percent"])
            sheet.write(row, 13, report_row.get("currency", ""))
            sheet.write(row, 14, report_row.get("commercial", ""))
            row += 1

        row += 1
        sheet.write(row, 0, _("Subtotal por cliente"), styles["section"])
        row += 1
        subtotal_headers = [
            _("Cliente"), _("Total original neto"), _("Total actual neto"), _("Variación acumulada %")
        ]
        for col, label in enumerate(subtotal_headers):
            sheet.write(row, col, label, styles["header"])
        row += 1

        for subtotal in payload.get("partner_subtotals", []):
            sheet.write(row, 0, subtotal.get("partner_name", ""), styles["subtotal"])
            sheet.write_number(row, 1, subtotal.get("total_original", 0.0), styles["subtotal"])
            sheet.write_number(row, 2, subtotal.get("total_current", 0.0), styles["subtotal"])
            sheet.write_number(row, 3, subtotal.get("variation", 0.0), styles["subtotal"])
            row += 1

        row += 2
        sheet.write(row, 0, _("Sección 2 - Suscripciones sin actualización"), styles["section"])
        row += 1
        headers_two = [
            _("Compañía"), _("SO"), _("SUS"), _("Tipo actualización"), _("Última actualización"),
            _("Producto"), _("Cuenta analítica"), _("Qty"), _("P.U. actual"),
            _("Subtotal neto"), _("Moneda"), _("Comercial"),
        ]
        for col, label in enumerate(headers_two):
            sheet.write(row, col, label, styles["header"])
        row += 1

        for report_row in payload.get("section_two_rows", []):
            sheet.write(row, 0, report_row.get("company", ""))
            sheet.write(row, 1, report_row.get("so", ""))
            sheet.write(row, 2, report_row.get("sus", ""))
            sheet.write(row, 3, report_row.get("update_frequency", ""))
            sheet.write(row, 4, str(report_row.get("last_update") or ""))
            sheet.write(row, 5, report_row.get("product", ""))
            sheet.write(row, 6, report_row.get("analytic_account", ""))
            sheet.write_number(row, 7, report_row.get("qty", 0.0))
            sheet.write_number(row, 8, report_row.get("current_price", 0.0), styles["money"])
            sheet.write_number(row, 9, report_row.get("subtotal_net", 0.0), styles["money"])
            sheet.write(row, 10, report_row.get("currency", ""))
            sheet.write(row, 11, report_row.get("commercial", ""))
            row += 1
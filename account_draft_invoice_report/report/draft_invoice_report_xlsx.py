from odoo import _, models
from odoo.tools import html2plaintext


class DraftInvoiceReportXlsx(models.AbstractModel):
    _name = "report.account_draft_invoice_report.draft_invoice_report_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Facturación Pendiente (Borradores) XLSX"

    def generate_xlsx_report(self, workbook, data, objects):
        wizard = objects[0]
        report_data = wizard._prepare_report_data()
        sheet = workbook.add_worksheet(_("Borradores")[:31])
        sheet.freeze_panes(4, 0)
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.set_margins(left=0.25, right=0.25, top=0.5, bottom=0.5)

        title_format = workbook.add_format(
            {"bold": True, "font_size": 14, "align": "center", "valign": "vcenter"}
        )
        filter_label_format = workbook.add_format(
            {"bold": True, "bg_color": "#F0F0F0", "border": 1, "align": "center"}
        )
        filter_value_format = workbook.add_format(
            {"border": 1, "align": "center"}
        )
        company_format = workbook.add_format(
            {"bold": True, "font_size": 12, "bg_color": "#D9E1F2", "border": 1}
        )
        client_format = workbook.add_format(
            {"bold": True, "font_size": 11, "bg_color": "#E2F0D9", "border": 1}
        )
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#F0F0F0",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        )
        text_format = workbook.add_format(
            {"border": 1, "valign": "top", "text_wrap": True}
        )
        date_format = workbook.add_format(
            {
                "border": 1,
                "num_format": "dd/mm/yyyy",
                "align": "center",
                "valign": "top",
            }
        )
        amount_format = workbook.add_format(
            {"border": 1, "num_format": "#,##0.00", "align": "right", "valign": "top"}
        )
        total_label_format = workbook.add_format(
            {"bold": True, "bg_color": "#F0F0F0", "border": 1}
        )
        total_amount_format = workbook.add_format(
            {"bold": True, "bg_color": "#F0F0F0", "border": 1, "num_format": "#,##0.00", "align": "right"}
        )
        blank_total_format = workbook.add_format(
            {"bold": True, "bg_color": "#F0F0F0", "border": 1}
        )

        widths = [14, 24, 14, 20, 18, 16, 14, 22, 16, 18, 45]
        for column, width in enumerate(widths):
            sheet.set_column(column, column, width)

        sheet.merge_range(0, 0, 0, 10, _("Facturación Pendiente (Borradores)"), title_format)
        sheet.set_row(0, 24)
        sheet.write(1, 0, _("Fecha Desde"), filter_label_format)
        sheet.write(1, 1, report_data["date_from"], date_format)
        sheet.write(1, 2, _("Fecha Hasta"), filter_label_format)
        sheet.write(1, 3, report_data["date_to"], date_format)
        sheet.write(1, 4, _("Compañías"), filter_label_format)
        sheet.merge_range(1, 5, 1, 10, report_data["companies_label"], filter_value_format)
        sheet.set_row(1, 28)

        headers = [
            _("Número"),
            _("Cliente"),
            _("Fecha factura"),
            _("Empresa"),
            _("Sale Order"),
            _("Suscripción"),
            _("Tipo"),
            _("Impuestos no incluidos"),
            _("Total"),
            _("Total en divisa"),
            _("Observaciones"),
        ]
        row = 3
        for company in report_data["companies"]:
            sheet.merge_range(row, 0, row, 10, _("Compañía: %s") % company["name"], company_format)
            row += 1
            for client in company["clients"]:
                sheet.merge_range(row, 0, row, 10, _("Cliente: %s") % client["name"], client_format)
                row += 1
                for column, header in enumerate(headers):
                    sheet.write(row, column, header, header_format)
                sheet.set_row(row, 34)
                row += 1
                for document in client["documents"]:
                    observations = html2plaintext(document["observations"] or "").strip()
                    values = [
                        document["number"],
                        document["client"],
                        document["invoice_date"],
                        document["company"],
                        document["sale_order"],
                        document["subscription"],
                        document["document_type"],
                        document["amount_untaxed"],
                        document["amount_total"],
                        document["foreign_total"] or "",
                        observations,
                    ]
                    for column, value in enumerate(values):
                        if column == 2 and value:
                            cell_format = date_format
                        elif column in (7, 8) and value != "":
                            cell_format = amount_format
                        else:
                            cell_format = text_format
                        sheet.write(row, column, value, cell_format)
                    sheet.set_row(row, 48)
                    row += 1
                for total in client["totals"].values():
                    sheet.merge_range(row, 0, row, 6, _("Total cliente"), total_label_format)
                    sheet.write(row, 7, total["untaxed"], total_amount_format)
                    sheet.write(row, 8, total["total"], total_amount_format)
                    sheet.write_blank(row, 9, None, blank_total_format)
                    sheet.write_blank(row, 10, None, blank_total_format)
                    row += 1
            for total in company["totals"].values():
                company_total_label = _("Total compañía %s") % total["currency"].name
                sheet.merge_range(row, 0, row, 6, company_total_label, total_label_format)
                sheet.write(row, 7, total["untaxed"], total_amount_format)
                sheet.write(row, 8, total["total"], total_amount_format)
                sheet.write_blank(row, 9, None, blank_total_format)
                sheet.write_blank(row, 10, None, blank_total_format)
                row += 1
            sheet.set_row(row, 10)
            row += 1

        for total in report_data["totals"]:
            sheet.merge_range(row, 0, row, 6, _("TOTAL GENERAL %s") % total["currency"].name, total_label_format)
            sheet.write(row, 7, total["untaxed"], total_amount_format)
            sheet.write(row, 8, total["total"], total_amount_format)
            sheet.write_blank(row, 9, None, blank_total_format)
            sheet.write_blank(row, 10, None, blank_total_format)
            row += 1

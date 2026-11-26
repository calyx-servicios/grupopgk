from odoo import models


class AccountVatLedgerXlsx(models.AbstractModel):
    _inherit = "report.account_vat_ledger_xlsx"

    def _get_vat_ledger_text_columns(self):
        """Columnas descriptivas: (título, función que recibe la línea).

        Los Char vacíos llegan como False: se escriben como "" para que el
        XLSX no muestre FALSE (p. ej. CUIT de proveedores del exterior).
        """
        return [
            ("Fecha", lambda line: line.invoice_date and line.invoice_date.strftime("%Y-%m-%d") or ""),
            ("Cliente/Proveedor", lambda line: line.partner_name or ""),
            ("CUIT", lambda line: line.cuit or ""),
            ("Tipo Comprobante", lambda line: line.document_type_id.display_name or ""),
            ("Responsabilidad AFIP", lambda line: line.afip_responsibility_type_name or ""),
            ("N° Comprobante", lambda line: line.move_name or ""),
        ]

    def _get_vat_ledger_amount_columns(self):
        """Columnas de importe: (título, campo de account.ar.vat.line).

        Mismo orden que la pestaña Invoices del Ledger. La suma de todas las
        columnas anteriores a "Total" tiene que dar el Total del comprobante.
        """
        return [
            ("NO gravado/Excento", "not_taxed"),
            ("Monto gravado 2,5%", "base_25"),
            ("IVA 2,5%", "vat_25"),
            ("Monto gravado 5%", "base_5"),
            ("IVA 5%", "vat_5"),
            ("Monto gravado 10,5%", "base_10"),
            ("IVA 10.5%", "vat_10"),
            ("Monto gravado 21%", "base_21"),
            ("IVA 21%", "vat_21"),
            ("Monto gravado 27%", "base_27"),
            ("IVA 27%", "vat_27"),
            ("Perc. IVA", "vat_per"),
            ("Perc. IIBB", "iibb_per"),
            ("Perc. Ganancias", "profit_per"),
            ("Otros", "other_taxes"),
            ("Total", "total"),
        ]

    def generate_xlsx_report(self, workbook, data, vat_ledgers):
        # Reemplaza por completo el método de l10n_ar_reports: el original arma
        # las columnas a mano y no tiene un punto de extensión.
        bold = workbook.add_format({"bold": True})
        money_format = workbook.add_format({"num_format": "$#,##0.00"})
        text_columns = self._get_vat_ledger_text_columns()
        amount_columns = self._get_vat_ledger_amount_columns()

        for vat_ledger in vat_ledgers:
            if not vat_ledger.invoice_ids:
                continue
            sheet = workbook.add_worksheet("IVA Ventas/Compras"[:31])
            sheet.write(1, 0, vat_ledger.display_name, bold)
            titles = [title for title, _getter in text_columns] + [
                title for title, _field in amount_columns
            ]
            for col, title in enumerate(titles):
                sheet.write(3, col, title, bold)
            sheet.set_column(0, len(text_columns) - 1, 30)
            sheet.set_column(len(text_columns), len(titles) - 1, 16)

            for row, line in enumerate(vat_ledger.invoice_ids, start=4):
                for col, (_title, getter) in enumerate(text_columns):
                    sheet.write(row, col, getter(line))
                for col, (_title, field_name) in enumerate(
                    amount_columns, start=len(text_columns)
                ):
                    sheet.write(row, col, line[field_name], money_format)

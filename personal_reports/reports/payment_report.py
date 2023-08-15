from odoo import api, models

from .utils.aux_report_data_retrieve import format_date, get_payment_report_lines


class PersonalPaymentReport(models.AbstractModel):
    _name = "report.personal_reports.payment_subledger_report"
    _description = "Payment Subledger Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        """default method that returns docs to reports, can add methods as key-value pairs

        Args:
            docids (list): list of active_ids in action report
            data (dict, optional): Other data send. Defaults to None.

        Returns:
            dict: {'docs':docs, kwargs}
        """
        invoices = self.env["account.move"].browse(data["docs"])
        invoices = invoices.filtered(lambda doc: doc.invoice_payment_state == "paid")
        docs = self.env["personal.subledger.report.wizard"].browse(docids)
        date_start = format_date(data["date_start"])
        date_end = format_date(data["date_end"])
        report_lines = get_payment_report_lines(invoices)
        return {
            "docs": docs,
            "report_lines": report_lines,
            "company_id": self.env.company,
            "date_start": date_start,
            "date_end": date_end,
        }


class PersonalPaymentReportTxt(PersonalPaymentReport):
    _name = "report.personal_reports.payment_subledger_report_txt"
    _description = "Payment Subledger Report Txt"

    @api.model
    def _get_report_values(self, docids, data=None):
        res = super(PersonalPaymentReportTxt, self)._get_report_values(docids, data)
        if res:
            data = res["report_lines"]
            for line in data:
                line["razon_social"] = line["razon_social"].replace(",", "")
        return res

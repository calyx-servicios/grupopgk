import logging

from odoo import api, models

from .utils.aux_report_data_retrieve import format_date, get_invoicing_report_lines


class PersonalInvoicingReport(models.AbstractModel):
    _name = "report.personal_reports.invoicing_subledger_report"
    _description = "Invoicing Subledger Report"

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
        docs = self.env["personal.subledger.report.wizard"].browse(docids)
        date_start = format_date(data["date_start"])
        date_end = format_date(data["date_end"])
        report_lines = get_invoicing_report_lines(invoices)
        return {
            "docs": docs,
            "docids": docids,
            "report_lines": report_lines,
            "company_id": self.env.company,
            "date_start": date_start,
            "date_end": date_end,
        }


class PersonalInvoicingReportTxt(PersonalInvoicingReport):
    _name = "report.personal_reports.invoicing_subledger_report_txt"
    _description = "Invoicing Subledger Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        res = super(PersonalInvoicingReportTxt, self)._get_report_values(docids, data)
        if res:
            data = res["report_lines"]
            for line in data:
                line["razon_social"] = line["razon_social"].replace(",", "")
        return res

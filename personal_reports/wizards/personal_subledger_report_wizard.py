import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PersonalSubLedgerReportWizard(models.TransientModel):
    _name = "personal.subledger.report.wizard"
    _description = "Personal Subledger Report Wizard"

    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    report_type = fields.Selection([("txt", "txt"), ("pdf", "pdf")], default="pdf", required=True)

    raw_report = fields.Boolean()

    def get_report_date(self):
        return fields.Datetime.today("GMT-3").strftime("%d%m%Y")

    def get_report_data(self, report):
        docs = self.env["account.move"].search(
            [
                ("invoice_date", ">=", self.date_start),
                ("invoice_date", "<=", self.date_end),
                ("state", "=", "posted"),
                ("type", "in", ["out_invoice", "out_refund"]),
            ]
        )
        report_name = f"personal_reports.{report}_subledger_report"
        if self.report_type == "txt":
            report_name += "_txt"
        report = self.env["ir.actions.report"]._get_report_from_name(report_name)
        return docs, report

    def action_create_invoicing_report(self):
        docs, report = self.get_report_data("invoicing")
        return report.report_action(
            self.ids, {"docs": docs.ids, "date_start": self.date_start, "date_end": self.date_end}
        )

    def action_create_payments_report(self):
        docs, report = self.get_report_data("payment")
        return report.report_action(
            self.ids, {"docs": docs.ids, "date_start": self.date_start, "date_end": self.date_end}
        )

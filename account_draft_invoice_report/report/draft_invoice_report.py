from odoo import api, models


class DraftInvoiceReport(models.AbstractModel):
    _name = "report.account_draft_invoice_report.draft_invoice_report"
    _description = "Facturación Pendiente (Borradores)"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["account.draft.invoice.report.wizard"].browse(docids).ensure_one()
        company = wizard._get_company_ids()[:1] or self.env.company
        return {
            "doc_ids": docids,
            "doc_model": "account.draft.invoice.report.wizard",
            "docs": wizard,
            "company": company,
            "res_company": company,
            "report_data": wizard._prepare_report_data(),
        }

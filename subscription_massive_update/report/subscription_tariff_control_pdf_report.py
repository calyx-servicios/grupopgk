from odoo import models


class SubscriptionTariffControlPdfReport(models.AbstractModel):
    _name = "report.subscription_massive_update.tariff_ctrl_pdf"
    _description = "Subscription Tariff Control PDF Report"

    def _get_report_values(self, docids, data=None):
        wizards = self.env["subscription.tariff.update.control.wizard"].browse(docids)
        wizard = wizards[:1]
        report_data = (data or {}).get("report_data")
        if not report_data and wizard:
            report_data = wizard._prepare_report_data()
        return {
            "doc_ids": docids,
            "doc_model": "subscription.tariff.update.control.wizard",
            "docs": wizards,
            "report_data": report_data or {},
        }
from odoo import _, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _get_sheet_domain(self):
        """Hook for extensions"""
        self.ensure_one()
        return [
            ("date_end", ">=", self.date),
            ("date_start", "<=", self.date),
            ("employee_id", "=", self.employee_id.id),
            ("company_id", "in", self.company_id.ids + [False]),
            ("state", "in", ["new", "draft"]),
        ]

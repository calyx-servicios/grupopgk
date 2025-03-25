from odoo import fields, models, api, _
from odoo.tools.safe_eval import safe_eval

def _get_timesheet_args(TS, context):
    timesheet_id = context.get("timesheet_sige")
    timesheet_id = TS.browse(timesheet_id)
    sheet_ids = timesheet_id.timesheet_ids.ids
    analytic_lines = context.get("analytic_lines")
    domain = [("id", "in", sheet_ids)]
    if analytic_lines and safe_eval(analytic_lines):
        domain.append(
            ("id", "not in", safe_eval(analytic_lines) )
        )
    return domain

class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        context = self.env.context
        if context.get("reclassify_hours") and context.get("timesheet_sige"):
            TS = self.env["timesheet.sige"]
            args = _get_timesheet_args(TS, context)
        return super().name_search(
            name, args=args, operator=operator, limit=limit
        )

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        context = self.env.context
        if context.get("reclassify_hours") and context.get("timesheet_sige"):
            TS = self.env["timesheet.sige"]
            domain = _get_timesheet_args(TS, context)
        return super().search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order
        )

    def name_get(self):
        context = self.env.context
        res = super().name_get()
        if context.get("reclassify_hours"):
            new_res = []
            for r in res:
                rec = self.browse(r[0])
                new_res.append((r[0], f"{r[1]} | {str(rec.unit_amount)} hs"))
            res = new_res
        return res

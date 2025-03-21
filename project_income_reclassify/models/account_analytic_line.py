from odoo import fields, models, api, _


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    project_income_reclassify_id = fields.Many2one(
        comodel_name="project.income.reclassify",
    )
    already_reclassified = fields.Boolean(
        string="Reclasificado"
    )

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        context = self.env.context
        res = super().name_search(
            name, args=args, operator=operator, limit=limit
        )
        if context.get("reclassify_incomes_action"):
            self = self.sudo()
            new_res = []
            for r in res:
                rec = self.browse(r[0])
                display_name = rec.move_id.display_name if rec.move_id else rec.display_name
                new_res.append((r[0], f'{display_name} - ${rec.amount}'))
            return new_res
        return res

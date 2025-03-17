from odoo import fields, models, api, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.constrains("user_id")
    def _onchange_user_id_set_pir(self):
        PIR = self.env["project.income.reclassify.line"]
        for rec in self:
            lines = PIR.search([("project_id", "=", rec.id)])
            lines.mapped("reclassify_id").write({
                "approver_id": rec.user_id if rec.user_id else False
            })

from odoo import fields, models, api, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.constrains("user_id")
    def _onchange_user_id(self):
        TRL = self.env["timesheet.reclassify.line"]
        for rec in self:
            lines = TRL.search([("project_id", "=", rec.id)])
            lines._compute_approver_id()

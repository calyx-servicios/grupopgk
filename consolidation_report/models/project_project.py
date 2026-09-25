from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_non_billable = fields.Boolean(
        string='Non-Billable',
        help='Marks the project as non-billable for the consolidation report.'
    )

    def write(self, vals):
        if 'analytic_account_id' not in vals:
            return super().write(vals)
        old_accounts = {project: project.analytic_account_id for project in self}
        res = super().write(vals)
        # las horas de la cuenta anterior pasan a la nueva para no quedar huerfanas
        line_obj = self.env['account.analytic.line'].sudo()
        for project, old_account in old_accounts.items():
            new_account = project.analytic_account_id
            if not old_account or not new_account or old_account == new_account:
                continue
            lines = line_obj.search([
                ('project_id', '=', project.id),
                ('account_id', '=', old_account.id),
                ('move_id', '=', False),
            ])
            lines._update_analytic_account(new_account)
            project.message_post(body="<br/>".join([
                _("Analytic account changed: %s analytic lines updated.") % len(lines),
                _("Previous account: %s (ID: %s)") % (old_account.display_name, old_account.id),
                _("New account: %s (ID: %s)") % (new_account.display_name, new_account.id),
            ]))
        return res

    @api.constrains('is_non_billable', 'allow_billable')
    def _check_non_billable(self):
        for project in self:
            if project.is_non_billable and project.allow_billable:
                raise ValidationError(
                    _("A project cannot be Billable and Non-Billable at the same time.")
                )

from odoo import models, fields, api,_
from odoo.exceptions import AccessError

class ProjectProject(models.Model):
    _inherit = 'project.project'


    has_profile_admin = fields.Boolean(string="Has administrator profile?", compute="_compute_has_profile_access", store=False, default=False)
    has_profile_manager = fields.Boolean(string="Has manager profile?", compute="_compute_has_profile_access", store=False, default=False)

    @api.depends('user_id')
    def _compute_has_profile_access(self):
        group_names = {
            'custom_access_permissions.group_profile_administrator': 'has_profile_admin',
            'custom_access_permissions.group_profile_manager': 'has_profile_manager'
        }
        for project in self:
            user = self.env.user
            for group_name, field_name in group_names.items():
                has_group = user.has_group(group_name)
                setattr(project, field_name, has_group)

    def _sync_analytic_accounts_active(self, active_value):
        """Keep analytic accounts aligned with the active projects using them."""
        analytic_accounts = self.with_context(active_test=False).mapped(
            'analytic_account_id'
        )
        if not analytic_accounts:
            return

        accounts_to_update = self.env['account.analytic.account']
        project_model = self.with_context(active_test=False)
        for analytic_account in analytic_accounts:
            has_active_projects = bool(project_model.search_count([
                ('analytic_account_id', '=', analytic_account.id),
                ('active', '=', True),
            ]))
            if active_value and has_active_projects:
                accounts_to_update |= analytic_account
            elif not active_value and not has_active_projects:
                accounts_to_update |= analytic_account

        if accounts_to_update:
            accounts_to_update.sudo().write({'active': active_value})
    
    def write(self, vals):
        profile_admin = self.env.user.has_group('custom_access_permissions.group_profile_administrator')
        if vals.get('active') == False and not profile_admin:
            raise AccessError(_('You do not have the necessary permissions, please contact the administrator'))

        sync_active = 'active' in vals
        res = super().write(vals)

        if sync_active:
            self._sync_analytic_accounts_active(vals['active'])

        return res
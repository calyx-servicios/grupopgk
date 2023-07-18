from odoo import models, api, fields, _
from odoo.exceptions import AccessError

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def create(self, vals):
        if not self.env.user.has_group('custom_access_permissions.group_profile_manager') and vals.get('move_type') not in ('out_refund', 'in_refund', 'in_invoice'):
            raise AccessError(_('You do not have access to create this type of move.'))
        return super().create(vals)

    def action_post(self):
        for rec in self:
            if not self.env.user.has_group('custom_access_permissions.group_profile_administrator'):
                raise AccessError(_('You do not have access to create this type of move.'))
        return super(AccountMove, self).action_post()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    move_type = fields.Selection(related='move_id.move_type', string='Move Type', readonly=True, store=True)
    source_origin = fields.Char(related='move_id.invoice_origin', string='Source Origin', readonly=True)

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

from odoo import models, api, fields, _
from odoo.exceptions import AccessError

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def create(self, vals):
        if not self.env.user.has_group('custom_access_permissions.group_profile_manager') and vals.get('move_type') not in ('out_refund', 'in_refund'):
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

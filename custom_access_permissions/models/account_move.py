from odoo import models, api,_
from odoo.exceptions import AccessError

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def create(self, vals):
        if self.env.user.has_group('custom_access_permissions.group_profile_manager') and vals.get('move_type') not in ('out_refund', 'in_refund'):
            raise AccessError(_('You do not have access to create this type of move.'))
        return super().create(vals)
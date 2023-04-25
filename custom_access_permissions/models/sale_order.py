from odoo import models, fields, api,_

class SaleOrder(models.Model):
    _inherit = 'sale.order'


    has_profile_admin = fields.Boolean(string="Has administrator profile?", compute="_compute_has_profile_access", store=False, default=False)
    has_profile_manager = fields.Boolean(string="Has manager profile?", compute="_compute_has_profile_access", store=False, default=False)

    @api.depends('user_id')
    def _compute_has_profile_access(self):
        group_names = {
            'custom_access_permissions.group_profile_administrator': 'has_profile_admin',
            'custom_access_permissions.group_profile_manager': 'has_profile_manager'
        }
        for order in self:
            user = self.env.user
            for group_name, field_name in group_names.items():
                has_group = user.has_group(group_name)
                setattr(order, field_name, has_group)
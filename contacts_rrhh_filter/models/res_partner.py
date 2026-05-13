from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        user = self.env.user

        if not user.has_group('hr.group_hr_manager'):
            args = args + [('id', '=', user.partner_id.id)]

        return super().search(args, offset=offset, limit=limit, order=order, count=count)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        user = self.env.user

        if not user.has_group('hr.group_hr_manager'):
            domain = domain + [('id', '=', user.partner_id.id)]

        return super().read_group(
            domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy,
        )

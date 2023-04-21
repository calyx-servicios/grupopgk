from odoo import models, _


class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'

    def update_massive(self):
        massive_update_obj = self.env['subscription.massive_update']
        subs_ids = None
        for sub in self:
            if sub.stage_id.category != 'closed':
                if not subs_ids:
                    subs_ids = sub
                else:
                    subs_ids += sub
        return massive_update_obj.massive_update(_('Massive Update'), subs_ids)
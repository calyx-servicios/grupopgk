from odoo import models, fields

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    refactoring_indicator = fields.Boolean(string='Refactoring Indicator', default=False)

    def _approval_allowed(self):
        """Returns whether the order qualifies to be approved by the current user"""
        self.ensure_one()
        if self.refactoring_indicator:
            return True
        else:
            return super(PurchaseOrder, self)._approval_allowed()

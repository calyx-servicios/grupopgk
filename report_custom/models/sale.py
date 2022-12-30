from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sales_order_with_detail = fields.Selection([
        ('with_detail', 'With Detail'),
        ('no_detail', 'No Detail'),
        ],'Quotation / Order', index=True, default='no_detail')

    def print_quotation(self):
        self.filtered(lambda s: s.state == 'draft').write({'state': 'sent'})

        return self.env.ref('report_custom.action_report_saleorder_custom')\
            .with_context(discard_logo_check=True).report_action(self)

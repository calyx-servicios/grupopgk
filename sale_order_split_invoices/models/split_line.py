from odoo import models, api, fields, _


class SplitLine(models.Model):
    _name = 'split.line'
    _description = 'Split Line'

    quantity = fields.Float(string="Quantity")
    product_id = fields.Many2one('product.product')
    name = fields.Text(string='Description')
    partner_id = fields.Many2one('res.partner', string='Child Company')
    unit_price = fields.Float(string='Unit Price')
    price_subtotal = fields.Float(string='Current Subtotal', compute='_compute_price_subtotal')
    amount = fields.Float('New subtotal', default=0)
    order_id = fields.Many2one('sale.order')
    order_line_id = fields.Many2one('sale.order.line')
    uom_id = fields.Many2one('uom.uom')
    tax_id = fields.Many2many('account.tax', string='Taxes')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', check_company=False, related='order_line_id.analytic_account_id')
    type_id = fields.Many2one('sale.order.type')

    
    @api.depends('unit_price', 'quantity')
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = rec.quantity * rec.unit_price

    @api.onchange('type_id')
    def _onchange_type_id(self):
        lines = self.search([('partner_id', '=', self._origin.partner_id.id), ('id', '!=', self._origin.id)])
        for line in lines:
            line.sudo().type_id = self.type_id.id
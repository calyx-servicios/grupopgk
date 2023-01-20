from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    split_invoice = fields.Boolean('Split Invoice?', default=False)
    split_type = fields.Selection([('quantity_per', 'Quantity on Percentage'), ('manual', 'Quantity manual')], default='quantity_per')
    total_required = fields.Float(compute='_compute_total_required', string='Total Required')
    total_split = fields.Float(string='Total', compute='_compute_total_split')
    res_partner_ids = fields.Many2many('res.partner')
    split_line_ids = fields.One2many('split.line', 'order_id')


    def _prepare_subscription(self, plan, split_line):
        self.ensure_one()
        values = {
            'name': plan.name,
            'plan_id': plan.id,
            'partner_id': split_line.partner_id.id,
            'user_id': self.user_id.id,
            'company_id': self.company_id.id,
            'sale_order': self.id,
            }

        default_stage = self.env['subscription.package.stage'].search([('category', '=', 'progress')], limit=1)
        if default_stage:
            values['stage_id'] = default_stage.id
        values['reference_code'] = self.env['ir.sequence'].next_by_code('sequence.reference.code') or 'New'
        return values

    def _prepare_subscription_lines(self, split_lines):
        values = []
        plans = []
        for line in split_lines:
            if line.product_id.is_subscription and line.product_id.subscription_plan_id:
                if line.product_id.subscription_plan_id not in plans:
                    plans.append(line.product_id.subscription_plan_id)
            values.append((0, False, {
                'product_id': line.product_id.id,
                'analytic_account_id': line.analytic_account_id.id,
                'product_qty': line.quantity,
                'product_uom_id': line.uom_id.id,
                'unit_price': line.order_id.set_amount(line.amount),
            }))

        return plans, values

    def _create_subscription(self, split_line):
        res = []
        plans, lines = self._prepare_subscription_lines(split_line)
        for index in range(0, len(plans)):
            values = self._prepare_subscription(plans[index], split_line)
            values['product_line_ids'] = lines
            subscription = self.env['subscription.package'].sudo().create(values)
            if plans[index].short_code and subscription.reference_code:
                subscription.write({
                    'name': plans[index].short_code + '/' + subscription.reference_code + '-' + self.partner_id.name,
                })
            subscription.button_start_date()
            res.append(subscription)
            self.write({'subscription_id': subscription.id})
            msg_body = _("Created with the product: (%s) a new subscription <a href=# data-oe-model=subscription.package data-oe-id=%d>%s</a>") % (', '.join([product.product_id.name for product in subscription.product_line_ids]) , self.subscription_id.id, self.subscription_id.name)
            self.message_post(body=msg_body)
        return res


    def action_confirm(self):
        for rec in self:
            if rec.split_invoice:
                self._check_amount_required(rec.total_required, rec.total_split)
                subscription = []
                for partner in rec.res_partner_ids:
                    split_line = rec.split_line_ids.filtered(lambda l: l.partner_id == partner)
                    sub = rec._create_subscription(split_line)
                    subscription.append(sub)
                len(subscription)
        return super(SaleOrder, self).action_confirm()

    def set_amount(self, split_amount):
        if self.split_type == 'quantity_per':
            amount = (self.amount_untaxed * split_amount) / 100
        else:
            amount = split_amount
        return amount

    def _check_amount_required(self, total_required, total_split):
        if total_required != total_split:
            raise UserError(_('The total amount must be equal to the required amount on Split lines'))

    @api.onchange('res_partner_ids')
    def _onchange_split_line_ids(self):
        if self.split_line_ids:
            self.split_line_ids = [(5,0,0)]
        for partner in self.res_partner_ids.ids:
            for line in self.order_line:
                if self.split_type in ['quantity_per', 'manual']:
                    vals = {
                        'order_id': self.id,
                        'partner_id': partner,
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'order_line_id': line.id,
                        'quantity': line.product_uom_qty,
                        'uom_id': line.product_uom.id,
                        'price_subtotal': line.price_subtotal,
                        'amount': 0.0,
                    }
                    self.split_line_ids.create(vals)

    @api.depends('split_line_ids.amount')
    def _compute_total_split(self):
        total = 0
        for line in self.split_line_ids:
            total += line.amount
            if total > self.total_required:
                raise UserError(_('Cannot exceed Total Required'))

        self.total_split = total

    @api.depends('split_type')
    def _compute_total_required(self):
        if self.split_type == 'quantity_per':
            self.total_required = 100
        else:
           self.total_required = self.amount_untaxed

    def _create_invoices(self, grouped=False, final=False, date=None):
        res = super(SaleOrder, self)._create_invoices(grouped, final, date)
        for rec in self:
            if rec.split_invoice:
                for partner in rec.res_partner_ids:
                    split_line = rec.split_line_ids.filtered(lambda l: l.partner_id == partner)
                    values = rec._prepare_invoice()
                    values['partner_id'] = partner
                    values['invoice_line_ids'] = rec._invoice_values_line(split_line)
                    move = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(values)
                    rec.invoice_ids = (4, move.id)
        return res
    
    def _invoice_values_line(self, split_line):
        lines = []
        for line in split_line:
            vals = {
                'display_type': line.order_line_id.display_type,
                'sequence': line.order_line_id.sequence,
                'name': line.name,
                'product_id': line.product_id.id,
                'product_uom_id': line.uom_id.id,
                'quantity': line.quantity,
                'discount': line.order_line_id.discount,
                'analytic_account_id': line.analytic_account_id.id,
                'price_unit': line.order_id.set_amount(line.amount),
                'tax_ids': [(6,0,line.order_line_id.tax_id.ids)],
                'sale_line_ids': line.order_line_id.id,
            }
            lines.append((0,0, vals))
        return lines


from odoo import api, models, fields, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'


    def _subscription_plans(self):
        self.ensure_one()
        res = {}
        new_sub_lines = self.order_line.filtered(lambda l: not l.order_id.subscription_id and l.subscription_plan_id)
        plans = new_sub_lines.mapped('subscription_plan_id')
        for plan in plans:
            lines = self.order_line.filtered(lambda l: l.subscription_plan_id == plan)
            res[plan] = lines
        return res


    def _prepare_subscription_lines(self, split_line):
        values = []
        for lines in split_line:
            price = lines.order_id.set_amount(lines.amount)
            if lines.order_line_id.subscription_plan_id.limit_choice == 'custom':
                    price = price / lines.order_line_id.subscription_plan_id.limit_count
            values.append(((0, False, {
                'product_id': lines.product_id.id,
                'analytic_account_id': lines.analytic_account_id.id,
                'product_qty': lines.quantity,
                'product_uom_id': lines.uom_id.id,
                'unit_price': price,
            })))
        return values


    def _prepare_plans_split(self, split_lines):
        res = {}
        plans = split_lines.mapped('order_line_id').mapped('subscription_plan_id')
        for plan in plans:
            lines = split_lines.filtered(lambda l: l.order_line_id.subscription_plan_id == plan)
            res[plan] = lines
        return res

    def _create_subscription(self, split_line):
        res = []
        plans = self._prepare_plans_split(split_line)
        for plan in plans:
            key = list(filter(lambda k: plans[k] == plans[plan], plans))[0]
            values = self._prepare_subscription(key, plans[plan])
            values['product_line_ids'] = self._prepare_subscription_lines(plans[plan])
            subscription = self.env['subscription.package'].sudo().create(values)
            if key.short_code and subscription.reference_code:
                subscription.write({
                    'name': key.short_code + '/' + subscription.reference_code + '-' + plans[plan].partner_id.name,
                })
            subscription.button_start_date()
            res.append(subscription)
            self.write({'subscription_id': subscription.id})
            msg_body = _("Created with the product: (%s) a new subscription <a href=# data-oe-model=subscription.package data-oe-id=%d>%s</a>") % (', '.join([product.product_id.name for product in subscription.product_line_ids]) , self.subscription_id.id, self.subscription_id.name)
            self.message_post(body=msg_body)
        return res

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"


    @api.onchange('product_id')
    def _onchange_product_id_domain(self):
        for rec in self:
            if len(rec.product_id.subscription_plan_id.ids) == 1:
                rec.subscription_plan_id = rec.product_id.subscription_plan_id.id
            return {'domain': {'subscription_plan_id': [('id', 'in', rec.product_id.subscription_plan_id.ids)]}}

    subscription_plan_id = fields.Many2one('subscription.package.plan', string='Subscription Plan')
    is_subscription = fields.Boolean(compute='_compute_total_plans', string='Is subscription?')

    @api.depends('product_id')
    def _compute_total_plans(self):
        for rec in self:
            rec.is_subscription = rec.product_id.is_subscription

    def _prepare_values_product(self):
        values = []
        for line in self:
            price = line.price_unit
            if line.subscription_plan_id.limit_choice == 'custom':
                price = price / line.subscription_plan_id.limit_count 
            values.append((0, False, {
                'product_id': line.product_id.id,
                'analytic_account_id': line.analytic_account_id.id,
                'product_qty': line.product_uom_qty,
                'product_uom_id': line.product_uom.id,
                'unit_price': price,
            }))
        return values
from odoo import api, models, fields, _

class SaleOrder(models.Model):
    _inherit = "sale.order"

    subscription_count = fields.Integer(string='Subscriptions', compute='_compute_subscription_count')

    @api.depends('subscription_count', 'order_line')
    def _compute_subscription_count(self):
        self.subscription_count = self.env['subscription.package'].search_count([('sale_order', '=', self.id)])

    def button_sub_count(self):
        return {
            'name': 'Subscriptions',
            'domain': [('sale_order', '=', self.id)],
            'view_type': 'form',
            'res_model': 'subscription.package',
            'view_mode': 'tree,form',
            'type': 'ir.actions.act_window',
        }

    def _prepare_subscription_data(self, plan):
        self.ensure_one()
        values = {
            'name': plan.name,
            'plan_id': plan.id,
            'partner_id': self.partner_invoice_id.id,
            'user_id': self.user_id.id,
            'company_id': self.company_id.id,
            'sale_order': self.id,
            }
        default_stage = self.env['subscription.package.stage'].search([('category', '=', 'progress')], limit=1)
        if default_stage:
            values['stage_id'] = default_stage.id
        values['reference_code'] = self.env['ir.sequence'].next_by_code('sequence.reference.code') or 'New'
        return values
    
    def create_service_subscription(self):
            res = []
            for order in self:  
                plans = self._subscription_plans()
                for plan in plans:
                    values = order._prepare_subscription_data(plan)
                    values['product_line_ids'] = plans[plan]._prepare_values_product()
                    subscription = self.env['subscription.package'].sudo().create(values)
                    if plan.short_code and subscription.reference_code:
                        subscription.write({
                            'name': plan.short_code + '/' + subscription.reference_code + '-' + self.partner_id.name,
                        })
                    subscription.button_start_date()
                    res.append(subscription)
                    plans[plan].order_id.write({'subscription_id': subscription.id})
                    product_names = []
                    for product in subscription.product_line_ids:
                        if product.display_type in ['line_section', 'line_note']:
                            continue
                        else:
                            product_names.append(product.product_id.name)

                    msg_body = _("Created with the product: (%s) a new subscription <a href=# data-oe-model=subscription.package data-oe-id=%d>%s</a>") % (
                        ', '.join(product_names),
                        self.subscription_id.id,
                        self.subscription_id.name
                    )
                    self.message_post(body=msg_body)
            return res

    def _subscription_plans(self):
        self.ensure_one()
        res = {}
        new_sub_lines = self.order_line.filtered(lambda l: not l.order_id.subscription_id and l.product_id.subscription_plan_id)
        plans = new_sub_lines.mapped('product_id').mapped('subscription_plan_id')
        for plan in plans:
            lines = self.order_line.filtered(lambda l: l.product_id.subscription_plan_id == plan)
            res[plan] = lines
        return res

    def action_confirm(self):
        res =  super(SaleOrder, self).action_confirm()
        subscription = None
        if len(self.company_id) == 1:
            subscription = self.sudo().with_company(self.company_id).create_service_subscription()
        else: # No deberia entrar ya que en la sale.order viene siempre una sola compañia
            for order in self:
                subscription = order.order_line.sudo().with_company(order.company_id).create_service_subscription()
        if subscription:
            self.is_subscription = True
            self.subscription_id = subscription[0].id
        return res

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.state == 'sale' and not line.is_expense:
                subscriptions = self.env['subscription.package'].search([('sale_order', '=', line.order_id.id)])
                if subscriptions:
                    for subscription in subscriptions:
                        if subscription.plan_id.id == line.product_id.subscription_plan_id.id:
                            new_line = [(0, 0, {'product_id': line.product_id.id,
                                        'product_qty': line.product_uom_qty,
                                        'analytic_account_id': line.analytic_account_id.id,
                            })]
                            subscription.product_line_ids = new_line
                            msg_body = _("New line Product (%s): <a href=# data-oe-model=subscription.package data-oe-id=%d>%s</a>") % (line.product_id.name, line.order_id.subscription_id.id, line.order_id.subscription_id.name)
                        else:
                            line.order_id.sudo().create_service_subscription()
                            line.order_id._compute_subscription_count()
                            msg_body = _("Subscription Created (%s): <a href=# data-oe-model=subscription.package data-oe-id=%d>%s</a>") % (line.product_id.name, line.order_id.subscription_id.id, line.order_id.subscription_id.name)
                            line.order_id.message_post(body=msg_body)
        return lines

    def _prepare_values_product(self):
        values = list()
        for line in self:
            values.append((0, False, {
                'product_id': line.product_id.id,
                'analytic_account_id': line.analytic_account_id.id,
                'product_qty': line.product_uom_qty,
                'product_uom_id': line.product_uom.id,
                'unit_price': line.price_unit,
            }))
        return values
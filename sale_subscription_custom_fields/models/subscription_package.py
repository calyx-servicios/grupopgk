from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class SubscriptionPackageProductLine(models.Model):
    _inherit = 'subscription.package.product.line'

    tax_id = fields.Many2many(
        'account.tax',
        string='Taxes',
        context={'active_test': False},
        check_company=True,
    )
    price_tax = fields.Float(compute='_compute_total_amount', string='Total Tax', store=True)
    price_subtotal = fields.Monetary(compute='_compute_total_amount', string='Subtotal', store=True)
    name_product = fields.Char(string='Description')

    def _register_hook(self):
        """Sanitize historical line taxes when the model is registered."""
        result = super()._register_hook()
        self.sudo().search([])._sanitize_company_taxes()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Create lines and sanitize taxes to the subscription company."""
        lines = super().create(vals_list)
        lines._sanitize_company_taxes()
        return lines

    def write(self, vals):
        """Keep taxes aligned with the line company after any update."""
        result = super().write(vals)
        if not self.env.context.get('skip_company_tax_sanitize'):
            self._sanitize_company_taxes()
        return result

    def read(self, fields=None, load='_classic_read'):
        """Auto-heal legacy cross-company taxes before UI reads tags.

        The many2many tags widget resolves tax names with current user rights.
        If a stale tax from another company is linked, opening the
        subscription raises AccessError on account.tax.
        """
        needs_tax_cleanup = fields is None or 'tax_id' in fields
        if needs_tax_cleanup and not self.env.context.get('skip_company_tax_sanitize'):
            self.sudo()._sanitize_company_taxes()
        return super().read(fields=fields, load=load)

    def _sanitize_company_taxes(self):
        """Keep only sale taxes from the subscription company on each line."""
        for line in self.sudo():
            if not line.company_id:
                continue

            allowed_taxes = line.tax_id.filtered(
                lambda tax: tax.company_id == line.company_id
                and tax.type_tax_use == 'sale'
            )
            new_tax_ids = list(allowed_taxes.ids)

            cross_company_taxes = line.tax_id.filtered(
                lambda tax: tax.company_id != line.company_id
                and tax.type_tax_use == 'sale'
            )

            mapped_ids = self._map_taxes_to_company(
                cross_company_taxes,
                line.company_id.id,
            )
            for tax_id in mapped_ids:
                if tax_id not in new_tax_ids:
                    new_tax_ids.append(tax_id)

            # Fallback to product sale taxes for the same company.
            if not new_tax_ids and line.product_id:
                new_tax_ids = line.product_id.taxes_id.filtered(
                    lambda tax: tax.company_id == line.company_id
                    and tax.type_tax_use == 'sale'
                ).ids

            # Final fallback to the company's default sale tax.
            if not new_tax_ids and line.company_id.account_sale_tax_id:
                new_tax_ids = [line.company_id.account_sale_tax_id.id]

            if set(line.tax_id.ids) != set(new_tax_ids):
                line.with_context(
                    skip_company_tax_sanitize=True,
                ).write({'tax_id': [(6, 0, new_tax_ids)]})

    def _map_taxes_to_company(self, taxes, company_id):
        """Map taxes to equivalent sale taxes in the target company.

        Matching criteria uses stable fiscal attributes to avoid random picks.
        """
        Tax = self.env['account.tax'].with_context(active_test=False).sudo()
        mapped_ids = []
        for tax in taxes:
            mapped_tax = Tax.search([
                ('company_id', '=', company_id),
                ('type_tax_use', '=', 'sale'),
                ('name', '=', tax.name),
                ('amount_type', '=', tax.amount_type),
                ('amount', '=', tax.amount),
                ('price_include', '=', tax.price_include),
            ], limit=1)
            if mapped_tax:
                mapped_ids.append(mapped_tax.id)
        return mapped_ids


    @api.depends('product_qty', 'unit_price', 'tax_id')
    def _compute_total_amount(self):
        """
        Compute the amounts of the Subscription product line.
        """
        for line in self:
            price = line.unit_price
            taxes = line.tax_id.compute_all(price, line.currency_id, line.product_qty, product=line.product_id, partner=line.subscription_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'total_amount': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'

    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')

    def create_invoice_forced(self):
        this_products_line = []
        for rec in self.product_line_ids:
            if rec.display_type == 'line_section':
                rec_list = [0, 0, {
                    'name': rec.name,  # Usa rec.name para secciones
                    'display_type': rec.display_type,
                    'sequence': rec.sequence,
                }]
            else:
                rec_list = [0, 0, {
                    'product_id': rec.product_id.id,
                    'name': rec.name_product,
                    'quantity': rec.product_qty,
                    'price_unit': rec.unit_price,
                    'analytic_account_id': rec.analytic_account_id.id,
                    'tax_ids': [(6, 0, rec.tax_id.ids)],
                    'sequence': rec.sequence,
                }]
            this_products_line.append(rec_list)
        move = self.env['account.move'].with_company(self.company_id).create(
            {
                'move_type': 'out_invoice',
                'date': fields.Date.today(),
                'invoice_date': fields.Date.today(),
                'state': 'draft',
                'sale_type_id': self.sale_order.type_id.id,
                'partner_id': self.partner_invoice_id.id,
                'invoice_payment_term_id': self.payment_term_id,
                'currency_id': self.partner_invoice_id.currency_id.id,
                'invoice_line_ids': this_products_line,
                'subscription_id': self.id,
                'company_id': self.company_id.id,
                'partner': self.sale_order.partner.id
            })
        if move:
            today_date = fields.Date.today()
            renewal_value = int(self.plan_id.renewal_value)
            if self.plan_id.renewal_period in ['days','weeks']:
                if self.plan_id.renewal_period == 'days':
                    self.next_invoice_date = today_date + relativedelta(
                        days=renewal_value)
                else:
                    self.next_invoice_date = today_date + relativedelta(
                        days=(renewal_value * 7))
            elif self.plan_id.renewal_period == 'months':
                self.next_invoice_date = today_date + relativedelta(
                    months=renewal_value)
            else:
                self.next_invoice_date = today_date + relativedelta(
                    years=renewal_value)
        return move
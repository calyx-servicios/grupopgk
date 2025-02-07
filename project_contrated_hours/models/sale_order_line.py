# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    contrated_hours = fields.Float(
        string='Contrated Hours'
    )
    total_project_amount = fields.Monetary(
        string='Total Project Amount',
        readonly=True,
        compute='_compute_total_project_amount'
    )
    order_state = fields.Selection(
        related='order_id.state',
        string="Order State",
        readonly=True,
        store=False
    )

    @api.onchange('contrated_hours', 'price_unit')
    def _compute_total_project_amount(self):
        """
        Multiply 'contracted hours' by 'unit price'
        """
        for rec in self:
            rec.total_project_amount = rec.contrated_hours * rec.price_unit

    def write(self, vals):
        """
        Add the values of the first sale order line pointing to project_id
        """
        res = super(SaleOrderLine, self).write(vals)
        for rec in self:
            if rec.project_id:
                lines = self.search([
                    ('project_id', '=', rec.project_id.id)
                ], order='create_date asc')
                if lines:
                    oldest_line = lines[0]
                    if oldest_line.contrated_hours and oldest_line.total_project_amount:
                        rec.project_id.write({
                            'contrated_hours': oldest_line.contrated_hours,
                            'total_project_amount': oldest_line.total_project_amount,
                            'project_currency_id': oldest_line.currency_id.id
                        })
        return res

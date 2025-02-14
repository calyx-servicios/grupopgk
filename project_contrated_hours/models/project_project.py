# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    contrated_hours = fields.Float(
        string='Contrated Hours',
        readonly=True,
        compute="_compute_hours_and_amount_project"
    )
    deviation_project_hours = fields.Float(
        string="Deviation Project Hours",
        compute="_compute_teorical_advance",
        help="Difference between contracted hours and actual timesheet hours."
    )
    total_project_amount = fields.Monetary(
        string='Total Project Amount',
        readonly=True
    )
    teorical_billing = fields.Monetary(
        string="Teorical Billing",
        compute="_compute_teorical_billing",
        help="Theoretical billing amount based on real advance percentage."
    )
    real_billing = fields.Monetary(
        string="Facturación",
        compute="_compute_real_billing"
    )
    project_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Project currency",
        readonly=True
    )
    teorical_advance = fields.Float(
        string="Teorical Advance",
        compute="_compute_teorical_advance",
        help="Expected project progress based on contracted hours and timesheets."
    )
    real_advance = fields.Float(
        string="Real Advance",
        help="Actual project progress in percentage."
    )
    forward_deviation = fields.Float(
        string="Forward Deviation",
        compute="_compute_forward_deviation",
        help="Difference between real and theoretical progress."
    )
    real_go_live_date = fields.Date(
        string="Real go live date",
        help="Actual date when the project went live."
    )
    expected_go_live_date = fields.Date(
        string="Expected go live date",
        help="Planned date for the project to go live."
    )
    delivery_time_deviation = fields.Integer(
        string="Delivery time deviation",
        compute="_compute_delivery_time_deviation",
        store=True,
        help="Difference in days between expected and actual go-live date."
    )

    def _compute_hours_and_amount_project(self):
        for rec in self:
            rec.contrated_hours = 0
            order_lines = self.env['sale.order.line'].search([
                    ('project_id', '=', rec.id),
                    ('state', '=', 'sale')
                ])
            if order_lines:
                for line in order_lines:
                    if line.contrated_hours:
                        rec.contrated_hours += line.contrated_hours

    @api.depends('invoice_count')
    def _compute_real_billing(self):
        for rec in self:
            rec.real_billing = False
            action_invoices = rec.action_open_project_invoices()
            invoices_domain = action_invoices["domain"]
            invoices = self.env['account.move'].search(invoices_domain)
            for invoice in invoices:
                rec.real_billing += invoice.amount_total

    @api.depends('expected_go_live_date', 'real_go_live_date')
    def _compute_delivery_time_deviation(self):
        """
        Computes the deviation in delivery time by calculating the difference in days
        between the expected and real go-live dates.
        """
        for rec in self:
            real_date = rec.real_go_live_date
            expected_date = rec.expected_go_live_date
            if real_date and expected_date:
                rec.delivery_time_deviation = (expected_date - real_date).days
            else:
                rec.delivery_time_deviation = 0

    @api.depends('total_timesheet_time', 'contrated_hours')
    def _compute_teorical_advance(self):
        """
        Calculates the theoretical advance of the project by dividing the total timesheet
        hours by the contracted hours. Also computes the deviation in project hours.
        """
        for rec in self:
            rec.teorical_advance = False
            rec.deviation_project_hours = False
            if rec.total_timesheet_time and rec.contrated_hours:
                rec.teorical_advance = (float(rec.total_timesheet_time) / rec.contrated_hours)
                rec.deviation_project_hours = float(rec.total_timesheet_time) - rec.contrated_hours

    @api.depends('real_advance', 'teorical_advance')
    def _compute_forward_deviation(self):
        """
        Computes the forward deviation as the difference between real and theoretical
        progress percentages.
        """
        for rec in self:
            rec.forward_deviation = False
            if rec.teorical_advance:
                rec.forward_deviation = rec.real_advance - rec.teorical_advance

    @api.depends('real_advance', 'total_project_amount')
    def _compute_teorical_billing(self):
        """
        Computes the theoretical billing by multiplying the real advance percentage
        by the total project amount.
        """
        for rec in self:
            rec.teorical_billing = False
            if rec.total_project_amount:
                rec.teorical_billing = rec.real_advance * rec.total_project_amount

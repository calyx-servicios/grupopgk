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
        string="Billing",
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
    service_area_id = fields.Many2one(
        comodel_name="account.analytic.group",
        string="Service Area"
    )
    project_manager = fields.Char(
        string="PM"
    )
    reference_month = fields.Text(
        string="Comment actual month"
    )
    action_suggested = fields.Text(
        string="Action suggested"
    )
    comment = fields.Text(
        string="Comment DC"
    )
    comment_last_month = fields.Text(
        string="Comment last month"
    )
    visible_fields_project = fields.Boolean(
        related='service_area_id.visible_fields_project'
    )
    billing_multyply_advance = fields.Monetary(
        string="Billing multyply by advance",
        compute="_compute_billing_multyply_advance"
    )
    billing_deviation = fields.Monetary(
        string="Billing deviation",
        compute="_compute_billing_deviation"
    )
    remaining_hours = fields.Float(
        string="Remaining hours",
        compute="_compute_remaining_hours"
    )
    billing_hours = fields.Float(
        string="Billing hours",
        compute="_compute_real_billing"
    )
    hours_multiply_advance = fields.Float(
        string="Advance by hours",
        compute="_compute_remaining_hours"
    )
    advance_deviation = fields.Float(
        string="Advance deviation",
        compute="_compute_remaining_hours"
    )

    def _compute_remaining_hours(self):
        """ Enzo: I made a variable abbreviation to avoid very long lines """
        for rec in self:
            rec.remaining_hours = False
            rec.hours_multiply_advance = False
            rec.advance_deviation = False
            if rec.contrated_hours:
                rec.remaining_hours = rec.contrated_hours - rec.total_timesheet_time
                rec.advance_deviation = rec.hours_multiply_advance - rec.total_timesheet_time
                if rec.billing_hours and rec.total_timesheet_time:
                    b_hours = rec.billing_hours
                    tt_time = rec.total_timesheet_time
                    c_hours = rec.contrated_hours
                    rec.hours_multiply_advance = (c_hours / tt_time) * b_hours

    def _compute_billing_deviation(self):
        """ Enzo: I made a variable abbreviation to avoid very long lines"""
        for rec in self:
            bmadv = rec.total_project_amount
            ra = rec.real_advance
            rb = rec.real_billing
            rec.billing_deviation = rb - (bmadv * ra)

    def _compute_billing_multyply_advance(self):
        """ Enzo: I made a variable abbreviation to avoid very long lines """
        for rec in self:
            rec.billing_multyply_advance = False
            if rec.total_project_amount and rec.contrated_hours and rec.total_timesheet_time:
                tpa = rec.total_project_amount
                c_hours = rec.contrated_hours
                tt_time = rec.total_timesheet_time
                rec.billing_multyply_advance = (tpa / c_hours) * tt_time

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
            rec.billing_hours = 0
            action_invoices = rec.action_open_project_invoices()
            invoices_domain = action_invoices["domain"]
            invoices = self.env['account.move'].search(invoices_domain)
            for invoice in invoices:
                for line in invoice.invoice_line_ids:
                    rec.billing_hours += line.quantity
                    rec.real_billing += line.price_subtotal

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
                rec.delivery_time_deviation = (real_date - expected_date).days
            else:
                rec.delivery_time_deviation = 0

    @api.depends('total_timesheet_time', 'contrated_hours')
    def _compute_teorical_advance(self):
        """
        Calculate the theoretical progress and the deviation of hours:
        - theoretical progress = hours consumed / contracted hours (if contracted hours > 0)
        - deviation = contracted hours – consumed hours (if at least one of the two is defined)
        tt = total timesheet
        ch = contracted hours
        """
        for r in self:
            tt = float(r.total_timesheet_time or 0)
            ch = float(r.contrated_hours or 0)
            if ch > 0:
                r.teorical_advance = tt / ch
            else:
                r.teorical_advance = False
            r.deviation_project_hours = ch - tt

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
                tpa = rec.total_project_amount
                ra = rec.real_advance
                rec.teorical_billing = tpa - (ra * tpa)

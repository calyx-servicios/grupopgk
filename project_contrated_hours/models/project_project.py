# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

ADALY_COMPANY_ID = 2


class ProjectProject(models.Model):
    _inherit = 'project.project'

    contrated_hours = fields.Float(
        string='Contrated Hours'
    )
    deviation_project_hours = fields.Float(
        string="Deviation Project Hours - Calyx",
        compute="_compute_teorical_advance",
        help="Difference between contracted hours and actual timesheet hours."
    )
    total_project_amount = fields.Monetary(
        string='Total Project Amount'
    )
    teorical_billing = fields.Monetary(
        string="Teorical Billing - PGK",
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
    area = fields.Char(
        string="Area"
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
    billing_multyply_advance = fields.Float(
        string="Billing multyply by advance - PGK",
        compute="_compute_billing_multyply_advance"
    )
    billing_deviation = fields.Monetary(
        string="Billing deviation - Calyx",
        compute="_compute_billing_deviation"
    )
    remaining_hours = fields.Float(
        string="Remaining hours",
        compute="_compute_remaining_hours"
    )
    left_hours = fields.Float(
        string="Left Hours",
        compute="_compute_left_hours"
    )
    billing_hours = fields.Float(
        string="Billing hours",
        compute="_compute_real_billing"
    )
    hours_multiply_advance = fields.Float(
        string="Advance by hours - Calyx",
        compute="_compute_remaining_hours"
    )
    advance_deviation = fields.Float(
        string="Advance deviation - Calyx",
        compute="_compute_remaining_hours"
    )
    advance_deviation_pgk = fields.Float(
        string="Advance deviation - PGK",
        compute="_compute_billing_multyply_advance"
    )
    advance_billing = fields.Float(
        string="Advance billing - PGK",
        compute="_compute_advance_billing"
    )
    cost = fields.Monetary(
        string="Cost",
        compute="_compute_cost"
    )
    overbilling_cost_rate = fields.Float(
        string="Overbilling Cost",
        compute="_compute_overbilling_cost"
    )
    achievement_rate = fields.Float(
        string="Achievement Rate",
        compute="_compute_overbilling_cost"
    )

    @api.depends('real_billing', 'cost')
    def _compute_overbilling_cost(self):
        """ 
        Calcular:
        - overbilling_cost_rate = % de costos sobre ingresos
        - achievement_rate según regla de negocio:
          * Si % de costos = 0  -> 100%
          * Si % de costos > 0  -> 55% / % de costos
        """
        for rec in self:
            rec.overbilling_cost_rate = 0.0
            rec.achievement_rate = 0.0

            # Si no hay facturación real, no podemos calcular el % de costos
            if not rec.real_billing:
                continue

            # % de costos sobre ingresos
            if rec.cost:
                rec.overbilling_cost_rate = rec.cost / rec.real_billing
            else:
                rec.overbilling_cost_rate = 0.0

            # Regla solicitada
            if rec.overbilling_cost_rate == 0:
                # 100% (1.0 en float, el widget percentage lo mostrará como 100%)
                rec.achievement_rate = 1.0
            else:
                rec.achievement_rate = 0.55 / rec.overbilling_cost_rate

    def _compute_cost(self):
        """
        Calcular el costo teniendo en cuenta solo las líneas de timesheet y las líneas
        de órdenes de compra asociadas a la cuenta analítica del proyecto.

        Adaly S.A. no pesifica sus comprobantes al cargarlos (moneda funcional
        USD): se excluye de estas dos búsquedas y, si ya se emitió el informe
        de consolidación del período, se suma aparte el costo ya pesificado
        desde `account.consolidation.data`. Sin informe, el costo de Adaly
        queda afuera del total (no se estima).
        """
        for rec in self:
            total_cost = 0.0
            if rec.analytic_account_id:
                # Costos desde partes de horas
                timesheet_lines = self.env['account.analytic.line'].search([
                    ('account_id', '=', rec.analytic_account_id.id),
                    ('timesheet_id', '!=', False),
                    ('employee_id.company_id', '!=', ADALY_COMPANY_ID),
                ])
                for line in timesheet_lines:
                    total_cost += abs(line.amount)

                # Costos desde facturas de proveedor asociadas a órdenes de compra
                lines_from_purchase_orders = self.env['account.analytic.line'].search([
                    ('account_id', '=', rec.analytic_account_id.id),
                    ('amount', '<', 0),
                    ('move_id', '!=', False),
                    ('move_id.company_id', '!=', ADALY_COMPANY_ID),
                ])
                for line in lines_from_purchase_orders:
                    move = line.move_id.move_id  # Acceso a account.move
                    if move.move_type == 'in_invoice':
                        total_cost += abs(line.amount)
                    elif move.move_type == 'in_refund':
                        total_cost -= abs(line.amount)  # un reembolso resta al costo total

                # Adaly: costo ya pesificado por el informe de consolidación (si existe)
                consolidated_cost = self.env['account.consolidation.data'].search([
                    ('analytic_account_id', '=', rec.analytic_account_id.id),
                    ('daughter_account.general_account_id.internal_group', '!=', 'income'),
                    '|',
                    ('daughter_account.move_id.company_id', '=', ADALY_COMPANY_ID),
                    ('daughter_account.employee_id.company_id', '=', ADALY_COMPANY_ID),
                ])
                total_cost += sum(abs(a) for a in consolidated_cost.mapped('amount'))

            rec.cost = total_cost

    @api.depends('contrated_hours', 'date_start', 'create_date')
    def _compute_advance_billing(self):
        for rec in self:
            rec.advance_billing = False
            if rec.contrated_hours and (rec.date_start or rec.create_date):
                start_date = rec.date_start
                if not start_date:
                    # Fallback to create_date only when project start date is not defined.
                    start_date = fields.Datetime.to_datetime(rec.create_date).date()

                today = fields.Date.context_today(rec)
                months_elapsed = (
                    (today.year - start_date.year) * 12
                    + (today.month - start_date.month)
                )
                months_elapsed = max(months_elapsed, 0)
                rec.advance_billing = (rec.contrated_hours / 12) * months_elapsed

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

    @api.depends('contrated_hours', 'total_timesheet_time')
    def _compute_left_hours(self):
        """ Compute left hours as contracted hours minus total timesheet time """
        for rec in self:
            if rec.contrated_hours and rec.total_timesheet_time:
                rec.left_hours = rec.contrated_hours - rec.total_timesheet_time
            else:
                rec.left_hours = False

    def _compute_billing_deviation(self):
        """ Enzo: I made a variable abbreviation to avoid very long lines"""
        for rec in self:
            bmadv = rec.total_project_amount
            ra = rec.real_advance
            rb = rec.real_billing
            rec.billing_deviation = rb - (bmadv * ra)

    def _compute_billing_multyply_advance(self):
        # Facturación por avance - PGK = (monto total del proyecto / horas contratadas) * horas consumidas
        # Desvío de horas - PGK = Horas por avance (pgk) - Horas consumidas
        for rec in self:
            rec.billing_multyply_advance = False
            rec.advance_deviation_pgk = False
            if rec.contrated_hours and rec.total_timesheet_time:
                rec.billing_multyply_advance = (rec.total_project_amount / rec.contrated_hours) * rec.total_timesheet_time
                rec.advance_deviation_pgk = rec.advance_billing - rec.total_timesheet_time

    def action_open_project_invoices_with_credits(self):
        """Get all invoices and credit notes for this project"""
        invoices = self.env['account.move'].search([
            ('line_ids.analytic_account_id', '!=', False),
            ('line_ids.analytic_account_id', 'in', self.analytic_account_id.ids),
            ('move_type', 'in', ['out_invoice', 'out_refund'])
        ])
        action = {
            'name': _('Invoices & Credit Notes'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'views': [[False, 'tree'], [False, 'form'], [False, 'kanban']],
            'domain': [('id', 'in', invoices.ids)],
            'context': {
                'create': False,
            }
        }
        if len(invoices) == 1:
            action['views'] = [[False, 'form']]
            action['res_id'] = invoices.id
        return action

    @api.depends('analytic_account_id')
    def _compute_real_billing(self):
        """Compute billing amount and billed hours from posted income lines.

        Adaly S.A. no pesifica sus comprobantes al momento de cargarlos (su
        moneda funcional es USD): se excluye de esta suma en ARS y, si ya se
        emitio el informe de consolidacion del periodo, se suma aparte el
        valor que ese informe dejo pesificado en `account.consolidation.data`.
        Mientras no haya informe, el aporte de Adaly queda afuera del total
        (no se estima), tal como pide el requerimiento.
        """
        for rec in self:
            rec.real_billing = 0.0
            rec.billing_hours = 0
            if not rec.analytic_account_id:
                continue

            move_lines = self.env['account.move.line'].search([
                ('analytic_account_id', '=', rec.analytic_account_id.id),
                ('move_id.state', '=', 'posted'),
                ('account_id.internal_group', '=', 'income'),
                ('display_type', '=', False),
                ('exclude_from_invoice_tab', '=', False),
                ('company_id', '!=', ADALY_COMPANY_ID),
            ])

            for line in move_lines:
                line_amount = line.credit - line.debit
                rec.real_billing += line_amount

                if line_amount > 0:
                    rec.billing_hours += line.quantity
                elif line_amount < 0:
                    rec.billing_hours -= line.quantity

            consolidated_billing = self.env['account.consolidation.data'].search([
                ('analytic_account_id', '=', rec.analytic_account_id.id),
                ('daughter_account.general_account_id.internal_group', '=', 'income'),
                '|',
                ('daughter_account.move_id.company_id', '=', ADALY_COMPANY_ID),
                ('daughter_account.employee_id.company_id', '=', ADALY_COMPANY_ID),
            ])
            rec.real_billing += sum(consolidated_billing.mapped('amount'))

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

    @api.depends('billing_multyply_advance', 'real_billing')
    def _compute_teorical_billing(self):
        # Desvío de facturación - PGK = Facturación realizada - Facturación por avance
        for rec in self:
            rec.teorical_billing = rec.real_billing - rec.billing_multyply_advance

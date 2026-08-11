from datetime import date
from uuid import uuid4

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SubscriptionMassiveUpdate(models.TransientModel):
    _name = 'subscription.massive_update'
    _description = 'Wizard massive update'


    subscriptions_ids = fields.Many2many('subscription.package', string='Subscriptions')
    fields_to_update = fields.Selection([
        ('price', 'Price'),
        ('plan', 'Plan'),
        ('date', 'Date'),
        ('plan_and_date', 'Plan and Date'),
    ], string='Fields to Update')
    percentage = fields.Float('Percentage to raise')
    ipc_period_from = fields.Selection(
        selection='_selection_ipc_periods',
        string='Desde',
    )
    ipc_period_to = fields.Selection(
        selection='_selection_ipc_periods',
        string='Hasta',
    )
    date = fields.Date('Next Invoice Date')
    subscriptions_plan_id = fields.Many2one('subscription.package.plan', string='Subscription Plan')

    @api.model
    def _selection_ipc_periods(self):
        """Return available MM/YYYY periods from IPC master for dropdowns."""
        periods = self.env['subscription.ipc.monthly'].search(
            [], order='period_year asc, period_month asc'
        )
        return [(period.period, period.period) for period in periods]

    @api.model
    def _period_to_date(self, period):
        """Convert an MM/YYYY string into a date pointing to month first day."""
        month_text, year_text = period.split('/')
        return date(int(year_text), int(month_text), 1)

    @api.model
    def _period_label(self, period_date):
        """Convert a date into MM/YYYY label used by the IPC master."""
        return f'{period_date.month:02d}/{period_date.year:04d}'

    @api.model
    def _get_period_labels_inclusive(self, period_from, period_to):
        """Build all MM/YYYY labels for an inclusive monthly range."""
        start_date = self._period_to_date(period_from)
        end_date = self._period_to_date(period_to)
        if start_date > end_date:
            raise ValidationError(_('Desde no puede ser posterior a Hasta.'))

        period_labels = []
        cursor = start_date
        while cursor <= end_date:
            period_labels.append(self._period_label(cursor))
            cursor += relativedelta(months=1)
        return period_labels

    def _validate_ipc_period_range(self):
        """Validate range integrity and ensure every month has IPC configured."""
        self.ensure_one()
        if not self.ipc_period_from and not self.ipc_period_to:
            return
        if not self.ipc_period_from or not self.ipc_period_to:
            raise ValidationError(
                _('Para usar cálculo IPC debe completar ambos períodos: Desde y Hasta.')
            )

        period_labels = self._get_period_labels_inclusive(
            self.ipc_period_from,
            self.ipc_period_to,
        )
        if not period_labels:
            raise ValidationError(
                _('Debe existir al menos un período válido para calcular IPC.')
            )

        ipc_records = self.env['subscription.ipc.monthly'].search(
            [('period', 'in', period_labels)]
        )
        ipc_by_period = {record.period: record for record in ipc_records}
        missing_periods = [period for period in period_labels if period not in ipc_by_period]
        if missing_periods:
            raise ValidationError(
                _(
                    'No se puede continuar porque faltan IPC para estos períodos: %s'
                ) % ', '.join(missing_periods)
            )
        return ipc_by_period, period_labels

    def _compute_compound_ipc_percentage(self):
        """Compute compounded IPC percentage for selected inclusive range."""
        self.ensure_one()
        validation_result = self._validate_ipc_period_range()
        if not validation_result:
            return False
        ipc_by_period, period_labels = validation_result

        accumulated_factor = 1.0
        for period in period_labels:
            ipc_percentage = ipc_by_period[period].percentage or 0.0
            accumulated_factor *= (1 + (ipc_percentage / 100.0))
        return (accumulated_factor - 1) * 100

    @api.onchange('ipc_period_from', 'ipc_period_to')
    def _onchange_ipc_periods(self):
        """Autofill percentage with compounded IPC while keeping manual edit possible."""
        for wizard in self:
            if wizard.fields_to_update != 'price':
                continue
            if wizard.ipc_period_from and wizard.ipc_period_to:
                wizard.percentage = wizard._compute_compound_ipc_percentage()

    def update(self):
        self.ensure_one()
        for subscription in self.subscriptions_ids:
            if self.fields_to_update == 'price':
                update_type = 'manual_percentage'
                if self.ipc_period_from or self.ipc_period_to:
                    self._validate_ipc_period_range()
                    update_type = 'ipc'
                original_price = subscription.total_recurring_price
                percentage = (self.percentage / 100) + 1
                event_id = str(uuid4())
                update_datetime = fields.Datetime.now()
                if subscription.product_line_ids:
                    changes = _('<table><thead><tr><th>Product</th><th>Original Price</th><th>Current Price</th></tr></thead><tbody>')
                    try:
                        for line in subscription.product_line_ids:
                            current_price = line.unit_price
                            new_price = current_price * percentage
                            line.with_context(
                                tariff_update_event_id=event_id,
                                tariff_update_datetime=update_datetime,
                                tariff_update_type=update_type,
                                tariff_applied_percentage=self.percentage,
                            ).write({'unit_price': new_price})
                            changes += _('<tr><td>{}</td><td>{}</td><td>{}</td></tr>').format(line.product_id.display_name, current_price, new_price)
                    except Exception as e:
                        raise UserError(_('Error ({}) when trying to update product line in subscription with ID({})').format(e, subscription.id)) 
                    changes += '</tbody></table>'
                else:
                    changes = ''
                message_body = _('Subscription prices have been updated by <a href=# data-oe-model=res.users data-oe-id={}>{}</a> with a {}% increase. The total price of subscription {} has been changed from {} to {}. The following changes were made to product lines: {}').format(
                self.env.user.id, self.env.user.name, self.percentage, subscription.display_name, original_price, subscription.total_recurring_price, changes)
                subscription.message_post(body=message_body)
            elif self.fields_to_update == 'plan':
                old_plan_name = subscription.plan_id.name
                subscription.plan_id = self.subscriptions_plan_id.id
                message_body = _('Subscription plan has been updated by <a href=# data-oe-model=res.users data-oe-id={}>{}</a>. The plan of subscription {} has been changed from {} to {}.').format(
                self.env.user.id, self.env.user.name, subscription.display_name, old_plan_name, subscription.plan_id.name)
                subscription.message_post(body=message_body)
            elif self.fields_to_update == 'date':
                old_date = subscription.next_invoice_date
                subscription.next_invoice_date = self.date
                message_body = _('Subscription next invoice date has been updated by <a href=# data-oe-model=res.users data-oe-id={}>{}</a>. The next invoice date of subscription {} has been changed from {} to {}.').format(
                self.env.user.id, self.env.user.name, subscription.display_name, old_date, subscription.next_invoice_date)
                subscription.message_post(body=message_body)
            elif self.fields_to_update == 'plan_and_date':
                old_plan_name = subscription.plan_id.name
                old_date = subscription.next_invoice_date
                subscription.plan_id = self.subscriptions_plan_id.id
                subscription.next_invoice_date = self.date
                message_body = _('Subscription plan and next invoice date have been updated by <a href=# data-oe-model=res.users data-oe-id={}>{}</a>. The plan of subscription {} has been changed from {} to {}. The next invoice date of subscription {} has been changed from {} to {}.').format(
                self.env.user.id, self.env.user.name, subscription.display_name, old_plan_name, subscription.plan_id.name, subscription.display_name, old_date, subscription.next_invoice_date)
                subscription.message_post(body=message_body)

    def massive_update(self, window_title, ids):
        wiz = self.create({
            'subscriptions_ids': ids,
        })
        return wiz.open_wizard(window_title)

    def open_wizard(self, title):
        view = self.env.ref('subscription_massive_update.wizard_massive_update_form')
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': self._name,
            'target': 'new',
            'view_id': view.id,
            'view_mode': 'form',
            'res_id': self.id,
            'context': self.env.context,
        }
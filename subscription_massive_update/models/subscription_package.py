import uuid

from odoo import _, fields, models
from odoo.tools.float_utils import float_compare, float_is_zero


TARIFF_UPDATE_TYPE_SELECTION = [
    ("manual", "Manual"),
    ("manual_percentage", "Porcentaje manual"),
    ("ipc", "IPC"),
]

TARIFF_FREQUENCY_SELECTION = [
    ("monthly", "Mensual"),
    ("bimonthly", "Bimestral"),
    ("quarterly", "Trimestral"),
    ("four_monthly", "Cuatrimestral"),
    ("semiannual", "Semestral"),
    ("annual", "Anual"),
]


class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'

    tariff_update_frequency = fields.Selection(
        selection=TARIFF_FREQUENCY_SELECTION,
        string="Tipo de actualización",
    )
    last_tariff_update_at = fields.Datetime(
        string="Última actualización de tarifa",
        readonly=True,
        copy=False,
    )
    tariff_update_history_ids = fields.One2many(
        "subscription.tariff.update.history",
        "subscription_id",
        string="Historial de actualizaciones",
        readonly=True,
        copy=False,
    )

    def update_massive(self):
        massive_update_obj = self.env['subscription.massive_update']
        subs_ids = None
        for sub in self:
            if sub.stage_id.category != 'closed':
                if not subs_ids:
                    subs_ids = sub
                else:
                    subs_ids += sub
        return massive_update_obj.massive_update(_('Massive Update'), subs_ids)


class SubscriptionPackageProductLine(models.Model):
    _inherit = "subscription.package.product.line"

    def write(self, vals):
        """Track every unit price change to keep tariff update traceability."""
        if "unit_price" not in vals:
            return super().write(vals)

        previous_prices = {line.id: line.unit_price for line in self}
        result = super().write(vals)

        history_model = self.env["subscription.tariff.update.history"]
        event_id = self.env.context.get("tariff_update_event_id")
        if not event_id:
            event_id = str(uuid.uuid4())

        update_datetime = self.env.context.get("tariff_update_datetime")
        update_type = self.env.context.get("tariff_update_type") or "manual"
        ctx_percentage = self.env.context.get("tariff_applied_percentage")

        history_vals = []
        subscriptions_to_touch = self.env["subscription.package"]
        for line in self:
            old_price = previous_prices.get(line.id)
            new_price = line.unit_price
            if old_price is None:
                continue

            precision_digits = line.currency_id.decimal_places or 2
            if float_compare(
                old_price,
                new_price,
                precision_digits=precision_digits,
            ) == 0:
                continue

            applied_percentage = ctx_percentage
            if applied_percentage is None:
                if float_is_zero(old_price, precision_digits=precision_digits):
                    applied_percentage = 0.0
                else:
                    applied_percentage = ((new_price - old_price) / old_price) * 100

            history_vals.append(
                {
                    "subscription_id": line.subscription_id.id,
                    "subscription_line_id": line.id,
                    "product_id": line.product_id.id,
                    "quantity": line.product_qty,
                    "analytic_account_id": line.analytic_account_id.id,
                    "update_datetime": update_datetime or fields.Datetime.now(),
                    "update_type": update_type,
                    "applied_percentage": applied_percentage,
                    "old_price": old_price,
                    "new_price": new_price,
                    "user_id": self.env.user.id,
                    "event_id": event_id,
                }
            )
            subscriptions_to_touch |= line.subscription_id

        if history_vals:
            history_model.create(history_vals)
            subscriptions_to_touch.write(
                {"last_tariff_update_at": update_datetime or fields.Datetime.now()}
            )
        return result
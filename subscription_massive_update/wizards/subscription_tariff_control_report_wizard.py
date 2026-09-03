from datetime import date, datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang


class SubscriptionTariffUpdateControlWizard(models.TransientModel):
    _name = "subscription.tariff.update.control.wizard"
    _description = "Subscription Tariff Update Control Report"

    company_ids = fields.Many2many(
        "res.company",
        string="Compañías",
        default=lambda self: self._default_company_ids(),
        required=True,
    )
    subscription_state = fields.Selection(
        selection="_selection_subscription_states",
        string="Estado de suscripción",
        default=lambda self: self._default_subscription_state(),
        required=True,
    )
    date_from = fields.Date(
        string="Desde",
        required=True,
        default=lambda self: self._default_date_from(),
    )
    date_to = fields.Date(
        string="Hasta",
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    update_frequency = fields.Selection(
        selection=[
            ("all", "Todas"),
            ("monthly", "Mensual"),
            ("bimonthly", "Bimestral"),
            ("quarterly", "Trimestral"),
            ("four_monthly", "Cuatrimestral"),
            ("semiannual", "Semestral"),
            ("annual", "Anual"),
        ],
        string="Tipo de actualización",
        default="all",
        required=True,
    )
    currency_filter = fields.Selection(
        selection=[
            ("all", "Todas"),
            ("ars", "ARS"),
            ("usd", "USD"),
        ],
        string="Moneda",
        default="all",
        required=True,
    )

    @api.model
    def _default_company_ids(self):
        return self.env.user.company_ids

    @api.model
    def _default_date_from(self):
        today = fields.Date.context_today(self)
        return date(today.year, 1, 1)

    @api.model
    def _selection_subscription_states(self):
        stages = self.env["subscription.package.stage"].search(
            [], order="sequence, id"
        )
        return [("all", "Todas")] + [
            (str(stage.id), stage.name) for stage in stages
        ]

    @api.model
    def _default_subscription_state(self):
        stage = self.env["subscription.package.stage"].search(
            [("category", "=", "progress")], order="sequence, id", limit=1
        )
        return str(stage.id) if stage else "all"

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("La fecha Desde no puede ser posterior a Hasta."))

    def _get_subscription_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "in", self.company_ids.ids),
        ]
        if self.subscription_state != "all":
            domain.append(("stage_id", "=", int(self.subscription_state)))
        if self.currency_filter == "ars":
            domain.append(("currency_id.name", "=", "ARS"))
        elif self.currency_filter == "usd":
            domain.append(("currency_id.name", "=", "USD"))
        return domain

    def _get_datetime_limits(self):
        self.ensure_one()
        date_from_dt = datetime.combine(self.date_from, time.min)
        date_to_dt = datetime.combine(self.date_to, time.max)
        return date_from_dt, date_to_dt

    def _selection_label(self, field_name, value):
        if field_name == "subscription_state":
            values = self._selection_subscription_states()
        else:
            values = self._fields[field_name].selection
        return dict(values).get(value, value or "")

    def _subscription_frequency_label(self, subscription):
        selection = dict(subscription._fields["tariff_update_frequency"].selection)
        return selection.get(subscription.tariff_update_frequency, "")

    def _get_analytic_names(self, analytic_ids):
        """Load analytic names without triggering unrelated computed fields."""
        valid_ids = list({analytic_id for analytic_id in analytic_ids if analytic_id})
        if not valid_ids:
            return {}
        self.env.cr.execute(
            "SELECT id, name FROM account_analytic_account WHERE id IN %s",
            [tuple(valid_ids)],
        )
        return dict(self.env.cr.fetchall())

    def _format_amount(self, amount):
        """Format report amounts with the current user's locale settings."""
        return formatLang(self.env, amount or 0.0, digits=2)

    def _prepare_section_one(self, histories, analytic_names, line_snapshots):
        rows = []
        for history in histories:
            subscription = history.subscription_id
            product = history.product_id
            snapshot = line_snapshots.get((subscription.id, product.id))
            qty = history.quantity or (
                snapshot.product_qty if snapshot else 0.0
            )
            analytic_id = history.analytic_account_id.id or (
                snapshot.analytic_account_id.id if snapshot else False
            )

            row = {
                "subscription_id": subscription.id,
                "partner_id": subscription.partner_id.id,
                "partner_name": subscription.partner_id.display_name or "",
                "company": subscription.company_id.display_name or "",
                "so": subscription.sale_order.name or "",
                "sus": subscription.name or "",
                "update_frequency": self._subscription_frequency_label(subscription),
                "change_date": history.update_datetime,
                "user": history.user_id.display_name or "",
                "product": product.display_name if product else "",
                "analytic_account": analytic_names.get(analytic_id, ""),
                "qty": qty,
                "old_price": history.old_price,
                "new_price": history.new_price,
                "subtotal_net": qty * history.new_price,
                "old_price_display": self._format_amount(history.old_price),
                "new_price_display": self._format_amount(history.new_price),
                "subtotal_net_display": self._format_amount(
                    qty * history.new_price
                ),
                "applied_percentage": history.applied_percentage,
                "currency": subscription.currency_id.name or "",
                "commercial": subscription.user_id.display_name or "",
                "event_id": history.event_id,
                "line_key": product.id if product else f"history-{history.id}",
            }
            rows.append(row)
        return rows

    def _prepare_partner_subtotals(self, section_one_rows):
        line_totals = {}
        for row in section_one_rows:
            key = (row["subscription_id"], row["line_key"])
            old_subtotal = row["qty"] * row["old_price"]
            new_subtotal = row["qty"] * row["new_price"]
            if key not in line_totals:
                line_totals[key] = {
                    "partner_id": row["partner_id"],
                    "partner_name": row["partner_name"],
                    "so": row["so"],
                    "original": old_subtotal,
                    "current": new_subtotal,
                }
            else:
                line_totals[key]["current"] += new_subtotal

        partner_accum = {}
        for totals in line_totals.values():
            partner_key = (totals["partner_id"], totals["so"])
            if partner_key not in partner_accum:
                partner_accum[partner_key] = {
                    "partner_name": totals["partner_name"],
                    "so": totals["so"],
                    "total_original": 0.0,
                    "total_current": 0.0,
                }
            partner_accum[partner_key]["total_original"] += totals["original"]
            partner_accum[partner_key]["total_current"] += totals["current"]

        subtotals = []
        for partner_data in sorted(
            partner_accum.values(), key=lambda p: p["partner_name"] or ""
        ):
            total_original = partner_data["total_original"]
            total_current = partner_data["total_current"]
            if total_original:
                variation = ((total_current - total_original) / total_original) * 100
            else:
                variation = 0.0
            subtotals.append(
                {
                    "so": partner_data["so"],
                    "partner_name": partner_data["partner_name"],
                    "total_original": total_original,
                    "total_current": total_current,
                    "total_original_display": self._format_amount(total_original),
                    "total_current_display": self._format_amount(total_current),
                    "variation": variation,
                }
            )
        return subtotals

    def _prepare_section_two(self, subscriptions_without_updates, analytic_names):
        rows = []
        for subscription in subscriptions_without_updates:
            valid_lines = subscription.product_line_ids.filtered(
                lambda line: line.display_type not in ("line_section", "line_note")
            )
            if not valid_lines:
                rows.append(
                    {
                        "company": subscription.company_id.display_name or "",
                        "so": subscription.sale_order.name or "",
                        "sus": subscription.name or "",
                        "update_frequency": self._subscription_frequency_label(subscription),
                        "last_update": subscription.last_tariff_update_at,
                        "product": "",
                        "analytic_account": "",
                        "qty": 0.0,
                        "current_price": 0.0,
                        "subtotal_net": 0.0,
                        "current_price_display": self._format_amount(0.0),
                        "subtotal_net_display": self._format_amount(0.0),
                        "currency": subscription.currency_id.name or "",
                        "commercial": subscription.user_id.display_name or "",
                    }
                )
                continue

            for line in valid_lines:
                qty = line.product_qty or 0.0
                current_price = line.unit_price or 0.0
                rows.append(
                    {
                        "company": subscription.company_id.display_name or "",
                        "so": subscription.sale_order.name or "",
                        "sus": subscription.name or "",
                        "update_frequency": self._subscription_frequency_label(subscription),
                        "last_update": subscription.last_tariff_update_at,
                        "product": line.product_id.display_name or "",
                        "analytic_account": analytic_names.get(
                            line.analytic_account_id.id, ""
                        ),
                        "qty": qty,
                        "current_price": current_price,
                        "subtotal_net": qty * current_price,
                        "current_price_display": self._format_amount(current_price),
                        "subtotal_net_display": self._format_amount(
                            qty * current_price
                        ),
                        "currency": subscription.currency_id.name or "",
                        "commercial": subscription.user_id.display_name or "",
                    }
                )
        return rows

    def _prepare_report_data(self):
        self.ensure_one()
        subscriptions = self.env["subscription.package"].search(
            self._get_subscription_domain(),
            order="partner_id, name",
        )
        date_from_dt, date_to_dt = self._get_datetime_limits()

        histories = self.env["subscription.tariff.update.history"].search(
            [
                ("subscription_id", "in", subscriptions.ids),
                ("update_datetime", ">=", fields.Datetime.to_string(date_from_dt)),
                ("update_datetime", "<=", fields.Datetime.to_string(date_to_dt)),
            ],
            order="update_datetime asc, id asc",
        )
        if self.update_frequency != "all":
            histories = histories.filtered(
                lambda history: history.subscription_id.tariff_update_frequency
                == self.update_frequency
            )

        line_snapshots = {}
        for subscription in subscriptions:
            for line in subscription.product_line_ids.filtered(
                lambda item: item.display_type not in ("line_section", "line_note")
            ):
                line_snapshots.setdefault(
                    (subscription.id, line.product_id.id), line
                )

        analytic_ids = histories.mapped("analytic_account_id").ids
        analytic_ids += subscriptions.mapped(
            "product_line_ids.analytic_account_id"
        ).ids
        analytic_names = self._get_analytic_names(analytic_ids)

        section_one_rows = self._prepare_section_one(
            histories, analytic_names, line_snapshots
        )
        partner_subtotals = self._prepare_partner_subtotals(section_one_rows)

        subscriptions_with_updates = set(histories.mapped("subscription_id").ids)
        subscriptions_without_updates = subscriptions.filtered(
            lambda subscription: subscription.id not in subscriptions_with_updates
        )
        section_two_rows = self._prepare_section_two(
            subscriptions_without_updates, analytic_names
        )

        return {
            "generated_at": fields.Datetime.now(),
            "filters": {
                "companies": ", ".join(self.company_ids.mapped("display_name")),
                "state": self._selection_label(
                    "subscription_state", self.subscription_state
                ),
                "date_from": self.date_from,
                "date_to": self.date_to,
                "update_frequency": self._selection_label(
                    "update_frequency", self.update_frequency
                ),
                "currency_filter": self._selection_label(
                    "currency_filter", self.currency_filter
                ),
            },
            "section_one_rows": section_one_rows,
            "partner_subtotals": partner_subtotals,
            "section_two_rows": section_two_rows,
        }

    def action_print_pdf(self):
        self.ensure_one()
        data = {"report_data": self._prepare_report_data()}
        return self.env.ref(
            "subscription_massive_update.action_report_subscription_tariff_control_pdf"
        ).report_action(self, data=data)

    def action_export_xlsx(self):
        self.ensure_one()
        data = {"report_data": self._prepare_report_data()}
        return self.env.ref(
            "subscription_massive_update.action_report_subscription_tariff_control_xlsx"
        ).report_action(self, data=data)
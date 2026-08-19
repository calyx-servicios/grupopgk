import re
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


PERIOD_PATTERN = re.compile(r"^(0[1-9]|1[0-2])/(\d{4})$")


class SubscriptionIpcMonthly(models.Model):
    """Stores the monthly IPC percentage used for subscription updates."""

    _name = "subscription.ipc.monthly"
    _description = "Subscription Monthly IPC"
    _order = "period_year desc, period_month desc"
    _rec_name = "period"

    period = fields.Char(
        string="Período",
        required=True,
        help="Formato MM/AAAA. Ejemplo: 01/2026.",
    )
    percentage = fields.Float(
        string="Porcentaje IPC",
        required=True,
        digits="Subscription IPC Percentage",
    )
    period_month = fields.Integer(
        string="Mes",
        compute="_compute_period_parts",
        store=True,
        index=True,
    )
    period_year = fields.Integer(
        string="Año",
        compute="_compute_period_parts",
        store=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            "subscription_ipc_monthly_period_unique",
            "unique(period)",
            "Ya existe un registro para ese período.",
        )
    ]

    @api.depends("period")
    def _compute_period_parts(self) -> None:
        """Compute numeric year/month to keep reliable chronological ordering."""
        for record in self:
            record.period_month = False
            record.period_year = False
            normalized_period = record._normalize_period(record.period)
            if normalized_period:
                month, year = normalized_period.split("/")
                record.period_month = int(month)
                record.period_year = int(year)

    @api.constrains("period")
    def _check_period(self) -> None:
        """Ensure period always follows MM/YYYY and maps to a valid month/year."""
        for record in self:
            if not record._normalize_period(record.period):
                raise ValidationError(
                    _(
                        "El período debe tener formato MM/AAAA. "
                        "Ejemplo: 01/2026."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Normalize period before creating records to avoid duplicate variants."""
        for vals in vals_list:
            if "period" in vals:
                vals["period"] = self._normalize_period_or_raise(vals["period"])
        return super().create(vals_list)

    def write(self, vals):
        """Normalize period on updates to keep consistent stored representation."""
        if "period" in vals:
            vals["period"] = self._normalize_period_or_raise(vals["period"])
        return super().write(vals)

    @api.model
    def _normalize_period_or_raise(self, period):
        """Return canonical MM/YYYY value or raise a validation error."""
        normalized_period = self._normalize_period(period)
        if not normalized_period:
            raise ValidationError(
                _(
                    "El período debe tener formato MM/AAAA. "
                    "Ejemplo: 01/2026."
                )
            )
        return normalized_period

    @api.model
    def _normalize_period(self, period):
        """Normalize text period input and validate month/year values."""
        if not period:
            return False

        raw_period = str(period).strip()
        match = PERIOD_PATTERN.match(raw_period)
        if not match:
            return False

        month_text, year_text = match.groups()
        month = int(month_text)
        year = int(year_text)
        try:
            date(year, month, 1)
        except ValueError:
            return False
        return f"{month:02d}/{year:04d}"
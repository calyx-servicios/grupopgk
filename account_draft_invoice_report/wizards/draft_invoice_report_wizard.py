from datetime import date as py_date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountDraftInvoiceReportWizard(models.TransientModel):
    _name = "account.draft.invoice.report.wizard"
    _description = "Facturación Pendiente (Borradores) Report Wizard"

    company_ids = fields.Many2many(
        "res.company",
        string="Compañías",
        default=lambda self: self.env.user.company_ids,
        domain=lambda self: [("id", "in", self.env.user.company_ids.ids)],
        required=True,
    )
    date_from = fields.Date(
        string="Fecha Desde",
        required=True,
        default=lambda self: self._default_date_from(),
    )
    date_to = fields.Date(
        string="Fecha Hasta",
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )

    @api.model
    def _default_date_from(self):
        today = fields.Date.context_today(self)
        return py_date(today.year, 1, 1)

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("La Fecha Desde no puede ser posterior a la Fecha Hasta."))

    @api.constrains("company_ids")
    def _check_company_ids(self):
        for wizard in self:
            if not wizard.company_ids:
                raise ValidationError(_("Debe seleccionar al menos una compañía."))
            if wizard.company_ids - self.env.user.company_ids:
                raise ValidationError(
                    _("No puede seleccionar compañías fuera de su contexto permitido.")
                )

    def _get_company_ids(self):
        self.ensure_one()
        return self.company_ids

    def _get_move_domain(self):
        self.ensure_one()
        return [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "draft"),
            ("company_id", "in", self._get_company_ids().ids),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]

    def _get_subscription_name(self, move, sale_order):
        subscription = False
        if "subscription_id" in move._fields:
            subscription = move.subscription_id
        if not subscription and sale_order and "subscription_id" in sale_order._fields:
            subscription = sale_order.subscription_id
        if not subscription:
            return ""
        return (
            getattr(subscription, "reference_code", False)
            or getattr(subscription, "name", False)
            or ""
        )

    def _get_sale_orders_by_origin(self, moves):
        origins = set()
        for origin in moves.mapped("invoice_origin"):
            if not origin:
                continue
            origins.update(part.strip() for part in origin.split(",") if part.strip())
        if not origins:
            return {}
        sale_orders = self.env["sale.order"].search(
            [
                ("name", "in", list(origins)),
                ("company_id", "in", self._get_company_ids().ids),
            ]
        )
        return {order.name: order for order in sale_orders}

    def _get_move_sale_orders(self, move, sale_orders_by_origin):
        sale_orders = self.env["sale.order"]
        if move.invoice_origin:
            for origin in move.invoice_origin.split(","):
                sale_order = sale_orders_by_origin.get(origin.strip())
                if sale_order:
                    sale_orders |= sale_order
        if "sale_line_ids" in self.env["account.move.line"]._fields:
            sale_orders |= move.invoice_line_ids.mapped("sale_line_ids.order_id")
        return sale_orders.filtered(lambda order: order.company_id in self._get_company_ids())

    def _get_document_sort_key(self, document):
        return (document["invoice_date"] or py_date.min, document["move"].id)

    def _get_client_sort_key(self, client):
        first_date = min(
            (document["invoice_date"] or py_date.min for document in client["documents"]),
            default=py_date.min,
        )
        return (first_date, client["name"])

    def _prepare_report_data(self):
        self.ensure_one()
        moves = self.env["account.move"].search(
            self._get_move_domain(),
            order="company_id, partner_id, invoice_date, id",
        )
        sale_orders_by_origin = self._get_sale_orders_by_origin(moves)
        companies = {}
        for move in moves:
            sale_orders = self._get_move_sale_orders(move, sale_orders_by_origin)
            sale_order = sale_orders[:1]
            company_data = companies.setdefault(
                move.company_id.id,
                {
                    "name": move.company_id.name,
                    "clients": {},
                    "totals": {},
                },
            )
            partner_key = move.partner_id.id or 0
            client_data = company_data["clients"].setdefault(
                partner_key,
                {"name": move.partner_id.name or "Sin cliente", "documents": [], "totals": {}},
            )
            currency = move.currency_id
            amount_total = move.amount_total
            client_data["documents"].append(
                {
                    "move": move,
                    "number": (
                        move.name
                        if move.name and move.name != "/"
                        else move.ref or _("Borrador")
                    ),
                    "client": move.partner_id.name or "",
                    "invoice_date": move.invoice_date,
                    "company": move.company_id.name,
                    "sale_order": ", ".join(sale_orders.mapped("name")),
                    "subscription": self._get_subscription_name(move, sale_order),
                    "amount_untaxed": move.amount_untaxed,
                    "amount_total": amount_total,
                    "foreign_total": (
                        amount_total if currency != move.company_id.currency_id else False
                    ),
                    "currency": currency,
                    "document_type": (
                        "Nota de crédito" if move.move_type == "out_refund" else "Factura"
                    ),
                    "observations": move.narration or "",
                }
            )
            for totals in (client_data["totals"], company_data["totals"]):
                currency_totals = totals.setdefault(currency.id, {"currency": currency, "untaxed": 0.0, "total": 0.0})
                currency_totals["untaxed"] += move.amount_untaxed
                currency_totals["total"] += amount_total

        general_totals = {}
        for company in companies.values():
            for currency_id, totals in company["totals"].items():
                general = general_totals.setdefault(
                    currency_id,
                    {"currency": totals["currency"], "untaxed": 0.0, "total": 0.0},
                )
                general["untaxed"] += totals["untaxed"]
                general["total"] += totals["total"]
            for client in company["clients"].values():
                client["documents"].sort(key=self._get_document_sort_key)

        return {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "companies_label": ", ".join(
                company["name"] for company in companies.values()
            ),
            "companies": sorted(
                [
                    dict(
                        company,
                        clients=sorted(
                            company["clients"].values(), key=self._get_client_sort_key
                        ),
                    )
                    for company in companies.values()
                ],
                key=lambda company: company["name"],
            ),
            "totals": list(general_totals.values()),
        }

    def action_generate_report(self):
        self.ensure_one()
        self._check_date_range()
        self._check_company_ids()
        return self.env.ref(
            "account_draft_invoice_report.action_draft_invoice_report"
        ).report_action(self)

from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountDraftInvoiceReportWizard(models.TransientModel):
    _name = "account.draft.invoice.report.wizard"
    _description = "Facturación Pendiente (Borradores) Report Wizard"

    multi_company = fields.Boolean(
        default=lambda self: len(self.env.user.company_ids) > 1,
    )
    all_companies = fields.Boolean(
        string="Todas",
        default=True,
    )
    company_ids = fields.Many2many(
        "res.company",
        string="Compañías",
        domain=lambda self: [("id", "in", self.env.user.company_ids.ids)],
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
        return date(today.year, 1, 1)

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("La Fecha Desde no puede ser posterior a la Fecha Hasta."))

    @api.constrains("all_companies", "company_ids")
    def _check_company_ids(self):
        for wizard in self:
            if not wizard.all_companies and not wizard.company_ids:
                raise ValidationError(_("Debe seleccionar al menos una compañía."))
            if wizard.company_ids - self.env.user.company_ids:
                raise ValidationError(
                    _("No puede seleccionar compañías fuera de su contexto permitido.")
                )

    def _get_company_ids(self):
        self.ensure_one()
        return self.company_ids if not self.all_companies else self.env.user.company_ids

    def _get_move_domain(self):
        self.ensure_one()
        return [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "draft"),
            ("company_id", "in", self._get_company_ids().ids),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]

    def action_generate_report(self):
        self.ensure_one()
        self._check_date_range()
        self._check_company_ids()
        company_ids = self._get_company_ids().ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Facturación Pendiente (Borradores)"),
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": self._get_move_domain(),
            "context": {
                "allowed_company_ids": company_ids,
                "default_move_type": "out_invoice",
            },
        }

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from .quoter_complexity_source import COMPANY_SIZE_SELECTION

# Campos del bloque que alimentan el nivel calculado.
QUOTER_DERIVED_LEVEL_INPUTS = frozenset({"labor_agreement_ids", "area_id"})

# Campos de la cotización que alimentan el tamaño de empresa (Tax / Auditoría).
QUOTER_COMPANY_SIZE_INPUTS = frozenset({"quoter_prev_year_revenue", "quoter_industry_id"})


class QuoterSaleOrderAreaComplexity(models.Model):
    _inherit = "quoter.sale.order.area"

    area_complexity_source = fields.Selection(
        related="area_id.complexity_source",
        readonly=True,
    )
    labor_agreement_ids = fields.Many2many(
        comodel_name="quoter.labor.agreement",
        relation="quoter_sale_order_area_labor_agreement_rel",
        column1="block_id",
        column2="agreement_id",
        string="Convenios colectivos",
        help="Convenios del cliente; definen el nivel de complejidad del área.",
    )
    # La facturación y la industria son únicas por cotización: se cargan en la cabecera.
    company_size = fields.Selection(
        related="order_id.quoter_company_size",
        string="Tamaño de empresa",
    )

    def _quoter_derived_complexity_level(self):
        """Nivel según los datos del bloque; vacío si el área es manual o faltan datos."""
        self.ensure_one()
        area = self.area_id
        level = self.env["quoter.complexity.level"]
        if not area:
            return level
        if area.complexity_source == "labor_agreement":
            return area._quoter_level_for_labor_agreements(self.labor_agreement_ids)
        if area.complexity_source == "company_size" and self.company_size:
            return area._quoter_level_for_company_size(self.company_size)
        return level

    def _quoter_derived_branch(self):
        """Rama de la industria si el área cotiza por rama (Auditoría)."""
        self.ensure_one()
        branch = self.order_id.quoter_industry_id.branch_id
        if (
            branch
            and self.area_id.complexity_source == "company_size"
            and branch in self.area_id.branch_ids
        ):
            return branch
        return self.env["quoter.area.branch"]

    def _quoter_apply_derived_complexity_level(self):
        """Escribe el nivel calculado por el camino normal (resincroniza líneas y horas).

        Devuelve los bloques cuyo nivel cambió.
        """
        changed = self.browse()
        for rec in self:
            if rec.area_complexity_source in (False, "manual"):
                continue
            order = rec.order_id
            if not order or not order.is_quotation or rec.state not in (False, "draft"):
                continue
            vals = {}
            level = rec._quoter_derived_complexity_level()
            if level and level != rec.complexity_level_id:
                vals["complexity_level_id"] = level.id
            branch = rec._quoter_derived_branch()
            if branch and branch != rec.branch_id:
                vals["branch_id"] = branch.id
            if vals:
                # Nivel y rama juntos: la resincronización de horas usa ambos.
                rec.with_context(quoter_derived_complexity_level=True).write(vals)
                if "complexity_level_id" in vals:
                    changed |= rec
        return changed

    @api.onchange("labor_agreement_ids")
    def _onchange_quoter_derived_complexity_level(self):
        """Vista previa en el formulario; al guardar se recalcula en servidor."""
        for rec in self:
            if rec.area_complexity_source in (False, "manual"):
                continue
            level = rec._quoter_derived_complexity_level()
            if level and level != rec.complexity_level_id:
                rec.complexity_level_id = level
            branch = rec._quoter_derived_branch()
            if branch and branch != rec.branch_id:
                rec.branch_id = branch

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._quoter_apply_derived_complexity_level()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("quoter_derived_complexity_level") and (
            QUOTER_DERIVED_LEVEL_INPUTS | {"complexity_level_id", "branch_id"}
        ) & set(vals):
            self._quoter_apply_derived_complexity_level()
        return res


class SaleOrderQuoterComplexity(models.Model):
    _inherit = "sale.order"

    quoter_prev_year_revenue = fields.Float(
        string="Facturación año anterior (ARS)",
        digits=(16, 2),
        tracking=True,
        help="Junto con la industria define el tamaño de empresa y, con él, el nivel "
        "de las áreas que lo calculan por tamaño (Tax, Auditoría).",
    )
    quoter_industry_id = fields.Many2one(
        comodel_name="quoter.industry",
        string="Industria",
        ondelete="restrict",
        tracking=True,
    )
    quoter_company_size = fields.Selection(
        selection=COMPANY_SIZE_SELECTION,
        string="Tamaño de empresa",
        compute="_compute_quoter_company_size",
        store=True,
    )
    quoter_company_size_inputs_required = fields.Boolean(
        string="Facturación e industria obligatorias",
        compute="_compute_quoter_company_size_inputs_required",
        help="Alguna de las áreas de la cotización calcula el nivel por tamaño de empresa.",
    )

    @api.depends(
        "quoter_prev_year_revenue",
        "quoter_industry_id",
        "quoter_industry_id.threshold_ids.date_from",
        "quoter_industry_id.threshold_ids.micro_max",
        "quoter_industry_id.threshold_ids.small_max",
        "quoter_industry_id.threshold_ids.medium_max",
        "date_order",
    )
    def _compute_quoter_company_size(self):
        for order in self:
            if not order.quoter_industry_id:
                order.quoter_company_size = False
                continue
            order.quoter_company_size = order.quoter_industry_id._quoter_company_size(
                order.quoter_prev_year_revenue, order._quoter_company_size_date()
            )

    @api.depends(
        "is_quotation",
        "quoter_area_ids.complexity_source",
        "quoter_area_block_ids.state",
    )
    def _compute_quoter_company_size_inputs_required(self):
        for order in self:
            cancelled = order.quoter_area_block_ids.filtered(
                lambda b: b.state == "cancel"
            ).mapped("area_id")
            areas = order.quoter_area_ids - cancelled
            order.quoter_company_size_inputs_required = bool(
                order.is_quotation
                and any(a.complexity_source == "company_size" for a in areas)
            )

    def _quoter_company_size_date(self):
        self.ensure_one()
        return (
            self.date_order.date()
            if self.date_order
            else fields.Date.context_today(self)
        )

    def _quoter_check_company_size_inputs_change(self, vals):
        """No cambiar facturación ni industria con bloques cerrados que dependen de ellas.

        Solo se recalcula el nivel de los bloques abiertos: un bloque cerrado quedaría con
        el nivel de los datos anteriores.
        """
        for order in self.filtered("is_quotation"):
            changed = False
            if "quoter_industry_id" in vals:
                changed = order.quoter_industry_id.id != (vals["quoter_industry_id"] or False)
            if not changed and "quoter_prev_year_revenue" in vals:
                changed = bool(
                    float_compare(
                        order.quoter_prev_year_revenue,
                        vals["quoter_prev_year_revenue"] or 0.0,
                        precision_digits=2,
                    )
                )
            if not changed:
                continue
            closed = order.quoter_area_block_ids.filtered(
                lambda b: b.state == "published"
                and b.area_complexity_source == "company_size"
            )
            if closed:
                raise UserError(
                    _(
                        "Para cambiar la facturación o la industria reabra antes los bloques "
                        "cerrados que calculan el nivel con esos datos: %s."
                    )
                    % ", ".join(closed.mapped("area_id.display_name"))
                )

    def write(self, vals):
        if QUOTER_COMPANY_SIZE_INPUTS & set(vals):
            self._quoter_check_company_size_inputs_change(vals)
        res = super().write(vals)
        # Los topes SICYPYME dependen de la fecha de la cotización.
        if (QUOTER_COMPANY_SIZE_INPUTS | {"date_order"}) & set(vals):
            self.mapped("quoter_area_block_ids")._quoter_apply_derived_complexity_level()
        return res

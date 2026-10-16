# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import api, fields, models

from .quoter_complexity_source import COMPANY_SIZE_SELECTION

# Campos del bloque que alimentan el nivel calculado.
QUOTER_DERIVED_LEVEL_INPUTS = frozenset(
    {"labor_agreement_ids", "prev_year_revenue", "industry_id", "area_id"}
)


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
    prev_year_revenue = fields.Float(
        string="Facturación año anterior (ARS)",
        digits=(16, 2),
    )
    industry_id = fields.Many2one(
        comodel_name="quoter.industry",
        string="Industria",
        ondelete="restrict",
    )
    company_size = fields.Selection(
        selection=COMPANY_SIZE_SELECTION,
        string="Tamaño de empresa",
        compute="_compute_company_size",
        store=True,
    )
    company_size_inputs_required = fields.Boolean(
        string="Facturación e industria obligatorias",
        compute="_compute_company_size_inputs_required",
    )

    @api.depends(
        "prev_year_revenue",
        "industry_id",
        "industry_id.threshold_ids.date_from",
        "industry_id.threshold_ids.micro_max",
        "industry_id.threshold_ids.small_max",
        "industry_id.threshold_ids.medium_max",
        "order_id.date_order",
    )
    def _compute_company_size(self):
        for rec in self:
            if not rec.industry_id:
                rec.company_size = False
                continue
            rec.company_size = rec.industry_id._quoter_company_size(
                rec.prev_year_revenue, rec._quoter_company_size_date()
            )

    @api.depends("area_complexity_source", "manager_required")
    def _compute_company_size_inputs_required(self):
        for rec in self:
            rec.company_size_inputs_required = bool(
                rec.area_complexity_source == "company_size" and rec.manager_required
            )

    def _quoter_company_size_date(self):
        self.ensure_one()
        date_order = self.order_id.date_order if self.order_id else False
        return date_order.date() if date_order else fields.Date.context_today(self)

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
        branch = self.industry_id.branch_id
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

    @api.onchange("labor_agreement_ids", "prev_year_revenue", "industry_id")
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

    def write(self, vals):
        res = super().write(vals)
        if "date_order" in vals:
            # Los topes SICYPYME dependen de la fecha de la cotización.
            self.mapped("quoter_area_block_ids")._quoter_apply_derived_complexity_level()
        return res

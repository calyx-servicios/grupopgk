# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import api, fields, models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel cotizador",
        ondelete="set null",
        index=True,
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _quoter_default_sale_tax_ids_for_company(self, company):
        """Impuesto de venta con alícuota 0%% (p. ej. IVA no gravado AR)."""
        if not company or "account.tax" not in self.env:
            return []
        Tax = self.env["account.tax"].sudo()
        domain = [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("active", "=", True),
            ("amount_type", "=", "percent"),
            ("amount", "=", 0),
        ]
        candidates = Tax.search(domain)
        if not candidates:
            return []
        prefer = candidates.filtered(
            lambda t: any(
                x in (t.name or "").lower()
                for x in ("no grav", "no gravado", "no grav.", "exento", "0%")
            )
        )
        chosen = prefer[:1] or candidates[:1]
        return chosen.ids

    @api.model
    def quoter_apply_default_sale_taxes(self, templates):
        """Asigna impuesto de venta 0%% a plantillas generadas por el cotizador."""
        for tmpl in templates:
            if not tmpl:
                continue
            company = tmpl.company_id or self.env.company
            tax_ids = self._quoter_default_sale_tax_ids_for_company(company)
            if tax_ids:
                tmpl.write({"taxes_id": [(6, 0, tax_ids)]})

    is_quoter_product = fields.Boolean(
        string="Producto del cotizador",
        index=True,
        help="Generado automáticamente por el módulo Quoter; no suele editarse a mano.",
    )

    quoter_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área cotizador",
        ondelete="set null",
        copy=False,
    )

    quoter_service_line_id = fields.Many2one(
        comodel_name="quoter.service.line",
        string="Línea de servicio cotizador",
        ondelete="set null",
        copy=False,
    )
    is_default_quoter_product = fields.Boolean(
        string="Producto predeterminado",
        default=False,
        index=True,
        help="Identifica el producto plantilla predeterminado para usar en venta.",
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_quoter_product = fields.Boolean(
        related="product_tmpl_id.is_quoter_product", store=True, readonly=True
    )
    quoter_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área cotizador",
        related="product_tmpl_id.quoter_area_id",
        store=True,
        readonly=True,
        index=True,
    )
    complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel de complejidad",
        compute="_compute_complexity_level_id",
        store=True,
        index=True,
        readonly=True,
    )
    is_default_quoter_product = fields.Boolean(
        related="product_tmpl_id.is_default_quoter_product",
        store=True,
        readonly=False,
        index=True,
        help="Marca heredada desde el producto plantilla.",
    )
    related_variant_ids = fields.Many2many(
        comodel_name="product.product",
        string="Variantes relacionadas",
        compute="_compute_related_variant_ids",
        help="Resto de variantes del mismo producto plantilla.",
    )

    @api.depends(
        "product_template_attribute_value_ids.product_attribute_value_id.complexity_level_id"
    )
    def _compute_complexity_level_id(self):
        for rec in self:
            levels = rec.mapped(
                "product_template_attribute_value_ids.product_attribute_value_id.complexity_level_id"
            )
            rec.complexity_level_id = levels[:1]

    @api.depends("product_tmpl_id", "product_tmpl_id.product_variant_ids")
    def _compute_related_variant_ids(self):
        for rec in self:
            rec.related_variant_ids = rec.product_tmpl_id.product_variant_ids.filtered(
                lambda v: v.id != rec.id
            )

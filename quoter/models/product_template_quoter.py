# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
    def quoter_create_generic_product(self, name):
        """Crea un producto genérico del cotizador (catálogo reutilizable entre áreas)."""
        general_categ = self.env.ref("quoter.product_category_quoter_general", raise_if_not_found=False)
        if not general_categ:
            raise UserError(_("No está configurada la categoría General (Cotizador)."))
        name = (name or "").strip()
        if not name:
            raise UserError(_("Indique un nombre para el producto."))
        if self.search(
            [("is_quoter_generic_product", "=", True), ("name", "=", name)], limit=1
        ):
            raise UserError(_("Ya existe un producto genérico con ese nombre."))
        uom_unit = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        tmpl_vals = {
            "name": name,
            "type": "service",
            "sale_ok": True,
            "purchase_ok": False,
            "default_code": "QR-G-%s" % (name[:40].replace(" ", "-") or "GEN"),
            "is_quoter_product": True,
            "is_quoter_generic_product": True,
            "quoter_area_id": False,
            "quoter_service_line_id": False,
            "categ_id": general_categ.id,
        }
        if uom_unit:
            tmpl_vals["uom_id"] = uom_unit.id
            tmpl_vals["uom_po_id"] = uom_unit.id
        tmpl = self.create(tmpl_vals)
        self.quoter_apply_default_sale_taxes(tmpl)
        return tmpl

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
    is_quoter_generic_product = fields.Boolean(
        string="Producto genérico del cotizador",
        index=True,
        help="Producto reutilizable en cualquier área (categoría General del cotizador).",
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

    @api.model
    def _quoter_product_ids_for_area_picker(self, area, order, exclude_line_id=None):
        """Productos del área aún no usados en otra línea de la misma cotización."""
        if not area or not order:
            return []
        QuoterLine = self.env["quoter.service.line"]
        products = (
            QuoterLine.search([("area_id", "=", area.id)])
            .mapped("product_id")
            .filtered(
                lambda p: p
                and p.sale_ok
                and not getattr(p, "is_quoter_range_rate_product", False)
            )
        )
        area_lines = order.order_line.filtered(
            lambda l, a=area: l.quoter_tab_area_id == a
            and not l.display_type
            and l.product_id
            and not l.quoter_is_area_discount_total_line
        )
        if exclude_line_id and isinstance(exclude_line_id, int):
            used = area_lines.filtered(lambda l, eid=exclude_line_id: l.id != eid).mapped(
                "product_id"
            )
        else:
            used = area_lines.mapped("product_id")
        return (products - used).ids

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = list(args or [])
        ctx = self.env.context
        if ctx.get("quoter_product_picker"):
            area = self.env["quoter.professional.area"].browse(ctx.get("quoter_area_id"))
            order = self.env["sale.order"].browse(ctx.get("quoter_order_id"))
            exclude_line_id = ctx.get("quoter_exclude_line_id")
            if area and order:
                ids = self._quoter_product_ids_for_area_picker(
                    area, order, exclude_line_id=exclude_line_id
                )
                args.append(("id", "in", ids or [0]))
        return super().name_search(name, args, operator, limit)

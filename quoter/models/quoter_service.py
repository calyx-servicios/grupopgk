# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class QuoterServiceLineRangeHour(models.Model):
    _name = "quoter.service.line.range.hour"
    _description = "Horas de una línea por rango del área"
    _order = "area_range_sequence, id"

    line_id = fields.Many2one(
        comodel_name="quoter.service.line",
        string="Línea de servicio",
        required=True,
        ondelete="cascade",
    )

    area_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rango del área",
        required=True,
        ondelete="cascade",
        index=True,
    )

    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )

    hours = fields.Float(string="Horas", default=0.0)

    _sql_constraints = [
        (
            "uniq_line_area_range",
            "UNIQUE(line_id, area_range_id)",
            "Ya hay horas cargadas para ese rango en esta línea.",
        )
    ]

    @api.constrains("area_range_id", "line_id")
    def _check_range_belongs_to_line_area(self):
        for row in self:
            area = row.line_id.area_id
            if not area or not row.area_range_id:
                continue
            if row.area_range_id not in area.area_range_ids:
                raise ValidationError(
                    _("El rango debe pertenecer a los rangos configurados en el área de la línea.")
                )


class QuoterServiceLine(models.Model):
    _name = "quoter.service.line"
    _description = "Línea de producto del cotizador (un producto por línea)"
    _order = "sequence, id"

    active = fields.Boolean(default=True)

    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer(default=10)

    name = fields.Char(
        string="Nombre",
        required=True,
        translate=True,
        help="Nombre del producto y variantes generados para esta línea.",
    )

    separator_tag_id = fields.Many2one(
        comodel_name="quoter.line.separator.tag",
        string="Etiqueta separadora",
        ondelete="set null",
        help="Para agrupar en vistas del pedido (se usará como separador entre líneas).",
    )
    is_default_product = fields.Boolean(
        string="Producto predeterminado",
        default=False,
        help="Marca este producto como opción predeterminada para usar en ventas.",
    )

    manual_load = fields.Boolean(
        string="Carga manual",
        default=False,
        help="Indica que las horas de esta línea se cargan manualmente (p. ej. en pedido). "
        "La aplicación en sale.order se puede enlazar después; conceptualmente similar a rangos unificados.",
    )

    range_hour_ids = fields.One2many(
        comodel_name="quoter.service.line.range.hour",
        inverse_name="line_id",
        string="Horas por rango del área",
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Variante predeterminada",
        readonly=True,
        copy=False,
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Producto",
        readonly=True,
        copy=False,
    )

    def _sync_range_hour_lines(self):
        """Filas de horas alineadas con los rangos definidos en el área."""
        Hour = self.env["quoter.service.line.range.hour"]
        for line in self:
            ranges = line.area_id.area_range_ids
            if not ranges:
                line.range_hour_ids.unlink()
                continue
            keep_ids = set(ranges.ids)
            line.range_hour_ids.filtered(
                lambda h: h.area_range_id.id not in keep_ids
            ).unlink()
            existing = set(line.range_hour_ids.mapped("area_range_id").ids)
            for ar in ranges.sorted(key=lambda r: (r.sequence, r.id)):
                if ar.id not in existing:
                    Hour.create(
                        {
                            "line_id": line.id,
                            "area_range_id": ar.id,
                            "hours": 0.0,
                        }
                    )

    def _sync_product_level_ranges(self):
        """Crear filas quoter.product.level.range por nivel del área (sin borrar)."""
        LevelRange = self.env["quoter.product.level.range"]
        for line in self:
            tmpl = line.product_tmpl_id or (line.product_id and line.product_id.product_tmpl_id)
            area = line.area_id
            if not tmpl or not area:
                continue
            levels = area._complexity_levels_ordered()
            if not levels:
                continue
            existing = LevelRange.search(
                [("product_tmpl_id", "=", tmpl.id), ("complexity_level_id", "in", levels.ids)]
            ).mapped("complexity_level_id")
            missing = levels - existing
            if not missing:
                continue
            for lev in missing:
                LevelRange.create(
                    {
                        "product_tmpl_id": tmpl.id,
                        "complexity_level_id": lev.id,
                    }
                )

    def _service_title(self):
        self.ensure_one()
        if not self.area_id:
            return ""
        return _("Servicio profesional %s") % (self.area_id.name,)

    def _sync_default_product_flag(self):
        for line in self:
            tmpl = line.product_tmpl_id or line.product_id.product_tmpl_id
            if tmpl:
                tmpl.is_default_quoter_product = line.is_default_product

    def _sync_product_template_link(self):
        for line in self:
            tmpl = line.product_id.product_tmpl_id if line.product_id else False
            super(QuoterServiceLine, line).write(
                {"product_tmpl_id": tmpl.id if tmpl else False}
            )

    def _get_quoter_product_template_name(self):
        self.ensure_one()
        return f"{self._service_title()} · {self.name}"

    def _quoter_product_internal_ref(self):
        self.ensure_one()
        return f"QR-A{self.area_id.id}-L{self.id}"

    def _normalize_single_variant_product(self):
        """Garantiza una sola variante seleccionable por línea de servicio."""
        self.ensure_one()
        line = self
        tmpl = line.product_tmpl_id or (line.product_id and line.product_id.product_tmpl_id)
        if not tmpl:
            return
        attr = self.env["product.attribute"]
        try:
            attr = self.env.ref("quoter.product_attribute_quoter_nivel")
        except ValueError:
            attr = self.env["product.attribute"].search(
                [("name", "=ilike", "Nivel cotización")], limit=1
            )
        if attr:
            tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id == attr).unlink()
        tmpl._create_variant_ids()
        variants = tmpl.with_context(active_test=False).product_variant_ids.sorted(key=lambda v: v.id)
        if not variants:
            return
        chosen = variants[:1]
        if line.product_id != chosen:
            super(QuoterServiceLine, line).write({"product_id": chosen.id})
        extra = variants - chosen
        if extra:
            extra.write({"active": False})

    def _ensure_quoter_product_simple(self):
        self.ensure_one()
        line = self
        if not line.area_id:
            return
        Template = self.env["product.template"]
        name = line._get_quoter_product_template_name()
        default_code = line._quoter_product_internal_ref()
        if line.product_id:
            tmpl = line.product_id.product_tmpl_id
            vals = {
                "name": name,
                "default_code": default_code,
                "quoter_area_id": line.area_id.id,
                "quoter_service_line_id": line.id,
            }
            if line.area_id.product_category_id:
                vals["categ_id"] = line.area_id.product_category_id.id
            tmpl.write(
                vals
            )
            super(QuoterServiceLine, line).write({"product_tmpl_id": tmpl.id})
            line._sync_default_product_flag()
            return
        uom_unit = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        tmpl_vals = {
            "name": name,
            "type": "service",
            "sale_ok": True,
            "purchase_ok": False,
            "default_code": default_code,
            "is_quoter_product": True,
            "quoter_area_id": line.area_id.id,
            "quoter_service_line_id": line.id,
        }
        if line.area_id.product_category_id:
            tmpl_vals["categ_id"] = line.area_id.product_category_id.id
        if uom_unit:
            tmpl_vals["uom_id"] = uom_unit.id
            tmpl_vals["uom_po_id"] = uom_unit.id
        tmpl = Template.create(tmpl_vals)
        Template.quoter_apply_default_sale_taxes(tmpl)
        variant = tmpl.product_variant_ids[:1]
        if not variant:
            return
        super(QuoterServiceLine, line).write({"product_id": variant.id})
        super(QuoterServiceLine, line).write({"product_tmpl_id": tmpl.id})
        line._sync_default_product_flag()

    def _ensure_quoter_product(self):
        for line in self:
            if not line.area_id:
                continue
            # Producto base del cotizador: solo una variante seleccionable.
            line._ensure_quoter_product_simple()
            line._normalize_single_variant_product()
            line._sync_service_line_primary_variant()

    def _sync_service_line_primary_variant(self):
        """Deja product_id en la única variante canónica del template."""
        for line in self:
            tmpl = line.product_tmpl_id or (line.product_id and line.product_id.product_tmpl_id)
            if not tmpl:
                continue
            variants = tmpl.with_context(active_test=False).product_variant_ids.sorted(key=lambda v: v.id)
            if not variants:
                continue
            chosen = variants[:1]
            if chosen and line.product_id != chosen:
                super(QuoterServiceLine, line).write({"product_id": chosen.id})

    def _unlink_quoter_product_template(self):
        for line in self:
            if not line.product_id and not line.product_tmpl_id:
                continue
            tmpl = line.product_tmpl_id or line.product_id.product_tmpl_id
            super(QuoterServiceLine, line).write(
                {"product_id": False, "product_tmpl_id": False}
            )
            if tmpl.exists() and tmpl.is_quoter_product:
                tmpl.unlink()

    def _quoter_notify_sale_orders_selectable_products(self):
        areas = self.mapped("area_id")
        if not areas:
            return
        orders = self.env["sale.order"].search([("quoter_area_ids", "in", areas.ids)])
        if orders:
            orders._quoter_refresh_selectable_products()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sync_range_hour_lines()
        lines._ensure_quoter_product()
        lines._sync_product_level_ranges()
        lines._sync_product_template_link()
        lines._sync_default_product_flag()
        lines._quoter_notify_sale_orders_selectable_products()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("quoter_skip_line_product_resync"):
            return res
        if "area_id" in vals:
            self._sync_range_hour_lines()
        if {"name", "area_id"} & set(vals.keys()):
            self._ensure_quoter_product()
            self._sync_product_level_ranges()
        if "is_default_product" in vals:
            self._sync_default_product_flag()
        if "product_id" in vals:
            self._sync_product_template_link()
        self._quoter_notify_sale_orders_selectable_products()
        return res

    def unlink(self):
        areas = self.mapped("area_id")
        self._unlink_quoter_product_template()
        res = super().unlink()
        if areas:
            orders = self.env["sale.order"].search([("quoter_area_ids", "in", areas.ids)])
            if orders:
                orders._quoter_refresh_selectable_products()
        return res

    def action_open_product_variant(self):
        self.ensure_one()
        if not self.product_id and not self.product_tmpl_id:
            self._ensure_quoter_product()
        tmpl = self.product_tmpl_id or self.product_id.product_tmpl_id
        if not tmpl:
            raise UserError(_("No se pudo generar el producto para esta línea."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Producto"),
            "res_model": "product.template",
            "view_mode": "form",
            "res_id": tmpl.id,
            "target": "current",
        }

    def action_open_level_ranges(self):
        self.ensure_one()
        if not self.product_id and not self.product_tmpl_id:
            self._ensure_quoter_product()
        tmpl = self.product_tmpl_id or self.product_id.product_tmpl_id
        if not tmpl:
            raise UserError(_("No se pudo generar el producto para esta línea."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Horas por nivel (rangos del área)"),
            "res_model": "quoter.product.level.range",
            "view_mode": "tree,form",
            "domain": [("product_tmpl_id", "=", tmpl.id)],
            "context": dict(self.env.context, default_product_tmpl_id=tmpl.id),
            "target": "current",
        }

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def read(self, fields=None, load="_classic_read"):
        """Evita MissingError cuando el formulario web pide líneas ya borradas (p. ej. tras unlink en bloque)."""
        return super(SaleOrderLine, self.exists()).read(fields=fields, load=load)

    def _quoter_range_hour_sudo(self):
        """ACL de horas por rango: lectura para vendedores; escritura técnica vía sudo en sincronización."""
        return self.env["sale.order.line.range.hour"].sudo()

    @staticmethod
    def _quoter_force_qty_one_in_vals(vals):
        if not vals or vals.get("display_type"):
            return
        vals["product_uom_qty"] = 1.0

    @staticmethod
    def _quoter_ensure_accountable_required_fields(vals, product):
        """Completa mínimos para evitar check SQL sale_order_line_accountable_required_fields."""
        if not vals or vals.get("display_type") or not product:
            return
        vals.setdefault("product_id", product.id)
        vals.setdefault("product_uom_qty", 1.0)
        if not vals.get("product_uom"):
            vals["product_uom"] = product.uom_id.id
        if not vals.get("name"):
            vals["name"] = (
                product.get_product_multiline_description_sale() or product.display_name
            )

    quoter_is_adjustment_line = fields.Boolean(
        string="Es ajuste",
        default=False,
        copy=False,
        index=True,
    )
    quoter_adjustment_parent_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Línea base de ajuste",
        copy=False,
        ondelete="cascade",
        index=True,
    )
    quoter_adjustment_child_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="quoter_adjustment_parent_line_id",
        string="Líneas de ajuste",
        readonly=True,
    )
    quoter_has_adjustment_line = fields.Boolean(
        string="Tiene ajuste",
        compute="_compute_quoter_has_adjustment_line",
        store=False,
    )
    quoter_adjustment_status = fields.Char(
        string="Estado ajuste",
        compute="_compute_quoter_has_adjustment_line",
        store=False,
    )
    quoter_adjustment_note = fields.Char(
        string="Observación ajuste",
        copy=False,
        help="Justificación obligatoria para líneas de ajuste.",
    )
    quoter_is_area_discount_total_line = fields.Boolean(
        string="Línea total descuento/recargo áreas",
        default=False,
        copy=False,
        index=True,
    )
    quoter_separator_tag_id = fields.Many2one(
        comodel_name="quoter.line.separator.tag",
        string="Sección de cotizador",
        related="product_id.product_tmpl_id.quoter_service_line_id.separator_tag_id",
        store=True,
        readonly=True,
    )
    quoter_product_separator_tag_color = fields.Integer(
        string="Color sección (producto)",
        related="quoter_separator_tag_id.color",
        readonly=True,
    )
    quoter_area_separator_visual_mode = fields.Selection(
        related="quoter_tab_area_id.separator_visual_mode",
        string="Visual separador (área)",
        readonly=True,
    )
    quoter_separator_section_tag_id = fields.Many2one(
        comodel_name="quoter.line.separator.tag",
        string="Sección de cotizador",
        copy=False,
        index=True,
    )
    quoter_separator_style_mode = fields.Selection(
        selection=[
            ("none", "Sin color"),
            ("full", "Línea completa con color"),
        ],
        string="Visual separador",
        copy=False,
    )
    quoter_separator_color = fields.Integer(
        string="Color separador",
        copy=False,
    )

    quoter_range_hour_ids = fields.One2many(
        comodel_name="sale.order.line.range.hour",
        inverse_name="sale_line_id",
        string="Horas por rango",
        copy=True,
    )

    quoter_total_hours = fields.Float(
        string="Horas totales",
        compute="_compute_quoter_total_hours",
        inverse="_inverse_quoter_total_hours",
        store=True,
    )
    quoter_manual_load = fields.Boolean(
        string="Carga manual (cotizador)",
        related="product_id.product_tmpl_id.quoter_service_line_id.manual_load",
        store=True,
        readonly=True,
    )
    quoter_manual_total_load = fields.Boolean(
        string="Horas totales manual (cotizador)",
        compute="_compute_quoter_manual_total_load",
        readonly=True,
    )
    quoter_can_edit_range_hours = fields.Boolean(
        string="Permite editar horas por rango",
        compute="_compute_quoter_can_edit_range_hours",
    )
    quoter_can_edit_total_hours = fields.Boolean(
        string="Permite editar horas totales",
        compute="_compute_quoter_can_edit_total_hours",
    )
    quoter_manual_mode_note = fields.Char(
        string="Modo manual",
        compute="_compute_quoter_manual_mode_note",
    )

    quoter_range_1_hours = fields.Float(
        string="Rango 1",
        compute="_compute_quoter_range_hours",
        inverse="_inverse_quoter_range_1_hours",
        store=True,
    )
    quoter_range_2_hours = fields.Float(
        string="Rango 2",
        compute="_compute_quoter_range_hours",
        inverse="_inverse_quoter_range_2_hours",
        store=True,
    )
    quoter_range_3_hours = fields.Float(
        string="Rango 3",
        compute="_compute_quoter_range_hours",
        inverse="_inverse_quoter_range_3_hours",
        store=True,
    )
    quoter_range_4_hours = fields.Float(
        string="Rango 4",
        compute="_compute_quoter_range_hours",
        inverse="_inverse_quoter_range_4_hours",
        store=True,
    )

    quoter_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área quoter",
        related="product_id.product_tmpl_id.quoter_area_id",
        store=True,
        readonly=True,
        index=True,
    )
    quoter_tab_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área (pestaña cotizador)",
        copy=False,
        ondelete="set null",
        index=True,
        help="Área de la pestaña donde se creó la línea; filtra líneas por área sin depender del producto.",
    )
    quoter_block_id = fields.Many2one(
        comodel_name="quoter.sale.order.area",
        string="Bloque cotizador",
        copy=False,
        ondelete="set null",
        index=True,
    )

    def _quoter_block_for_tab_area(self):
        self.ensure_one()
        order = self.order_id
        area = self.quoter_tab_area_id
        if not order or not area:
            return self.env["quoter.sale.order.area"]
        return order.quoter_area_block_ids.filtered(lambda b, a=area: b.area_id == a)[:1]

    def _quoter_sync_line_block_link(self):
        """Asocia la línea al bloque del pedido según `quoter_tab_area_id`."""
        for line in self:
            block = line._quoter_block_for_tab_area()
            if line.quoter_block_id != block:
                super(SaleOrderLine, line.with_context(quoter_skip_line_block_sync=True)).write(
                    {"quoter_block_id": block.id if block else False}
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order_id = vals.get("order_id")
            if not order_id:
                continue
            order = self.env["sale.order"].browse(order_id)
            product = self.env["product.product"].browse(vals.get("product_id"))
            if product.exists():
                self._quoter_ensure_accountable_required_fields(vals, product)
            if order.exists() and order.is_quotation:
                self._quoter_force_qty_one_in_vals(vals)
        self._quoter_prepare_sequences_on_create_vals(vals_list)
        lines = super().create(vals_list)
        post_ctx = dict(self.env.context, quoter_skip_chatter_log=True)
        lines.filtered(lambda l: l.order_id).with_context(
            post_ctx, quoter_skip_line_block_sync=True
        )._quoter_sync_line_block_link()
        qty_lines = lines.filtered(
            lambda l: l.order_id.is_quotation
            and not l.display_type
            and l.product_uom_qty != 1.0
        )
        if qty_lines:
            super(SaleOrderLine, qty_lines.with_context(post_ctx)).write({"product_uom_qty": 1.0})
        quoter_lines = lines.filtered(
            lambda l: l.order_id.is_quotation
            and l.quoter_tab_area_id
            and l.product_id
            and getattr(l.product_id, "is_quoter_product", False)
        )
        for line in quoter_lines.with_context(post_ctx):
            line._quoter_sync_range_hours()
            if not line.quoter_is_adjustment_line and not line.quoter_manual_load:
                if not line.quoter_manual_total_load:
                    line._quoter_apply_level_template_hours()
        for line in quoter_lines:
            price, _warn = line._quoter_compute_unit_price_from_ranges()
            super(SaleOrderLine, line.with_context(post_ctx)).write({"price_unit": price})
        quoter_lines.filtered("quoter_is_adjustment_line")._quoter_validate_adjustment_hours_balance()
        if not self.env.context.get("quoter_skip_chatter_log"):
            lines._quoter_log_lines_created()
        if not self.env.context.get("quoter_skip_block_product_refresh"):
            lines.mapped("order_id")._quoter_refresh_block_selectable_products()
        return lines

    def _quoter_block_level_for_line(self):
        self.ensure_one()
        order = self.order_id
        area = self.quoter_tab_area_id
        if not order or not area:
            return self.env["quoter.complexity.level"]
        block = order.quoter_area_block_ids.filtered(lambda b, a=area: b.area_id == a)[:1]
        return block.complexity_level_id if block else self.env["quoter.complexity.level"]

    def _quoter_block_branch_for_line(self):
        self.ensure_one()
        order = self.order_id
        area = self.quoter_tab_area_id
        if not order or not area:
            return self.env["quoter.area.branch"]
        block = order.quoter_area_block_ids.filtered(lambda b, a=area: b.area_id == a)[:1]
        if block and block.branch_id:
            return block.branch_id
        return area._resolve_matrix_branch()

    def _quoter_manual_total_mode(self):
        self.ensure_one()
        return bool(
            self.order_id
            and self.order_id.is_quotation
            and self.product_id
            and getattr(self.product_id, "is_quoter_product", False)
            and self.quoter_manual_total_load
        )

    def _quoter_manual_ranges_mode(self):
        self.ensure_one()
        return bool(
            self.order_id
            and self.order_id.is_quotation
            and self.product_id
            and getattr(self.product_id, "is_quoter_product", False)
            and self.quoter_manual_load
            and not self.quoter_manual_total_load
        )

    def _quoter_apply_level_template_hours(self):
        """Copia horas de quoter.product.level.range (plantilla por nivel) a las filas de esta línea."""
        for line in self:
            if line.quoter_is_adjustment_line:
                continue
            if line.quoter_manual_load or line.quoter_manual_total_load:
                continue
            if not line.order_id.is_quotation:
                continue
            if not line.product_id or not getattr(line.product_id, "is_quoter_product", False):
                continue
            area = line.quoter_tab_area_id
            if not area:
                continue
            level = line._quoter_block_level_for_line()
            branch = line._quoter_block_branch_for_line()
            if not level:
                continue
            tmpl = line.product_id.product_tmpl_id
            domain = [
                ("product_tmpl_id", "=", tmpl.id),
                ("complexity_level_id", "=", level.id),
            ]
            if branch:
                domain.append(("branch_id", "=", branch.id))
            plr = line.env["quoter.product.level.range"].search(domain, limit=1)
            if not plr and branch:
                plr = line.env["quoter.product.level.range"].search(
                    [
                        ("product_tmpl_id", "=", tmpl.id),
                        ("complexity_level_id", "=", level.id),
                    ],
                    limit=1,
                )
            if not plr:
                continue
            line._quoter_sync_range_hours()
            for tmpl_row in plr.output_line_ids:
                ar = tmpl_row.area_range_id
                h = float(tmpl_row.hours)
                row = line.quoter_range_hour_ids.filtered(
                    lambda hrow, a=ar: hrow.area_range_id == a
                )[:1]
                if row:
                    line._quoter_range_hour_sudo().browse(row.ids).write({"hours": h})

    def _quoter_product_id_domain(self):
        """Dominio de producto en cotización por área (excluye ya usados en otras líneas)."""
        order = self.order_id
        area = self.quoter_tab_area_id
        if not order or not order.is_quotation or not area:
            return []
        if not self._quoter_block_level_for_line():
            return [("id", "in", [])]
        exclude_id = self.id if isinstance(self.id, int) else False
        ids = self.env["product.product"]._quoter_product_ids_for_area_picker(
            area, order, exclude_line_id=exclude_id
        )
        if self.product_id and self.product_id.id not in ids:
            ids = list(ids) + [self.product_id.id]
        return [
            ("sale_ok", "=", True),
            ("is_quoter_range_rate_product", "=", False),
            ("id", "in", ids or [0]),
        ]

    @api.onchange("product_id", "quoter_tab_area_id", "order_id", "quoter_block_id")
    def _onchange_product_id_quoter_tab_area(self):
        tmpl = self.product_id.product_tmpl_id if self.product_id else False
        if self.product_id and tmpl and tmpl.quoter_area_id and not self.quoter_tab_area_id:
            self.quoter_tab_area_id = tmpl.quoter_area_id
        self._quoter_sync_range_hours()
        self._quoter_apply_level_template_hours()
        self._quoter_onchange_compute_price_from_ranges()
        if self.order_id and self.order_id.is_quotation and self.quoter_tab_area_id:
            return {"domain": {"product_id": self._quoter_product_id_domain()}}
        return {}

    @api.onchange(
        "quoter_tab_area_id",
        "order_id",
        "order_id.pricelist_id",
        "order_id.is_quotation",
    )
    def _onchange_order_pricelist(self):
        """Cotización: solo productos canónicos de quoter.service.line; horas por nivel del bloque."""
        order = self.order_id
        if not order:
            return {}
        self._quoter_sync_range_hours()
        self._quoter_apply_level_template_hours()
        self._quoter_onchange_compute_price_from_ranges()
        if order.is_quotation and self.quoter_tab_area_id:
            return {"domain": {"product_id": self._quoter_product_id_domain()}}
        if order.pricelist_id:
            domain = [
                ("area_id.pricelist_id", "=", order.pricelist_id.id),
                ("area_id.active", "=", True),
            ]
            if order.quoter_area_ids:
                domain.append(("area_id", "in", order.quoter_area_ids.ids))
            lines = self.env["quoter.service.line"].search(domain)
            tmpl_ids = lines.mapped("product_tmpl_id").ids
            product_ids = (
                self.env["product.product"]
                .search(
                    [
                        ("product_tmpl_id", "in", tmpl_ids),
                        ("is_quoter_range_rate_product", "=", False),
                    ]
                )
                .ids
            )
            if product_ids:
                return {"domain": {"product_id": [("id", "in", product_ids)]}}
        return {}

    def _quoter_price_warning_no_pricelist(self):
        return {
            "warning": {
                "title": _("Lista de precios requerida"),
                "message": _(
                    "Esta línea usa un producto del Cotizador y requiere una lista de precios en el área "
                    "(o en el pedido como respaldo) con reglas por producto para los ítems «Tarifa/h» "
                    "(área + rango), generados al configurar rangos del área."
                ),
            }
        }

    def _quoter_range_rate_variant(self, area, range_rec):
        """Variante del producto técnico tarifa/h para (área, rango)."""
        tmpl = self.env["product.template"].search(
            [
                ("is_quoter_range_rate_product", "=", True),
                ("quoter_range_rate_area_id", "=", area.id),
                ("quoter_range_rate_range_id", "=", range_rec.id),
            ],
            limit=1,
        )
        return tmpl.product_variant_id if tmpl else self.env["product.product"]

    def _quoter_compute_unit_price_from_ranges(self):
        self.ensure_one()
        product = self.product_id
        if not product or not getattr(product, "is_quoter_product", False):
            return 0.0, False
        order = self.order_id
        if not order:
            return 0.0, False
        if not self.quoter_tab_area_id:
            return 0.0, False

        ranges = self._quoter_first_area_ranges(limit=4)
        if not ranges:
            return 0.0, False

        area = self.quoter_tab_area_id
        partner = order.partner_id or self.env["res.partner"]
        pl = area.pricelist_id or order.pricelist_id
        if not pl:
            return 0.0, self._quoter_price_warning_no_pricelist()
        hours_by_range = {h.area_range_id.id: h.hours for h in self.quoter_range_hour_ids if h.area_range_id}

        total = 0.0
        for r in ranges:
            pvariant = self._quoter_range_rate_variant(area, r)
            if not pvariant:
                continue
            price_h = pl.get_product_price(
                pvariant,
                1.0,
                partner,
                date=order.date_order,
                uom_id=pvariant.uom_id.id,
            )
            total += float(hours_by_range.get(r.id, 0.0)) * float(price_h)
        return total, False

    @api.onchange(
        "product_id",
        "quoter_tab_area_id",
        "order_id",
        "order_id.pricelist_id",
        "quoter_range_1_hours",
        "quoter_range_2_hours",
        "quoter_range_3_hours",
        "quoter_range_4_hours",
        "quoter_range_hour_ids",
        "quoter_range_hour_ids.hours",
    )
    def _quoter_onchange_compute_price_from_ranges(self):
        for line in self:
            if not line.product_id or not getattr(line.product_id, "is_quoter_product", False):
                continue
            price, warn = line._quoter_compute_unit_price_from_ranges()
            line.price_unit = price
            if warn:
                return warn
        return {}

    def write(self, vals):
        """Ignora escrituras sobre líneas ya borradas (p. ej. BasicModel tras unlink en bloque)."""
        recs = self.exists()
        if not recs:
            return True
        if vals and "product_uom_qty" in vals:
            if any(line.order_id.is_quotation and not line.display_type for line in recs):
                vals = dict(vals)
                vals["product_uom_qty"] = 1.0
        log_vals = dict(vals) if vals else {}
        res = super(SaleOrderLine, recs).write(vals)
        trigger_fields = {
            "product_id",
            "order_id",
            "quoter_tab_area_id",
            "quoter_range_hour_ids",
            "quoter_range_1_hours",
            "quoter_range_2_hours",
            "quoter_range_3_hours",
            "quoter_range_4_hours",
            "quoter_total_hours",
        }
        if set(vals.keys()) & trigger_fields:
            for line in recs:
                if not line.product_id or not getattr(line.product_id, "is_quoter_product", False):
                    continue
                price, _warn = line._quoter_compute_unit_price_from_ranges()
                super(SaleOrderLine, line).write({"price_unit": price})
        if not self.env.context.get("quoter_skip_line_block_sync") and vals:
            if {"quoter_tab_area_id", "order_id"} & set(vals.keys()):
                recs.filtered(lambda l: l.order_id).with_context(
                    quoter_skip_line_block_sync=True
                )._quoter_sync_line_block_link()
        if log_vals and not self.env.context.get("quoter_skip_chatter_log"):
            recs._quoter_log_line_change(log_vals)
        if set(vals or {}) & {"product_id", "quoter_tab_area_id", "order_id"}:
            if not self.env.context.get("quoter_skip_block_product_refresh"):
                recs.mapped("order_id")._quoter_refresh_block_selectable_products()
        trigger_hours = {
            "quoter_range_1_hours",
            "quoter_range_2_hours",
            "quoter_range_3_hours",
            "quoter_range_4_hours",
            "quoter_range_hour_ids",
            "quoter_total_hours",
        }
        if set(vals or {}) & trigger_hours:
            recs.filtered("quoter_is_adjustment_line")._quoter_validate_adjustment_hours_balance()
        return res

    def unlink(self):
        recs = self.exists()
        if not recs:
            return True
        orders = recs.mapped("order_id")
        removed_logs = []
        if not self.env.context.get("quoter_skip_chatter_log"):
            for line in recs:
                order = line.order_id
                if (
                    not order
                    or not order.is_quotation
                    or line.display_type
                    or line.quoter_is_area_discount_total_line
                    or not line.quoter_tab_area_id
                ):
                    continue
                product_name = (
                    line.product_id.display_name
                    if line.product_id
                    else (line.name or _("Línea"))
                )
                removed_logs.append(
                    (order.id, line.quoter_tab_area_id.display_name, product_name)
                )
        orders_to_refresh = orders
        res = super(SaleOrderLine, recs).unlink()
        if not self.env.context.get("quoter_skip_block_product_refresh"):
            orders_to_refresh._quoter_refresh_block_selectable_products()
        if removed_logs:
            for order_id, area_name, product_name in removed_logs:
                order = self.env["sale.order"].browse(order_id)
                if order.exists():
                    order._quoter_message_post(
                        _("<b>%s</b><br/>%s: %s")
                        % (area_name, _("Producto eliminado"), product_name)
                    )
        return res

    def _quoter_first_area_ranges(self, limit=4):
        self.ensure_one()
        area = self.quoter_tab_area_id
        if not area:
            return self.env["quoter.area.complexity.range"].browse()
        return area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:limit]

    def _quoter_sync_range_hours(self):
        """Alinear quoter_range_hour_ids con los rangos del área (máx. 4)."""
        for line in self:
            ranges = line._quoter_first_area_ranges(limit=4)
            if not ranges:
                if isinstance(line.id, int) and line.quoter_range_hour_ids:
                    line._quoter_range_hour_sudo().browse(line.quoter_range_hour_ids.ids).unlink()
                elif not isinstance(line.id, int):
                    line.quoter_range_hour_ids = [(5, 0, 0)]
                continue
            keep_ids = set(ranges.ids)
            existing_rows = line.quoter_range_hour_ids
            existing_by_range = {h.area_range_id.id: h for h in existing_rows if h.area_range_id}

            # En registros nuevos (NewId) no podemos hacer create/unlink en BD.
            in_db = isinstance(line.id, int)
            if in_db:
                # borrar filas que ya no aplican (por cambio de área o rangos)
                line._quoter_range_hour_sudo().browse(
                    existing_rows.filtered(lambda h: h.area_range_id.id not in keep_ids).ids
                ).unlink()
                existing = set(line.quoter_range_hour_ids.mapped("area_range_id").ids)
                for r in ranges:
                    if r.id not in existing:
                        line._quoter_range_hour_sudo().create(
                            {
                                "sale_line_id": line.id,
                                "area_range_id": r.id,
                                "hours": 0.0,
                            }
                        )
            else:
                # Re-armar en memoria respetando orden/limite y manteniendo horas existentes.
                commands = [(5, 0, 0)]
                for r in ranges:
                    row = existing_by_range.get(r.id)
                    hours = row.hours if row else 0.0
                    commands.append((0, 0, {"area_range_id": r.id, "hours": hours}))
                line.quoter_range_hour_ids = commands

    @api.depends("quoter_range_hour_ids", "quoter_range_hour_ids.hours")
    def _compute_quoter_total_hours(self):
        for line in self:
            line.quoter_total_hours = sum(line.quoter_range_hour_ids.mapped("hours"))

    @api.depends(
        "product_id",
        "product_id.product_tmpl_id",
        "product_id.product_tmpl_id.quoter_service_line_id",
    )
    def _compute_quoter_manual_total_load(self):
        for line in self:
            service_line = line.product_id.product_tmpl_id.quoter_service_line_id
            line.quoter_manual_total_load = bool(
                service_line and getattr(service_line, "manual_total_load", False)
            )

    @api.depends(
        "order_id.is_quotation",
        "product_id",
        "product_id.product_tmpl_id.is_quoter_product",
        "product_id.product_tmpl_id.quoter_service_line_id.manual_load",
        "quoter_manual_total_load",
        "quoter_is_adjustment_line",
    )
    def _compute_quoter_can_edit_range_hours(self):
        for line in self:
            if line.quoter_is_adjustment_line and line.order_id.is_quotation:
                line.quoter_can_edit_range_hours = True
                continue
            line.quoter_can_edit_range_hours = line._quoter_manual_ranges_mode()

    @api.depends(
        "order_id.is_quotation",
        "product_id",
        "product_id.product_tmpl_id.is_quoter_product",
        "quoter_manual_total_load",
        "quoter_tab_area_id",
        "quoter_is_adjustment_line",
    )
    def _compute_quoter_can_edit_total_hours(self):
        for line in self:
            if line.quoter_is_adjustment_line and line.order_id.is_quotation:
                line.quoter_can_edit_total_hours = False
                continue
            line.quoter_can_edit_total_hours = line._quoter_manual_total_mode()

    @api.depends(
        "quoter_manual_load",
        "quoter_manual_total_load",
    )
    def _compute_quoter_manual_mode_note(self):
        for line in self:
            if line.quoter_manual_total_load:
                line.quoter_manual_mode_note = _("Total manual")
            elif line.quoter_manual_load:
                line.quoter_manual_mode_note = _("Rangos manual")
            else:
                line.quoter_manual_mode_note = ""

    def _inverse_quoter_total_hours(self):
        Policy = self.env["quoter.hours.policy"]
        for line in self:
            if not line._quoter_manual_total_mode():
                continue
            value = Policy.validate_hours_strictly_positive(
                line.quoter_total_hours, _("Total horas")
            )
            line._quoter_sync_range_hours()
            rows = line.quoter_range_hour_ids.sorted(key=lambda r: (r.area_range_id.sequence, r.id))
            if not rows:
                continue
            current = [float(r.hours or 0.0) for r in rows]
            total = sum(current)
            if total > 0:
                factor = value / total
                new_vals = [h * factor for h in current]
            else:
                each = (value / len(rows)) if rows else 0.0
                new_vals = [each] * len(rows)
            for row, new_h in zip(rows, new_vals):
                row.write({"hours": new_h})
            line._quoter_onchange_compute_price_from_ranges()

    @api.depends(
        "quoter_tab_area_id",
        "quoter_range_hour_ids",
        "quoter_range_hour_ids.hours",
        "quoter_range_hour_ids.area_range_id",
        "quoter_range_hour_ids.area_range_id.sequence",
    )
    def _compute_quoter_range_hours(self):
        for line in self:
            vals = [0.0, 0.0, 0.0, 0.0]
            ranges = line._quoter_first_area_ranges(limit=4)
            if ranges:
                by_range = {h.area_range_id.id: h.hours for h in line.quoter_range_hour_ids}
                for i, r in enumerate(ranges):
                    vals[i] = float(by_range.get(r.id, 0.0))
            line.quoter_range_1_hours = vals[0]
            line.quoter_range_2_hours = vals[1]
            line.quoter_range_3_hours = vals[2]
            line.quoter_range_4_hours = vals[3]

    def _quoter_set_range_hours_by_index(self, index_1based, value):
        Policy = self.env["quoter.hours.policy"]
        for line in self:
            if not line.quoter_tab_area_id:
                continue
            line._quoter_sync_range_hours()
            ranges = line._quoter_first_area_ranges(limit=4)
            if len(ranges) < index_1based:
                continue
            r = ranges[index_1based - 1]
            row = line.quoter_range_hour_ids.filtered(lambda h: h.area_range_id == r)[:1]
            hours_val = float(value or 0.0)
            if line.quoter_is_adjustment_line:
                hours_val = Policy.validate_adjustment_hours_nonzero(
                    hours_val, r.display_name
                )
            elif line._quoter_manual_ranges_mode():
                hours_val = Policy.validate_hours_strictly_positive(
                    hours_val, _("Horas")
                )
            if row:
                line._quoter_range_hour_sudo().browse(row.ids).write({"hours": hours_val})
                continue
            if isinstance(line.id, int):
                line._quoter_range_hour_sudo().create(
                    {
                        "sale_line_id": line.id,
                        "area_range_id": r.id,
                        "hours": hours_val,
                    }
                )
            else:
                line.quoter_range_hour_ids = [
                    (0, 0, {"area_range_id": r.id, "hours": hours_val})
                ]

    def _inverse_quoter_range_1_hours(self):
        for line in self:
            line._quoter_set_range_hours_by_index(1, line.quoter_range_1_hours)

    def _inverse_quoter_range_2_hours(self):
        for line in self:
            line._quoter_set_range_hours_by_index(2, line.quoter_range_2_hours)

    def _inverse_quoter_range_3_hours(self):
        for line in self:
            line._quoter_set_range_hours_by_index(3, line.quoter_range_3_hours)

    def _inverse_quoter_range_4_hours(self):
        for line in self:
            line._quoter_set_range_hours_by_index(4, line.quoter_range_4_hours)

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.order_id.is_quotation and self.product_id:
            QLine = self.env["quoter.service.line"]
            if self.quoter_tab_area_id:
                quoter_line = QLine.search(
                    [
                        ("product_tmpl_id", "=", self.product_id.product_tmpl_id.id),
                        ("area_id", "=", self.quoter_tab_area_id.id),
                    ],
                    limit=1,
                )
            else:
                quoter_line = QLine.search([("product_id", "=", self.product_id.id)], limit=1)
            if quoter_line:
                # Extensible: copiar metadatos a factura si hace falta
                pass
        return res

    @api.constrains("quoter_is_adjustment_line", "quoter_adjustment_note")
    def _check_quoter_adjustment_note(self):
        for line in self:
            if line.quoter_is_adjustment_line and not (line.quoter_adjustment_note or "").strip():
                raise ValidationError(
                    _("La observación es obligatoria en líneas de ajuste.")
                )

    @api.constrains(
        "product_id",
        "quoter_tab_area_id",
        "order_id",
        "display_type",
        "quoter_is_area_discount_total_line",
    )
    def _check_unique_product_per_area(self):
        for line in self:
            if (
                not line.order_id.is_quotation
                or line.display_type
                or not line.product_id
                or not line.quoter_tab_area_id
                or line.quoter_is_area_discount_total_line
                or line.quoter_is_adjustment_line
            ):
                continue
            dup = self.search(
                [
                    ("order_id", "=", line.order_id.id),
                    ("quoter_tab_area_id", "=", line.quoter_tab_area_id.id),
                    ("product_id", "=", line.product_id.id),
                    ("id", "!=", line.id),
                    ("display_type", "=", False),
                    ("quoter_is_area_discount_total_line", "=", False),
                    ("quoter_is_adjustment_line", "=", False),
                ],
                limit=1,
            )
            if dup:
                raise ValidationError(
                    _("El producto «%s» ya está en esta área de la cotización.")
                    % line.product_id.display_name
                )

    def _quoter_validate_adjustment_hours_balance(self):
        """Las horas de ajuste no pueden dejar el total por rol por debajo de cero."""
        for line in self.filtered("quoter_is_adjustment_line"):
            parent = line.quoter_adjustment_parent_line_id
            if not parent or not line.quoter_tab_area_id:
                continue
            ranges = line._quoter_first_area_ranges(limit=4)
            parent_by_range = {
                h.area_range_id.id: float(h.hours or 0.0)
                for h in parent.quoter_range_hour_ids
                if h.area_range_id
            }
            adj_by_range = {
                h.area_range_id.id: float(h.hours or 0.0)
                for h in line.quoter_range_hour_ids
                if h.area_range_id
            }
            for ar in ranges:
                adj_h = adj_by_range.get(ar.id, 0.0)
                if adj_h == 0.0 and ar.id in adj_by_range:
                    raise ValidationError(
                        _(
                            "Las horas de ajuste en «%s» no pueden ser cero "
                            "(categoría «%s»)."
                        )
                        % (line.display_name, ar.display_name)
                    )
                total = parent_by_range.get(ar.id, 0.0) + adj_h
                if total < 0.0:
                    raise ValidationError(
                        _(
                            "Las horas de ajuste en «%s» no pueden superar las horas base "
                            "del producto en la categoría de recursos «%s»."
                        )
                        % (line.display_name, ar.display_name)
                    )
            base_total = sum(parent_by_range.get(ar.id, 0.0) for ar in ranges)
            adj_total = sum(adj_by_range.get(ar.id, 0.0) for ar in ranges)
            if base_total + adj_total < 0.0:
                raise ValidationError(
                    _("El ajuste de horas no puede dejar un total negativo en la línea.")
                )

    def _quoter_log_lines_created(self):
        """Chatter al agregar líneas de producto en una cotización por área."""
        for line in self:
            order = line.order_id
            if (
                not order
                or not order.is_quotation
                or line.display_type
                or line.quoter_is_area_discount_total_line
                or not line.quoter_tab_area_id
            ):
                continue
            area_name = line.quoter_tab_area_id.display_name
            product_name = (
                line.product_id.display_name
                if line.product_id
                else (line.name or _("Línea"))
            )
            parts = [_("Producto agregado: %s") % product_name]
            if line.quoter_is_adjustment_line:
                parts[0] = _("Línea de ajuste agregada: %s") % product_name
            total_h = float(line.quoter_total_hours or 0.0)
            if total_h:
                parts.append("%s: %s" % (_("Total horas"), total_h))
            order._quoter_message_post(
                _("<b>%s</b><br/>%s") % (area_name, "<br/>".join(parts))
            )

    def _quoter_log_line_change(self, vals):
        tracked = {
            "product_id": _("Producto"),
            "quoter_total_hours": _("Total horas"),
            "quoter_adjustment_note": _("Observación ajuste"),
        }
        hour_fields = {
            "quoter_range_1_hours",
            "quoter_range_2_hours",
            "quoter_range_3_hours",
            "quoter_range_4_hours",
        }
        for line in self:
            order = line.order_id
            if not order or not order.is_quotation or not line.quoter_tab_area_id:
                continue
            parts = []
            area_name = line.quoter_tab_area_id.display_name
            for fname in hour_fields:
                if fname in vals:
                    parts.append(
                        "%s: %s → %s"
                        % (_("Horas por categoría"), line[fname], vals[fname])
                    )
            for fname, label in tracked.items():
                if fname not in vals:
                    continue
                old = line[fname]
                new = vals[fname]
                if fname == "product_id":
                    old_disp = old.display_name if old else "-"
                    new_p = self.env["product.product"].browse(new) if new else False
                    new_disp = new_p.display_name if new_p else "-"
                    if old_disp != new_disp:
                        parts.append("%s: %s → %s" % (label, old_disp, new_disp))
                elif old != new:
                    parts.append("%s: %s → %s" % (label, old, new))
            if parts:
                order._quoter_message_post(
                    _("<b>%s</b> — %s<br/>%s")
                    % (area_name, line.name or line.product_id.display_name or "", "<br/>".join(parts))
                )

    @api.depends("quoter_adjustment_child_line_ids")
    def _compute_quoter_has_adjustment_line(self):
        for line in self:
            has_adj = bool(line.quoter_adjustment_child_line_ids)
            line.quoter_has_adjustment_line = has_adj
            line.quoter_adjustment_status = _("Ajustado") if has_adj else ""

    @api.model
    def _quoter_next_odd_sequence_after(self, current_max):
        """Siguiente impar estrictamente mayor que current_max (hueco par reservado al ajuste)."""
        n = int(current_max or 0) + 1
        if n % 2 == 0:
            n += 1
        return n

    @api.model
    def _quoter_prepare_sequences_on_create_vals(self, vals_list):
        """En cotización + pestaña cotizador: líneas base en impar; deja el par libre para el ajuste."""
        running_max_by_order = {}
        for vals in vals_list:
            if vals.get("display_type"):
                continue
            if vals.get("quoter_is_adjustment_line"):
                continue
            order_id = vals.get("order_id")
            if not order_id:
                continue
            order = self.env["sale.order"].browse(order_id)
            if not order.exists() or not order.is_quotation:
                continue
            if not vals.get("quoter_tab_area_id"):
                continue
            if order_id not in running_max_by_order:
                running_max_by_order[order_id] = max(order.order_line.mapped("sequence") or [0])
            nxt = self._quoter_next_odd_sequence_after(running_max_by_order[order_id])
            vals["sequence"] = nxt
            running_max_by_order[order_id] = nxt

    def _quoter_shift_sequences_after(self, pivot_sequence):
        self.ensure_one()
        order = self.order_id
        if not order:
            return
        pivot = int(pivot_sequence)
        lines_to_shift = order.order_line.filtered(lambda l: int(l.sequence) > pivot)
        if lines_to_shift:
            for line in lines_to_shift.sorted(key=lambda l: (l.sequence, l.id), reverse=True):
                super(SaleOrderLine, line).write({"sequence": int(line.sequence) + 1})

    def _quoter_ensure_odd_sequence_for_adjustment_parent(self):
        """Línea base impar; la de ajuste queda en base+1 (par)."""
        self.ensure_one()
        order = self.order_id
        if not order:
            return int(self.sequence)
        seq = int(self.sequence)
        if seq % 2 == 1:
            return seq
        others = order.order_line.filtered(lambda l: l.id != self.id)
        for candidate in (seq - 1, seq + 1):
            if candidate < 1:
                continue
            if not others.filtered(lambda l: int(l.sequence) == candidate):
                super(SaleOrderLine, self).write({"sequence": candidate})
                self.invalidate_cache(fnames=["sequence"])
                return candidate
        return seq

    def _quoter_validate_adjustment_create_permissions(self):
        self.ensure_one()
        if self.display_type:
            raise ValidationError(_("No se pueden crear ajustes sobre una línea separadora."))
        if self.quoter_is_adjustment_line:
            raise ValidationError(_("Solo se pueden crear ajustes desde una línea base."))
        if not self.order_id or not self.order_id.is_quotation:
            raise ValidationError(_("El ajuste solo aplica a cotizaciones del cotizador."))
        if not self.product_id:
            raise ValidationError(_("La línea base debe tener un producto para crear el ajuste."))
        if self.quoter_adjustment_child_line_ids:
            raise ValidationError(_("Esta línea ya tiene un ajuste creado."))
        if not self.order_id.quoter_manager_id:
            raise ValidationError(
                _("Defina primero un Gerente responsable en la cotización para crear líneas de ajuste.")
            )
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(_("Solo usuarios del grupo Quoter - Gerente pueden crear líneas de ajuste."))
        if self.order_id.quoter_manager_id != self.env.user:
            raise AccessError(
                _("Solo el gerente asignado en la cotización puede crear líneas de ajuste.")
            )

    def _quoter_create_adjustment_line(self, note):
        self.ensure_one()
        self._quoter_validate_adjustment_create_permissions()
        note = (note or "").strip()
        if not note:
            raise ValidationError(_("La observación es obligatoria en líneas de ajuste."))
        base_seq = self._quoter_ensure_odd_sequence_for_adjustment_parent()
        self._quoter_shift_sequences_after(base_seq)
        adj_seq = int(self.sequence) + 1
        adj_vals = {
            "order_id": self.order_id.id,
            "product_id": self.product_id.id,
            "name": _("Ajuste - %s") % (self.name or self.product_id.display_name),
            "product_uom_qty": 1.0,
            "product_uom": self.product_uom.id if self.product_uom else self.product_id.uom_id.id,
            "tax_id": [(6, 0, self.tax_id.ids)],
            "discount": 0.0,
            "sequence": adj_seq,
            "quoter_tab_area_id": self.quoter_tab_area_id.id,
            "quoter_is_adjustment_line": True,
            "quoter_adjustment_parent_line_id": self.id,
            "quoter_adjustment_note": note,
        }
        if self.quoter_block_id:
            adj_vals["quoter_block_id"] = self.quoter_block_id.id
        new_line = self.create(adj_vals)
        new_line._quoter_sync_range_hours()
        for rh in new_line.quoter_range_hour_ids:
            rh.write({"hours": 0.0})
        new_line._quoter_onchange_compute_price_from_ranges()
        return True

    def action_quoter_add_adjustment_line(self):
        self.ensure_one()
        self._quoter_validate_adjustment_create_permissions()
        return {
            "type": "ir.actions.act_window",
            "name": _("Agregar ajuste"),
            "res_model": "quoter.adjustment.note.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_sale_line_id": self.id,
            },
        }

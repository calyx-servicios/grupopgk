# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    _QUOTER_RANGE_HOUR_FIELD_NAMES = frozenset(
        {
            "quoter_range_1_hours",
            "quoter_range_2_hours",
            "quoter_range_3_hours",
            "quoter_range_4_hours",
        }
    )

    # Campos técnicos gestionados por el sistema (computados almacenados que se
    # persisten solos al leerse, p. ej. `number` de sale_order_line_number). No son
    # contenido editable por el usuario, así que su reescritura NO debe bloquearse por
    # el guard de flujo aunque la cotización esté en un estado no editable.
    _QUOTER_LINE_GUARD_TECHNICAL_FIELDS = frozenset(
        {
            "number",
        }
    )

    @api.model
    def _quoter_is_real_db_id(self, record_id):
        return isinstance(record_id, int) and record_id > 0

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
    quoter_subtract_in_bpa = fields.Boolean(
        string="Restar en BPA",
        related="product_id.product_tmpl_id.quoter_service_line_id.subtract_in_bpa",
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
        compute="_compute_quoter_manual_flags",
        readonly=True,
    )
    quoter_manual_total_load = fields.Boolean(
        string="Horas totales manual (cotizador)",
        compute="_compute_quoter_manual_flags",
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
    quoter_formula_volume = fields.Float(
        string="Volumen",
        default=1.0,
        copy=True,
        help="Volumen editable en la cotización para áreas fórmula. "
        "Es independiente del volumen de prueba de la configuración del área/producto.",
    )
    quoter_formula_is_fixed = fields.Boolean(
        string="Horas fijas (fórmula)",
        compute="_compute_quoter_formula_is_fixed",
    )
    quoter_formula_referencia = fields.Char(
        string="Referencia volumen",
        related="product_id.product_tmpl_id.quoter_formula_config_id.referencia_volumen",
        readonly=True,
    )
    quoter_tab_area_is_formula = fields.Boolean(
        string="Área fórmula (pestaña)",
        compute="_compute_quoter_tab_area_is_formula",
    )
    quoter_show_formula_volume = fields.Boolean(
        string="Mostrar volumen fórmula",
        compute="_compute_quoter_show_formula_volume",
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
            area = line._quoter_effective_tab_area()
            if (
                not line.quoter_is_adjustment_line
                and not line._quoter_manual_ranges_mode()
                and not line._quoter_manual_total_mode()
            ):
                if area and area.hour_matrix_mode == "formula":
                    if float(line.quoter_formula_volume or 0.0) <= 0.0:
                        line.quoter_formula_volume = line._quoter_formula_initial_volume()
                    line._quoter_apply_formula_hours()
                else:
                    line._quoter_apply_level_template_hours()
            elif line._quoter_manual_ranges_mode() and not line.quoter_is_adjustment_line:
                line._quoter_sync_slots_to_hour_rows_from_columns()
        for line in quoter_lines:
            line.with_context(quoter_allow_zero_hours=line.quoter_is_adjustment_line)._quoter_prepare_hours_and_price()
            if line._quoter_is_regular_manual_line():
                # Finanzas: el precio unitario es manual; no pisar el valor recibido.
                continue
            price, _warn = line._quoter_compute_unit_price_from_ranges()
            super(SaleOrderLine, line.with_context(post_ctx)).write({"price_unit": price})
        quoter_lines.filtered("quoter_is_adjustment_line")._quoter_validate_adjustment_hours_balance()
        if not self.env.context.get("quoter_skip_chatter_log"):
            lines._quoter_log_lines_created()
        if not self.env.context.get("quoter_skip_block_product_refresh"):
            lines.mapped("order_id")._quoter_refresh_block_selectable_products()
        return lines

    def _quoter_effective_order(self):
        """Pedido cotización en onchange (form embebido puede omitir order_id en el payload)."""
        self.ensure_one()
        if self.order_id:
            return self.order_id
        order_id = self.env.context.get("default_order_id")
        if order_id:
            return self.env["sale.order"].browse(order_id)
        if self.quoter_block_id:
            return self.quoter_block_id.order_id
        return self.env["sale.order"]

    def _quoter_effective_tab_area(self):
        """Área de pestaña en onchange (default del bloque / contexto)."""
        self.ensure_one()
        if self.quoter_tab_area_id:
            return self.quoter_tab_area_id
        area_id = self.env.context.get("default_quoter_tab_area_id")
        if area_id:
            return self.env["quoter.professional.area"].browse(area_id)
        if self.quoter_block_id and self.quoter_block_id.area_id:
            return self.quoter_block_id.area_id
        return self.quoter_area_id

    def _quoter_block_level_for_line(self):
        self.ensure_one()
        order = self._quoter_effective_order()
        area = self._quoter_effective_tab_area()
        if not order or not area:
            return self.env["quoter.complexity.level"]
        block = order.quoter_area_block_ids.filtered(lambda b, a=area: b.area_id == a)[:1]
        if not block and self.quoter_block_id:
            block = self.quoter_block_id
        return block.complexity_level_id if block else self.env["quoter.complexity.level"]

    def _quoter_block_branch_for_line(self):
        self.ensure_one()
        order = self._quoter_effective_order()
        area = self._quoter_effective_tab_area()
        if not order or not area:
            return self.env["quoter.area.branch"]
        block = order.quoter_area_block_ids.filtered(lambda b, a=area: b.area_id == a)[:1]
        if not block and self.quoter_block_id:
            block = self.quoter_block_id
        if block and block.branch_id:
            return block.branch_id
        return area._resolve_matrix_branch()

    def _quoter_service_line(self):
        """Línea de servicio del producto en el área de la pestaña (no el genérico del tmpl)."""
        self.ensure_one()
        if not self.product_id:
            return self.env["quoter.service.line"]
        tmpl = self.product_id.product_tmpl_id
        QLine = self.env["quoter.service.line"]
        area = self._quoter_effective_tab_area()
        if area:
            line = QLine.search(
                [("product_tmpl_id", "=", tmpl.id), ("area_id", "=", area.id)],
                limit=1,
            )
            if line:
                return line
        return tmpl.quoter_service_line_id

    def _quoter_manual_total_mode(self):
        self.ensure_one()
        if self.quoter_is_adjustment_line:
            return False
        order = self._quoter_effective_order()
        if not (
            order
            and order.is_quotation
            and self.product_id
            and getattr(self.product_id, "is_quoter_product", False)
        ):
            return False
        qsl = self._quoter_service_line()
        return bool(qsl and getattr(qsl, "manual_total_load", False))

    def _quoter_manual_ranges_mode(self):
        self.ensure_one()
        if self.quoter_is_adjustment_line:
            return False
        order = self._quoter_effective_order()
        if not (
            order
            and order.is_quotation
            and self.product_id
            and getattr(self.product_id, "is_quoter_product", False)
        ):
            return False
        if self.quoter_manual_total_load:
            return False
        if self.quoter_manual_load:
            return True
        # Áreas regular_manual: horas siempre manuales (sin configuración por producto).
        area = self._quoter_effective_tab_area()
        if area and area.hour_matrix_mode == "regular_manual":
            return True
        return False

    def _quoter_is_regular_manual_line(self):
        """Línea de área Finanzas (regular_manual): horas y precio unitario 100% manuales.

        En estas áreas el precio unitario lo escribe el usuario (el onchange lo
        rellena desde la tarifa al cambiar horas, pero una edición manual debe
        conservarse). Por eso el backend no debe recalcular ni pisar `price_unit`.
        """
        self.ensure_one()
        if self.quoter_is_adjustment_line:
            return False
        order = self._quoter_effective_order()
        if not (
            order
            and order.is_quotation
            and self.product_id
            and getattr(self.product_id, "is_quoter_product", False)
        ):
            return False
        area = self._quoter_effective_tab_area()
        return bool(area and area.hour_matrix_mode == "regular_manual")

    def _quoter_is_new_line_record(self):
        """Línea aún no persistida (NewId en x2many del bloque embebido)."""
        self.ensure_one()
        return not self._quoter_is_real_db_id(self.id)

    def _quoter_should_validate_hours_on_edit(self):
        """Validación por celda solo en líneas guardadas; la suma se controla al guardar."""
        self.ensure_one()
        if self.quoter_is_adjustment_line:
            return False
        if self.env.context.get("quoter_allow_zero_hours"):
            return False
        return not self._quoter_is_new_line_record()

    def _quoter_bypass_per_role_hours_validation(self):
        """Líneas de ajuste: sin validación >0 por celda; solo balance base+ajuste."""
        self.ensure_one()
        return bool(self.quoter_is_adjustment_line)

    def _quoter_range_hours_sum(self):
        self.ensure_one()
        return sum(float(h.hours or 0.0) for h in self.quoter_range_hour_ids)

    def _quoter_validate_quotation_line_hours_sum(self):
        """Al guardar bloque/pedido: suma > 0 en líneas base; ajustes excluidos."""
        Policy = self.env["quoter.hours.policy"].with_context(
            quoter_allow_zero_hours=False
        )
        for line in self.exists():
            if line.quoter_is_adjustment_line:
                continue
            if not line.order_id or not line.order_id.is_quotation:
                continue
            if line.display_type or not line.product_id:
                continue
            if not getattr(line.product_id, "is_quoter_product", False):
                continue
            if line._quoter_manual_total_mode():
                Policy.validate_hours_non_negative(
                    line.quoter_total_hours,
                    _("Total horas"),
                )
                continue
            if line._quoter_manual_ranges_mode():
                Policy.validate_quotation_line_hours_sum(
                    line._quoter_range_hours_sum(),
                    line.product_id.display_name,
                )
                continue
            Policy.validate_quotation_line_hours_sum(
                line._quoter_range_hours_sum(),
                line.product_id.display_name,
            )

    @api.depends(
        "quoter_tab_area_id",
        "quoter_tab_area_id.hour_matrix_mode",
        "quoter_block_id",
        "quoter_block_id.area_id",
        "quoter_block_id.area_id.hour_matrix_mode",
    )
    def _compute_quoter_tab_area_is_formula(self):
        for line in self:
            area = line._quoter_effective_tab_area()
            line.quoter_tab_area_is_formula = bool(
                area and area.hour_matrix_mode == "formula"
            )

    @api.depends(
        "quoter_tab_area_id",
        "quoter_tab_area_id.hour_matrix_mode",
        "quoter_block_id",
        "quoter_block_id.area_id",
        "quoter_block_id.area_id.hour_matrix_mode",
    )
    def _compute_quoter_show_formula_volume(self):
        for line in self:
            area = line._quoter_effective_tab_area()
            line.quoter_show_formula_volume = bool(
                area and area.hour_matrix_mode == "formula"
            )

    def _quoter_formula_config_for_line(self):
        self.ensure_one()
        if not self.product_id:
            return self.env["quoter.formula.product.config"]
        area = self._quoter_effective_tab_area()
        if not area or area.hour_matrix_mode != "formula":
            return self.env["quoter.formula.product.config"]
        return self.env["quoter.formula.product.config"].get_config_for_template(
            self.product_id.product_tmpl_id, area
        )

    @api.depends(
        "product_id",
        "quoter_tab_area_id",
        "quoter_block_id",
        "quoter_block_id.area_id",
    )
    def _compute_quoter_formula_is_fixed(self):
        for line in self:
            config = line._quoter_formula_config_for_line()
            line.quoter_formula_is_fixed = bool(
                config and config.tipo_calculo == "fija"
            )

    def _quoter_formula_hours_map_for_config(self, config, area, volume):
        """
        Horas por rol según volumen en cotización.
        Si volumen es 0 y el producto no es de horas fijas, todas las horas son 0
        (evita horas «por debajo del umbral» de la fórmula con volumen 0).
        """
        if not config:
            return {}
        area = area or config.area_id
        ranges = config._ordered_area_ranges(area=area)
        if config.tipo_calculo == "fija":
            return config.compute_hours_by_range(volume, area=area)
        if float(volume or 0.0) <= 0.0:
            return {r.id: 0.0 for r in ranges}
        return config.compute_hours_by_range(volume, area=area)

    def _quoter_apply_formula_output_hours(self, area, config, volume, raw_hours):
        """
        Horas finales por rol en cotización.
        Volumen 0 (producto no fijo): siempre 0, sin piso de «mínimo tabla resultado».
        """
        if config and config.tipo_calculo != "fija" and float(volume or 0.0) <= 0.0:
            return 0.0
        return area._apply_output_hours_minimum(raw_hours)

    def _quoter_is_formula_variable_volume_line(self):
        """Producto de área fórmula con volumen (no horas fijas)."""
        self.ensure_one()
        if self.quoter_is_adjustment_line:
            return False
        area = self._quoter_effective_tab_area()
        if not area or area.hour_matrix_mode != "formula" or not self.product_id:
            return False
        config = self._quoter_formula_config_for_line()
        return bool(config and config.tipo_calculo != "fija")

    def _quoter_formula_product_changed(self):
        """True si el producto de la línea cambió en este onchange."""
        self.ensure_one()
        origin = self._origin
        if not origin or not origin.product_id:
            return bool(self.product_id)
        return origin.product_id != self.product_id

    def _quoter_formula_initial_volume(self, config=None):
        """Volumen inicial al crear/cambiar producto (no usa config de prueba)."""
        self.ensure_one()
        if config is None:
            config = self._quoter_formula_config_for_line()
        if config and config.tipo_calculo == "fija":
            return 0.0
        return 1.0

    def _quoter_effective_formula_volume(self):
        """Volumen usado en fórmulas: el de la línea (mín. 1 salvo horas fijas)."""
        self.ensure_one()
        vol = float(self.quoter_formula_volume or 0.0)
        if self._quoter_is_formula_variable_volume_line():
            return vol if vol > 0.0 else 1.0
        area = self._quoter_effective_tab_area()
        if area and area.hour_matrix_mode == "formula":
            config = self._quoter_formula_config_for_line()
            if config and config.tipo_calculo == "fija":
                return 0.0
        return vol

    def _quoter_write_formula_hour_columns_direct(self, range_hours):
        """Persiste columnas de horas de fórmula sin inverse (evita pisar al guardar)."""
        self.ensure_one()
        if not isinstance(self.id, int):
            return
        merged = {}
        hours_list = list(range_hours or [])[:4]
        while len(hours_list) < 4:
            hours_list.append(0.0)
        for i in range(1, 5):
            merged["quoter_range_%s_hours" % i] = float(hours_list[i - 1] or 0.0)
        total = sum(merged.values())
        assignments = ["%s = %%s" % key for key in merged]
        params = list(merged.values()) + [total, self.id]
        assignments.append("quoter_total_hours = %s")
        self.env.cr.execute(
            "UPDATE sale_order_line SET %s WHERE id = %%s" % ", ".join(assignments),
            params,
        )
        self.invalidate_cache(
            list(merged.keys()) + ["quoter_total_hours", "quoter_range_hour_ids"]
        )

    def _quoter_apply_formula_hours(self):
        """Calcula horas por rol desde configuración por fórmula y volumen de la línea."""
        FormulaConfig = self.env["quoter.formula.product.config"]
        for line in self:
            if line.quoter_is_adjustment_line:
                continue
            if line.quoter_manual_load or line.quoter_manual_total_load:
                continue
            order = line._quoter_effective_order()
            if not order or not order.is_quotation:
                continue
            if not line.product_id or not getattr(line.product_id, "is_quoter_product", False):
                continue
            area = line._quoter_effective_tab_area()
            if not area or area.hour_matrix_mode != "formula":
                continue
            tmpl = line.product_id.product_tmpl_id
            config = FormulaConfig.get_config_for_template(tmpl, area)
            if not config:
                continue
            volume = line._quoter_effective_formula_volume()
            hours_map = line._quoter_formula_hours_map_for_config(config, area, volume)
            line._quoter_sync_range_hours()
            ranges = line._quoter_first_area_ranges(limit=4)
            col_hours = []
            for area_range in ranges:
                raw = float(hours_map.get(area_range.id, 0.0))
                h = line._quoter_apply_formula_output_hours(
                    area, config, volume, raw
                )
                col_hours.append(h)
                row = line.quoter_range_hour_ids.filtered(
                    lambda hrow, a=area_range: hrow.area_range_id == a
                )[:1]
                if row:
                    if line._quoter_is_real_db_id(row.id):
                        line._quoter_range_hour_sudo().browse(row.ids).write(
                            {"hours": h}
                        )
                    else:
                        row.sudo().write({"hours": h})
            if isinstance(line.id, int):
                line._quoter_write_formula_hour_columns_direct(col_hours)
            else:
                for idx, h in enumerate(col_hours, start=1):
                    line["quoter_range_%s_hours" % idx] = h
                line.quoter_total_hours = sum(col_hours)

    def _quoter_apply_chain_hours(self):
        """Horas por rol desde tablas cadena; 0 si no hay celda para ese rol."""
        for line in self:
            if line.quoter_is_adjustment_line:
                continue
            if line.quoter_manual_load or line.quoter_manual_total_load:
                continue
            order = line._quoter_effective_order()
            if not order or not order.is_quotation:
                continue
            if not line.product_id or not getattr(
                line.product_id, "is_quoter_product", False
            ):
                continue
            area = line._quoter_effective_tab_area()
            if not area or area.hour_matrix_mode != "formula_chain":
                continue
            block = line.quoter_block_id
            if not block and line.quoter_tab_area_id:
                block = order.quoter_area_block_ids.filtered(
                    lambda b, a=line.quoter_tab_area_id: b.area_id == a
                )[:1]
            people = int(block.chain_employee_count or 1) if block else 1
            complexity_level = block.complexity_level_id if block else None
            tmpl = line.product_id.product_tmpl_id
            hours_map = area._chain_compute_hours_map_for_product(
                people, tmpl, complexity_level=complexity_level
            )
            ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))
            col_hours = [float(hours_map.get(r.id, 0.0)) for r in ranges[:4]]
            line._quoter_sync_range_hours()
            for idx, area_range in enumerate(ranges[:4]):
                h = col_hours[idx] if idx < len(col_hours) else 0.0
                row = line.quoter_range_hour_ids.filtered(
                    lambda hrow, a=area_range: hrow.area_range_id == a
                )[:1]
                if row:
                    if line._quoter_is_real_db_id(row.id):
                        line._quoter_range_hour_sudo().browse(row.ids).write(
                            {"hours": h}
                        )
                    else:
                        row.sudo().write({"hours": h})
            if isinstance(line.id, int):
                line._quoter_write_formula_hour_columns_direct(col_hours)
            else:
                for idx, h in enumerate(col_hours, start=1):
                    line["quoter_range_%s_hours" % idx] = h
                line.quoter_total_hours = sum(col_hours)

    def _quoter_apply_level_template_hours(self):
        """Copia horas de quoter.product.level.range (plantilla por nivel) a las filas de esta línea."""
        for line in self:
            if line.quoter_is_adjustment_line:
                continue
            if line.quoter_manual_load or line.quoter_manual_total_load:
                continue
            order = line._quoter_effective_order()
            if not order or not order.is_quotation:
                continue
            if not line.product_id or not getattr(line.product_id, "is_quoter_product", False):
                continue
            area = line._quoter_effective_tab_area()
            if not area:
                continue
            if area.hour_matrix_mode in ("formula", "formula_chain", "regular_manual"):
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
                h = area._apply_output_hours_minimum(tmpl_row.hours)
                row = line.quoter_range_hour_ids.filtered(
                    lambda hrow, a=ar: hrow.area_range_id == a
                )[:1]
                if row:
                    if line._quoter_is_real_db_id(row.id):
                        line._quoter_range_hour_sudo().browse(row.ids).write(
                            {"hours": h}
                        )
                    else:
                        row.sudo().write({"hours": h})

    def _quoter_product_id_domain(self):
        """Dominio de producto en cotización por área (excluye ya usados en otras líneas)."""
        order = self.order_id
        area = self.quoter_tab_area_id or self._quoter_effective_tab_area()
        if not order or not order.is_quotation or not area:
            return []
        if area.hour_matrix_mode == "formula":
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
        if area.hour_matrix_mode in ("formula_chain", "regular_manual"):
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
        self = self.with_context(quoter_allow_zero_hours=True)
        tmpl = self.product_id.product_tmpl_id if self.product_id else False
        if self.product_id and tmpl and tmpl.quoter_area_id and not self.quoter_tab_area_id:
            self.quoter_tab_area_id = tmpl.quoter_area_id
        self._compute_quoter_manual_flags()
        self._compute_quoter_can_edit_range_hours()
        self._compute_quoter_can_edit_total_hours()
        self._quoter_sync_range_hours()
        area = self._quoter_effective_tab_area()
        if not self._quoter_manual_ranges_mode() and not self._quoter_manual_total_mode():
            if area and area.hour_matrix_mode == "formula":
                cfg = (
                    self.env["quoter.formula.product.config"].get_config_for_template(
                        tmpl, area
                    )
                    if self.product_id and tmpl
                    else self.env["quoter.formula.product.config"]
                )
                product_changed = self._quoter_formula_product_changed()
                if cfg and cfg.tipo_calculo == "fija":
                    if product_changed or float(self.quoter_formula_volume or 0.0) <= 0.0:
                        self.quoter_formula_volume = 0.0
                elif product_changed or float(self.quoter_formula_volume or 0.0) <= 0.0:
                    self.quoter_formula_volume = self._quoter_formula_initial_volume(cfg)
                self._quoter_apply_formula_hours()
            elif area and area.hour_matrix_mode == "formula_chain":
                self._quoter_apply_chain_hours()
            elif area and area.hour_matrix_mode == "regular_manual":
                pass
            else:
                self._quoter_apply_level_template_hours()
        elif self._quoter_manual_ranges_mode():
            for idx in range(1, 5):
                setattr(self, "quoter_range_%s_hours" % idx, 0.0)
            self.quoter_total_hours = 0.0
        chres = self._quoter_onchange_compute_price_from_ranges()
        result = dict(chres) if isinstance(chres, dict) else {}
        result["value"] = {
            **(result.get("value") or {}),
            **self._quoter_onchange_line_client_value(),
        }
        order = self._quoter_effective_order()
        if order and order.is_quotation and self.quoter_tab_area_id:
            result.setdefault("domain", {})["product_id"] = self._quoter_product_id_domain()
        return result

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
        area = self._quoter_effective_tab_area()
        if area and area.hour_matrix_mode == "formula":
            self._quoter_apply_formula_hours()
        elif area and area.hour_matrix_mode == "formula_chain":
            self._quoter_apply_chain_hours()
        elif area and area.hour_matrix_mode == "regular_manual":
            pass
        else:
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

    def _quoter_hours_by_range_for_price(self):
        """Horas por rango para precio: O2M + columnas (form embebido / NewId)."""
        self.ensure_one()
        hours_by_range = {
            h.area_range_id.id: float(h.hours or 0.0)
            for h in self.quoter_range_hour_ids
            if h.area_range_id
        }
        ranges = self._quoter_first_area_ranges(limit=4)
        for idx, area_range in enumerate(ranges, start=1):
            col_hours = float(getattr(self, "quoter_range_%s_hours" % idx, 0.0) or 0.0)
            if col_hours:
                hours_by_range[area_range.id] = col_hours
        return hours_by_range

    def _quoter_prepare_hours_and_price(self, for_onchange=False):
        """Sincroniza horas (plantilla/manual) antes de calcular precio."""
        for line in self:
            if not line.product_id or not getattr(
                line.product_id, "is_quoter_product", False
            ):
                continue
            order = line._quoter_effective_order()
            if not order or not order.is_quotation:
                continue
            if line._quoter_manual_ranges_mode() or line.quoter_is_adjustment_line:
                if not for_onchange:
                    ctx = dict(self.env.context)
                    if line.quoter_is_adjustment_line:
                        ctx["quoter_allow_zero_hours"] = True
                    line.with_context(ctx)._quoter_sync_slots_to_hour_rows_from_columns()
                if not line.quoter_is_adjustment_line:
                    line._quoter_sync_range_hours()
            else:
                line._quoter_sync_range_hours()
                area = line._quoter_effective_tab_area()
                if not line._quoter_manual_total_mode() and not for_onchange:
                    if area and area.hour_matrix_mode == "formula":
                        line._quoter_apply_formula_hours()
                    elif area and area.hour_matrix_mode == "formula_chain":
                        line._quoter_apply_chain_hours()
                    else:
                        line._quoter_apply_level_template_hours()

    @api.onchange("quoter_formula_volume")
    def _onchange_quoter_formula_volume(self):
        self = self.with_context(quoter_allow_zero_hours=True)
        area = self._quoter_effective_tab_area()
        if not area or area.hour_matrix_mode != "formula":
            return {}
        config = self._quoter_formula_config_for_line()
        if config and config.tipo_calculo == "fija":
            return {}
        if float(self.quoter_formula_volume or 0.0) <= 0.0:
            self.quoter_formula_volume = 1.0
        # Solo recalcular en memoria; la persistencia va por RPC (form embebido).
        self._quoter_apply_formula_hours()
        price, warn = self._quoter_compute_unit_price_from_ranges()
        self.price_unit = price
        order = self._quoter_effective_order()
        if order and order.is_quotation and not self.display_type:
            self.product_uom_qty = 1.0
            self._compute_amount()
        result = dict(warn) if warn else {}
        result["value"] = {
            **self._quoter_onchange_line_client_value(),
            "quoter_formula_volume": self.quoter_formula_volume,
        }
        return result

    def _quoter_persist_formula_volume_value(self, volume=None):
        """Guarda volumen en BD de inmediato (evita onchanges encadenados que lo pisan)."""
        self.ensure_one()
        if not isinstance(self.id, int):
            return False
        area = self._quoter_effective_tab_area()
        if not area or area.hour_matrix_mode != "formula":
            return False
        config = self._quoter_formula_config_for_line()
        if config and config.tipo_calculo == "fija":
            return False
        vol = float(
            volume if volume is not None else (self.quoter_formula_volume or 0.0)
        )
        if vol <= 0.0:
            vol = 1.0
            self.quoter_formula_volume = vol
        self.with_context(
            quoter_skip_chatter_log=True,
            quoter_skip_block_product_refresh=True,
            quoter_skip_formula_vol_normalize=True,
        ).write({"quoter_formula_volume": vol})
        return True

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
        order = self._quoter_effective_order()
        if not order:
            return 0.0, False
        area = self._quoter_effective_tab_area()
        if not area:
            return 0.0, False

        ranges = self._quoter_first_area_ranges(limit=4)
        if not ranges:
            return 0.0, False
        partner = order.partner_id or self.env["res.partner"]
        pl = area.pricelist_id or order.pricelist_id
        if not pl:
            return 0.0, self._quoter_price_warning_no_pricelist()
        hours_by_range = self._quoter_hours_by_range_for_price()

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

    def _quoter_sync_slots_to_hour_rows_from_columns(self):
        """Carga manual / ajuste: persiste columnas en O2M (onchange, antes del precio)."""
        for line in self:
            if not (
                line._quoter_manual_ranges_mode() or line.quoter_is_adjustment_line
            ):
                continue
            ctx = self.env.context
            if line.quoter_is_adjustment_line:
                ctx = dict(ctx, quoter_allow_zero_hours=True)
            for idx in range(1, 5):
                line.with_context(ctx)._quoter_set_range_hours_by_index(
                    idx, getattr(line, "quoter_range_%s_hours" % idx)
                )
            if line.quoter_is_adjustment_line and line._quoter_is_real_db_id(line.id):
                line._quoter_validate_adjustment_hours_balance()

    def _quoter_onchange_line_client_value(self):
        """Valores para el form embebido: flags de edición, horas, precio y subtotal."""
        line = self[:1]
        if not line:
            return {}
        line._compute_quoter_manual_flags()
        line._compute_quoter_can_edit_range_hours()
        line._compute_quoter_can_edit_total_hours()
        line._compute_quoter_formula_is_fixed()
        values = {
            "quoter_manual_load": line.quoter_manual_load,
            "quoter_manual_total_load": line.quoter_manual_total_load,
            "quoter_formula_is_fixed": line.quoter_formula_is_fixed,
            "quoter_can_edit_range_hours": line.quoter_can_edit_range_hours,
            "quoter_can_edit_total_hours": line.quoter_can_edit_total_hours,
            "quoter_formula_volume": line.quoter_formula_volume,
            "quoter_range_1_hours": line.quoter_range_1_hours,
            "quoter_range_2_hours": line.quoter_range_2_hours,
            "quoter_range_3_hours": line.quoter_range_3_hours,
            "quoter_range_4_hours": line.quoter_range_4_hours,
            "quoter_total_hours": line.quoter_total_hours,
            "price_unit": line.price_unit,
        }
        order = line._quoter_effective_order()
        if order and order.is_quotation:
            line.product_uom_qty = 1.0
            line._compute_amount()
            values["price_subtotal"] = line.price_subtotal
        return values

    def _quoter_onchange_line_hours_value(self):
        """Alias: parche de onchange de horas/precio en línea."""
        return self._quoter_onchange_line_client_value()

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
        warn = {}
        ctx = dict(self.env.context, quoter_allow_zero_hours=True)
        for line in self.with_context(ctx):
            if not line.product_id or not getattr(line.product_id, "is_quoter_product", False):
                continue
            order = line._quoter_effective_order()
            if order and order.is_quotation:
                line._quoter_prepare_hours_and_price(for_onchange=True)
            price, w = line._quoter_compute_unit_price_from_ranges()
            area = line._quoter_effective_tab_area()
            if area and area.hour_matrix_mode == "regular_manual":
                if area.pricelist_id or (order and order.pricelist_id):
                    line.price_unit = price
            else:
                line.price_unit = price
            if order and order.is_quotation and not line.display_type:
                line.product_uom_qty = 1.0
                line._compute_amount()
            if line._quoter_manual_ranges_mode() or line.quoter_is_adjustment_line:
                line.quoter_total_hours = sum(
                    float(getattr(line, "quoter_range_%s_hours" % i, 0.0) or 0.0)
                    for i in range(1, 5)
                )
            else:
                line.quoter_total_hours = line._quoter_range_hours_sum()
            if w and not warn:
                warn = w
        result = dict(warn) if isinstance(warn, dict) else {}
        if len(self) == 1 and self.product_id:
            result["value"] = dict(
                result.get("value") or {},
                **self._quoter_onchange_line_client_value(),
            )
        return result

    def _quoter_commands_only_zero_adjustment_hours(self, commands):
        """True si los comandos O2M solo ponen hours=0 (payload espurio del form web)."""
        if not commands or not isinstance(commands, (list, tuple)):
            return False
        saw_hour_write = False
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)) or len(cmd) < 2:
                continue
            if cmd[0] == 6:
                return False
            if cmd[0] in (0, 1) and len(cmd) >= 3 and isinstance(cmd[2], dict):
                if "hours" in cmd[2]:
                    saw_hour_write = True
                    if float(cmd[2].get("hours") or 0.0) != 0.0:
                        return False
            elif cmd[0] in (2, 3, 4, 5):
                return False
        return saw_hour_write

    def _quoter_filter_stale_adjustment_hour_vals(self, line, vals):
        """Evita que el form embebido pise horas ya guardadas con ceros desincronizados."""
        if not line.quoter_is_adjustment_line:
            return vals
        if self.env.context.get("quoter_force_adjustment_hours_write"):
            return vals
        vals = dict(vals)
        hour_keys = self._QUOTER_RANGE_HOUR_FIELD_NAMES & set(vals.keys())
        for key in hour_keys:
            incoming = float(vals.get(key) or 0.0)
            stored = float(line[key] or 0.0)
            if incoming == 0.0 and stored != 0.0:
                vals.pop(key, None)
        if "quoter_range_hour_ids" in vals and self._quoter_commands_only_zero_adjustment_hours(
            vals.get("quoter_range_hour_ids")
        ):
            if any(float(line[f] or 0.0) != 0.0 for f in self._QUOTER_RANGE_HOUR_FIELD_NAMES):
                vals.pop("quoter_range_hour_ids", None)
        elif "quoter_range_hour_ids" in vals and line.quoter_is_adjustment_line:
            vals.pop("quoter_range_hour_ids", None)
        return vals

    def write(self, vals):
        """Ignora escrituras sobre líneas ya borradas (p. ej. BasicModel tras unlink en bloque)."""
        recs = self.exists()
        if not recs:
            return True
        vals = dict(vals or {})
        # Solo interesan las escrituras de CONTENIDO. Las que tocan únicamente campos
        # técnicos del sistema (p. ej. `number`, un computado almacenado que se persiste
        # solo al leerse) no son edición del usuario y no deben bloquearse.
        content_keys = set(vals.keys()) - self._QUOTER_LINE_GUARD_TECHNICAL_FIELDS
        if content_keys and not self.env.context.get("quoter_workflow_transition"):
            for line in recs:
                # La línea-total de Descuento/Recargo por área la gestiona el sistema
                # (_quoter_sync_area_discount_total_line) como efecto del socio/aprobador
                # editando los % del bloque; nunca la edita el usuario directamente (está
                # excluida del O2M del bloque). Su recálculo no debe bloquearse por el
                # estado del flujo, o el Aprobador no podría guardar Descuento %/Recargo %.
                if line.quoter_is_area_discount_total_line:
                    continue
                order = line.order_id
                if (
                    order
                    and order.is_quotation
                    and isinstance(order.id, int)
                    and not order._quoter_workflow_can_edit_content()
                ):
                    raise AccessError(
                        _(
                            "No puede modificar líneas de la cotización en el estado «%s»."
                        )
                        % order._quoter_workflow_state_label(order.quoter_workflow_state)
                    )
        adj_recs = recs.filtered("quoter_is_adjustment_line")
        if adj_recs and len(adj_recs) == len(recs) and vals:
            for line in adj_recs:
                vals = line._quoter_filter_stale_adjustment_hour_vals(line, vals)
            if not vals:
                return True
        if vals and "product_uom_qty" in vals:
            if any(line.order_id.is_quotation and not line.display_type for line in recs):
                vals = dict(vals)
                vals["product_uom_qty"] = 1.0
        if vals and "quoter_formula_volume" in vals and not self.env.context.get(
            "quoter_skip_formula_vol_normalize"
        ):
            vol_in = float(vals.get("quoter_formula_volume") or 0.0)
            if vol_in <= 0.0 and recs.filtered(
                lambda l: l._quoter_is_formula_variable_volume_line()
            ):
                vals = dict(vals)
                vals["quoter_formula_volume"] = 1.0
        log_vals = dict(vals) if vals else {}
        sync_range_cols = self._QUOTER_RANGE_HOUR_FIELD_NAMES & set(vals.keys())
        res = super(SaleOrderLine, recs).write(vals)
        if self.env.context.get("quoter_skip_quoter_line_write_hooks"):
            trigger_hours = {
                "quoter_range_1_hours",
                "quoter_range_2_hours",
                "quoter_range_3_hours",
                "quoter_range_4_hours",
                "quoter_range_hour_ids",
                "quoter_total_hours",
            }
            if set(vals or {}) & trigger_hours:
                recs.filtered(
                    "quoter_is_adjustment_line"
                )._quoter_validate_adjustment_hours_balance()
            return res
        if sync_range_cols:
            for line in recs:
                if line.quoter_is_adjustment_line:
                    line.with_context(
                        quoter_allow_zero_hours=True
                    )._quoter_sync_slots_to_hour_rows_from_columns()
                elif line._quoter_manual_ranges_mode():
                    line._quoter_sync_slots_to_hour_rows_from_columns()
        quoter_reprice = recs.filtered(
            lambda l: l._quoter_effective_order().is_quotation
            and l.product_id
            and getattr(l.product_id, "is_quoter_product", False)
        )
        prepared_from_range_cols = self.env["sale.order.line"]
        if sync_range_cols and quoter_reprice:
            for line in quoter_reprice.filtered(lambda l: not l.quoter_is_adjustment_line):
                line.with_context(self.env.context)._quoter_prepare_hours_and_price()
                prepared_from_range_cols |= line
            adj_reprice = quoter_reprice.filtered("quoter_is_adjustment_line")
            if adj_reprice:
                ctx = dict(self.env.context, quoter_allow_zero_hours=True)
                adj_reprice.with_context(ctx)._quoter_sync_slots_to_hour_rows_from_columns()
                for line in adj_reprice:
                    price, _warn = line._quoter_compute_unit_price_from_ranges()
                    super(SaleOrderLine, line).write({"price_unit": price})
                prepared_from_range_cols |= adj_reprice
        trigger_fields = {
            "product_id",
            "order_id",
            "quoter_tab_area_id",
            "quoter_formula_volume",
            "quoter_range_hour_ids",
            "quoter_range_1_hours",
            "quoter_range_2_hours",
            "quoter_range_3_hours",
            "quoter_range_4_hours",
            "quoter_total_hours",
        }
        if "quoter_formula_volume" in vals:
            formula_lines = recs.filtered(
                lambda l: l._quoter_effective_tab_area().hour_matrix_mode == "formula"
                and not l.quoter_is_adjustment_line
                and not l._quoter_manual_ranges_mode()
                and not l._quoter_manual_total_mode()
            )
            if formula_lines:
                formula_lines._quoter_apply_formula_hours()
        if set(vals.keys()) & trigger_fields:
            for line in recs.filtered(
                lambda l: l.product_id
                and getattr(l.product_id, "is_quoter_product", False)
            ):
                if not line._quoter_effective_order().is_quotation:
                    continue
                if line._quoter_is_regular_manual_line():
                    # Finanzas: precio unitario manual; las horas ya se sincronizaron
                    # arriba. No recalcular ni pisar el precio ingresado.
                    continue
                if sync_range_cols and line in prepared_from_range_cols:
                    price, _warn = line._quoter_compute_unit_price_from_ranges()
                    super(SaleOrderLine, line).write({"price_unit": price})
                    continue
                if line.quoter_is_adjustment_line:
                    ctx = dict(self.env.context, quoter_allow_zero_hours=True)
                    line.with_context(ctx)._quoter_sync_slots_to_hour_rows_from_columns()
                else:
                    line.with_context(self.env.context)._quoter_prepare_hours_and_price()
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
        low_vol = recs.filtered(
            lambda l: l._quoter_is_formula_variable_volume_line()
            and float(l.quoter_formula_volume or 0.0) <= 0.0
        )
        if low_vol and not self.env.context.get("quoter_skip_formula_vol_normalize"):
            low_vol.with_context(
                quoter_skip_formula_vol_normalize=True,
                quoter_skip_chatter_log=True,
            ).write({"quoter_formula_volume": 1.0})
            low_vol._quoter_apply_formula_hours()
            for line in low_vol:
                price, _warn = line._quoter_compute_unit_price_from_ranges()
                super(SaleOrderLine, line).write({"price_unit": price})
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
        area = self._quoter_effective_tab_area()
        if not area:
            return self.env["quoter.area.complexity.range"].browse()
        return area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:limit]

    def _quoter_ensure_range_hour_rows(self):
        """Crea filas de horas faltantes sin borrar las existentes (carga manual / onchange)."""
        for line in self:
            ranges = line._quoter_first_area_ranges(limit=4)
            if not ranges:
                continue
            keep_ids = set(ranges.ids)
            existing_rows = line.quoter_range_hour_ids
            existing_by_range = {
                h.area_range_id.id: h for h in existing_rows if h.area_range_id
            }
            in_db = isinstance(line.id, int)
            if in_db:
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
                line._quoter_range_hour_sudo().browse(
                    existing_rows.filtered(
                        lambda h: h.area_range_id.id not in keep_ids
                    ).ids
                ).unlink()
            else:
                for r in ranges:
                    if r.id not in existing_by_range:
                        line.quoter_range_hour_ids = [
                            (0, 0, {"area_range_id": r.id, "hours": 0.0})
                        ]

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

    @api.depends(
        "quoter_range_hour_ids",
        "quoter_range_hour_ids.hours",
        "quoter_range_1_hours",
        "quoter_range_2_hours",
        "quoter_range_3_hours",
        "quoter_range_4_hours",
        "quoter_is_adjustment_line",
        "quoter_manual_load",
        "quoter_tab_area_id",
        "quoter_tab_area_id.hour_matrix_mode",
    )
    def _compute_quoter_total_hours(self):
        for line in self:
            if line._quoter_manual_ranges_mode() or line.quoter_is_adjustment_line:
                line.quoter_total_hours = sum(
                    float(getattr(line, "quoter_range_%s_hours" % i, 0.0) or 0.0)
                    for i in range(1, 5)
                )
            else:
                line.quoter_total_hours = line._quoter_range_hours_sum()

    @api.depends(
        "quoter_tab_area_id",
        "quoter_tab_area_id.hour_matrix_mode",
        "quoter_range_hour_ids",
        "quoter_range_hour_ids.hours",
        "quoter_range_hour_ids.area_range_id",
        "quoter_range_hour_ids.area_range_id.sequence",
    )
    def _compute_quoter_range_hours(self):
        # Ajuste / carga manual: columnas las define el usuario; no copiar desde O2M
        # (si no, al crear filas O2M en 0 el compute almacenado pisa las columnas).
        lines = self.filtered(
            lambda l: not l._quoter_manual_ranges_mode()
            and not l.quoter_is_adjustment_line
        )
        for line in lines:
            vals = [0.0, 0.0, 0.0, 0.0]
            ranges = line._quoter_first_area_ranges(limit=4)
            if ranges:
                by_range = {
                    h.area_range_id.id: float(h.hours or 0.0)
                    for h in line.quoter_range_hour_ids
                    if h.area_range_id
                }
                for i, r in enumerate(ranges):
                    vals[i] = by_range.get(r.id, 0.0)
            line.quoter_range_1_hours = vals[0]
            line.quoter_range_2_hours = vals[1]
            line.quoter_range_3_hours = vals[2]
            line.quoter_range_4_hours = vals[3]

    def _quoter_write_adjustment_hour_columns_direct(self, hour_vals):
        """Persiste columnas de horas en ajuste sin pasar por compute/inverse del form."""
        self.ensure_one()
        if not self.quoter_is_adjustment_line or not isinstance(self.id, int):
            return
        hour_vals = dict(hour_vals or {})
        if not hour_vals:
            return
        merged = {}
        for i in range(1, 5):
            key = "quoter_range_%s_hours" % i
            if key in hour_vals:
                merged[key] = float(hour_vals[key] or 0.0)
            else:
                merged[key] = float(getattr(self, key, 0.0) or 0.0)
        total = sum(merged.values())
        assignments = ["%s = %%s" % key for key in merged]
        params = list(merged.values()) + [total, self.id]
        assignments.append("quoter_total_hours = %s")
        self.env.cr.execute(
            "UPDATE sale_order_line SET %s WHERE id = %%s"
            % ", ".join(assignments),
            params,
        )
        self.invalidate_cache(
            list(merged.keys()) + ["quoter_total_hours", "quoter_range_hour_ids"]
        )

    def _quoter_set_range_hours_by_index(self, index_1based, value):
        Policy = self.env["quoter.hours.policy"]
        for line in self:
            area = line._quoter_effective_tab_area()
            if not area:
                continue
            if line.quoter_is_adjustment_line:
                line._quoter_ensure_range_hour_rows()
            else:
                line._quoter_sync_range_hours()
            ranges = line._quoter_first_area_ranges(limit=4)
            if len(ranges) < index_1based:
                continue
            r = ranges[index_1based - 1]
            row = line.quoter_range_hour_ids.filtered(
                lambda h, ar=r: h.area_range_id == ar
            )[:1]
            hours_val = float(value or 0.0)
            if not line._quoter_should_validate_hours_on_edit():
                pass
            elif line.quoter_is_adjustment_line:
                pass
            elif line._quoter_manual_ranges_mode():
                if line._quoter_is_new_line_record():
                    hours_val = Policy.validate_hours_non_negative(
                        hours_val, _("Horas")
                    )
                else:
                    hours_val = Policy.validate_hours_non_negative(
                        hours_val, _("Horas")
                    )
            elif hours_val < 0.0:
                raise ValidationError(_("Las horas no pueden ser negativas."))
            if row:
                # browse().write no actualiza filas O2M en NewId; usar el recordset en memoria.
                row_ctx = self.env.context
                if line.quoter_is_adjustment_line:
                    row_ctx = dict(row_ctx, quoter_allow_zero_hours=True)
                if self._quoter_is_real_db_id(row.id):
                    line._quoter_range_hour_sudo().browse(row.ids).with_context(
                        row_ctx
                    ).write({"hours": hours_val})
                else:
                    row.with_context(row_ctx).sudo().write({"hours": hours_val})
                continue
            create_ctx = self.env.context
            if line.quoter_is_adjustment_line:
                create_ctx = dict(create_ctx, quoter_allow_zero_hours=True)
            if isinstance(line.id, int):
                line.with_context(create_ctx)._quoter_range_hour_sudo().create(
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

    @api.depends(
        "product_id",
        "quoter_tab_area_id",
        "quoter_area_id",
        "product_id.product_tmpl_id",
    )
    def _compute_quoter_manual_flags(self):
        for line in self:
            qsl = line._quoter_service_line()
            line.quoter_manual_load = bool(qsl and getattr(qsl, "manual_load", False))
            line.quoter_manual_total_load = bool(
                qsl and getattr(qsl, "manual_total_load", False)
            )

    @api.depends(
        "order_id.is_quotation",
        "product_id",
        "product_id.product_tmpl_id.is_quoter_product",
        "quoter_manual_load",
        "quoter_manual_total_load",
        "quoter_is_adjustment_line",
        "quoter_block_id",
        "quoter_tab_area_id",
        "quoter_tab_area_id.hour_matrix_mode",
    )
    def _compute_quoter_can_edit_range_hours(self):
        for line in self:
            order = line._quoter_effective_order()
            if line.quoter_is_adjustment_line and order.is_quotation:
                line.quoter_can_edit_range_hours = True
            elif line._quoter_manual_ranges_mode() and order and order.is_quotation:
                line.quoter_can_edit_range_hours = True
            else:
                line.quoter_can_edit_range_hours = False

    @api.depends(
        "order_id.is_quotation",
        "product_id",
        "product_id.product_tmpl_id.is_quoter_product",
        "quoter_manual_total_load",
        "quoter_tab_area_id",
        "quoter_is_adjustment_line",
        "quoter_block_id",
    )
    def _compute_quoter_can_edit_total_hours(self):
        for line in self:
            order = line._quoter_effective_order()
            if line.quoter_is_adjustment_line and order.is_quotation:
                line.quoter_can_edit_total_hours = False
            elif (
                line._quoter_manual_total_mode() and line._quoter_is_new_line_record()
            ):
                line.quoter_can_edit_total_hours = True
            else:
                line.quoter_can_edit_total_hours = False

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
            value = Policy.validate_hours_non_negative(
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
            price, _warn = line._quoter_compute_unit_price_from_ranges()
            line.price_unit = price

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
            "price_unit": _("Precio unitario"),
            "quoter_manual_load": _("Carga manual por rol"),
            "quoter_manual_total_load": _("Carga manual total"),
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
        else:
            block = self._quoter_block_for_tab_area()
            if block:
                adj_vals["quoter_block_id"] = block.id
        new_line = self.with_context(quoter_allow_zero_hours=True).create(adj_vals)
        if not new_line.quoter_block_id:
            new_line._quoter_sync_line_block_link()
        new_line._quoter_sync_range_hours()
        for rh in new_line.quoter_range_hour_ids:
            rh.with_context(quoter_allow_zero_hours=True).write({"hours": 0.0})
        new_line._quoter_onchange_compute_price_from_ranges()
        return new_line.id

    def _quoter_workflow_content_edit_blocked(self):
        """True si esta línea pertenece a una cotización cuyo contenido el usuario no puede
        editar (p. ej. Aprobador en «En aprobación»/«Aprobado interno»).

        Los persist-batch que dispara el cliente (horas/volumen/precio) deben SALTAR estas
        líneas en lugar de intentar escribir: ese perfil no puede editar ese contenido, y el
        cliente los reenvía sin cambios al abrir el bloque para tocar solo Descuento %/Recargo %.
        """
        self.ensure_one()
        order = self.order_id
        return bool(
            order
            and order.is_quotation
            and isinstance(order.id, int)
            and not order._quoter_workflow_can_edit_content()
        )

    @api.model
    def quoter_persist_adjustment_line_hours_batch(self, payloads):
        """Persiste horas de columnas en líneas de ajuste (form embebido antes de guardar)."""
        if not payloads:
            return True
        hour_fields = self._QUOTER_RANGE_HOUR_FIELD_NAMES
        ctx = dict(
            self.env.context,
            quoter_allow_zero_hours=True,
            quoter_skip_chatter_log=True,
            quoter_skip_block_product_refresh=True,
            quoter_force_adjustment_hours_write=True,
            quoter_skip_quoter_line_write_hooks=True,
        )
        Line = self.env["sale.order.line"].with_context(ctx)
        for item in payloads:
            if not isinstance(item, dict):
                continue
            line_id = item.get("id")
            if not line_id:
                continue
            line = Line.browse(int(line_id)).exists()
            if not line or not line.quoter_is_adjustment_line:
                continue
            if line._quoter_workflow_content_edit_blocked():
                continue
            hour_vals = {
                key: float(item[key] or 0.0)
                for key in hour_fields
                if key in item
            }
            note = (item.get("quoter_adjustment_note") or "").strip()
            if not hour_vals and not note:
                continue
            if hour_vals:
                line._quoter_write_adjustment_hour_columns_direct(hour_vals)
                line._quoter_sync_slots_to_hour_rows_from_columns()
                price, _warn = line._quoter_compute_unit_price_from_ranges()
                line.with_context(ctx).write({"price_unit": price})
            if note:
                line.with_context(ctx).write({"quoter_adjustment_note": note})
            line._quoter_validate_adjustment_hours_balance()
        return True

    @api.model
    def quoter_persist_formula_volume_batch(self, payloads):
        """Persiste volumen fórmula desde el form embebido (antes de guardar el bloque)."""
        if not payloads:
            return True
        ctx = dict(
            quoter_skip_chatter_log=True,
            quoter_skip_block_product_refresh=True,
            quoter_skip_formula_vol_normalize=True,
        )
        Line = self.env["sale.order.line"].with_context(ctx)
        for item in payloads:
            if not isinstance(item, dict):
                continue
            line_id = item.get("id")
            if not line_id or "quoter_formula_volume" not in item:
                continue
            line = Line.browse(int(line_id)).exists()
            if not line or line.quoter_is_adjustment_line:
                continue
            if line._quoter_workflow_content_edit_blocked():
                continue
            area = line._quoter_effective_tab_area()
            if not area or area.hour_matrix_mode != "formula":
                continue
            if not line._quoter_persist_formula_volume_value(
                item.get("quoter_formula_volume")
            ):
                continue
            price, _warn = line._quoter_compute_unit_price_from_ranges()
            line.with_context(ctx).write({"price_unit": price})
        return True

    @api.model
    def quoter_persist_regular_manual_line_edits_batch(self, payloads):
        """Persiste horas por rango (y precio unitario en Finanzas) de líneas con carga
        manual de horas desde el form embebido antes de guardar el bloque.

        Aplica a líneas con `_quoter_manual_ranges_mode()`: área Finanzas (regular_manual)
        o producto configurado en quoter.service.line con `manual_load = True` en cualquier
        área. En Finanzas el precio unitario es manual y se respeta; en el resto el precio
        se recalcula desde la tarifa según las horas (lo hace `write()`).
        """
        if not payloads:
            return True
        hour_fields = self._QUOTER_RANGE_HOUR_FIELD_NAMES
        ctx = dict(
            self.env.context,
            quoter_skip_chatter_log=True,
            quoter_skip_block_product_refresh=True,
        )
        Line = self.env["sale.order.line"].with_context(ctx)
        for item in payloads:
            if not isinstance(item, dict):
                continue
            line_id = item.get("id")
            if not line_id:
                continue
            line = Line.browse(int(line_id)).exists()
            if not line or not line._quoter_manual_ranges_mode():
                continue
            if line._quoter_workflow_content_edit_blocked():
                continue
            write_vals = {}
            for key in hour_fields:
                if key in item and item[key] is not None:
                    write_vals[key] = float(item[key] or 0.0)
            if (
                "price_unit" in item
                and item["price_unit"] is not None
                and line._quoter_is_regular_manual_line()
            ):
                # El precio manual solo se respeta en Finanzas (regular_manual); en el
                # resto lo recalcula write() desde la tarifa según las horas.
                write_vals["price_unit"] = float(item["price_unit"] or 0.0)
            if not write_vals:
                continue
            line.with_context(ctx).write(write_vals)
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

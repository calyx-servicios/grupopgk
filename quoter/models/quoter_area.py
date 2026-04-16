# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class QuoterProfessionalArea(models.Model):
    _name = "quoter.professional.area"
    _description = "Área / sector profesional"
    _order = "sequence, name, id"

    name = fields.Char(string="Nombre", required=True, translate=True)
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
        help="Orden de pestañas del cotizador (1=Área en pestaña 1, 2=pestaña 2, etc.).",
    )
    active = fields.Boolean(default=True)

    cerrado = fields.Boolean(
        string="Cerrado (en cotizaciones)",
        default=False,
        groups="quoter.group_quoter_manager",
        help="Si está marcado, el área puede elegirse en pedidos/cotizaciones (campo Áreas). "
        "No bloquea la edición: use «Abrir editor de tabla» / «Cerrar editor de tabla» para eso.",
    )
    quoter_config_edit_mode = fields.Boolean(
        string="Configuración editable",
        default=False,
        help="Cuando está activo, se pueden cambiar la política de matrices, las líneas del "
        "cotizador y la matriz de horas. Al guardar con el botón correspondiente se recalcula "
        "y se vuelve a bloquear.",
    )
    quoter_config_complete = fields.Boolean(
        string="Configuración completa",
        compute="_compute_quoter_config_complete",
        help="True cuando secuencia, rangos y niveles están configurados.",
    )

    group_id = fields.Many2one(
        comodel_name="res.groups",
        string="Visibilidad (grupo)",
        help="Si se define, solo usuarios de este grupo ven este sector, las líneas "
        "del cotizador y los productos asociados.",
    )

    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Lista de Precios",
        ondelete="restrict",
        help="Lista de precios usada al cotizar pedidos con productos de esta área.",
    )
    product_category_id = fields.Many2one(
        comodel_name="product.category",
        string="Categoría",
        ondelete="restrict",
        help="Categoría por defecto para los productos del cotizador de esta área.",
    )

    separator_tag_ids = fields.Many2many(
        comodel_name="quoter.line.separator.tag",
        relation="quoter_professional_area_separator_tag_rel",
        column1="area_id",
        column2="separator_tag_id",
        string="Etiquetas separador",
        help="Etiquetas reutilizables entre áreas; sirven para agrupar y dar color en el cotizador.",
    )
    separator_visual_mode = fields.Selection(
        selection=[
            ("none", "Sin color"),
            ("full", "Línea completa con color"),
        ],
        string="Visual separadores",
        default="none",
        required=True,
        help="Cómo se muestran los separadores de etiquetas en las líneas del pedido.",
    )

    complexity_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        relation="quoter_professional_area_complexity_level_rel",
        column1="area_id",
        column2="complexity_level_id",
        string="Niveles de complejidad",
        help="Bajo, medio, alto, etc.: definen variantes de producto y colores en el pedido.",
    )

    area_range_ids = fields.Many2many(
        comodel_name="quoter.area.complexity.range",
        relation="quoter_professional_area_range_rel",
        column1="area_id",
        column2="range_id",
        string="Rangos del área",
        help="Rangos disponibles para esta área. Se crean desde el menú de rangos.",
    )

    hour_matrix_mode = fields.Selection(
        selection=[
            ("regular", "Regular"),
            ("combined", "Combinada"),
        ],
        string="Tipo de tabla de horas",
        default="regular",
        required=True,
        help="Regular: se cargan horas finales por producto y nivel. "
        "Combinada: horas base (tabla A) y factor (tabla B) según el formato y tipo definidos aquí.",
    )
    table_a_layout = fields.Selection(
        selection=[
            ("normal", "Celdas por rango"),
            ("compact", "Unificada (un valor para todos los rangos)"),
        ],
        string="Formato tabla A",
        default="normal",
        required=True,
        help="Unificada: un solo campo en la pantalla de matrices replica A en los cuatro rangos.",
    )
    table_b_kind = fields.Selection(
        selection=[
            ("percent", "Porcentaje (sobre A)"),
            ("multiplier", "Multiplicador"),
            ("formula", "Fórmula (próximamente)"),
        ],
        string="Tipo tabla B",
        default="percent",
        required=True,
        help="Porcentaje: final = A × (B ÷ 100). Multiplicador: final = A × B. "
        "Fórmula: por ahora final = A.",
    )

    line_ids = fields.One2many(
        comodel_name="quoter.service.line",
        inverse_name="area_id",
        string="Líneas del cotizador",
    )

    line_count = fields.Integer(compute="_compute_line_counts", string="Líneas")
    quoter_product_count = fields.Integer(
        compute="_compute_line_counts",
        string="Productos cotizador",
    )

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Permite a usuarios con listas de precios elegir áreas aunque group_id restrinja."""
        args = args or []
        if self.env.user.has_group("product.group_sale_pricelist"):
            return super(QuoterProfessionalArea, self.sudo()).name_search(
                name=name, args=args, operator=operator, limit=limit
            )
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    @api.depends("line_ids", "line_ids.product_tmpl_id")
    def _compute_line_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.quoter_product_count = len(rec.line_ids.mapped("product_tmpl_id"))

    @api.depends("sequence", "area_range_ids", "complexity_level_ids")
    def _compute_quoter_config_complete(self):
        for rec in self:
            rec.quoter_config_complete = bool(
                rec.sequence and rec.area_range_ids and rec.complexity_level_ids
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "quoter_config_edit_mode" not in vals:
                vals["quoter_config_edit_mode"] = True
        areas = super().create(vals_list)
        areas._sync_range_rate_products()
        return areas

    def _sync_range_rate_products(self):
        Template = self.env["product.template"]
        hour_uom = self.env.ref("uom.product_uom_hour")
        all_categ = self.env.ref("product.product_category_all")
        for area in self:
            ranges = area.area_range_ids
            keep_range_ids = set(ranges.ids)
            existing = Template.search(
                [
                    ("is_quoter_range_rate_product", "=", True),
                    ("quoter_range_rate_area_id", "=", area.id),
                ]
            )
            for tmpl in existing:
                rid = tmpl.quoter_range_rate_range_id.id
                if rid and rid not in keep_range_ids:
                    tmpl.active = False
            for r in ranges:
                tmpl = Template.search(
                    [
                        ("is_quoter_range_rate_product", "=", True),
                        ("quoter_range_rate_area_id", "=", area.id),
                        ("quoter_range_rate_range_id", "=", r.id),
                    ],
                    limit=1,
                )
                if tmpl:
                    if not tmpl.active:
                        tmpl.active = True
                    continue
                categ = area.product_category_id or all_categ
                tmpl = Template.create(
                    {
                        "name": _("%s · %s · Tarifa/h") % (area.name, r.name),
                        "type": "service",
                        "is_quoter_range_rate_product": True,
                        "quoter_range_rate_area_id": area.id,
                        "quoter_range_rate_range_id": r.id,
                        "sale_ok": True,
                        "purchase_ok": False,
                        "categ_id": categ.id,
                        "uom_id": hour_uom.id,
                        "uom_po_id": hour_uom.id,
                        "list_price": 0.0,
                    }
                )
                Template.quoter_apply_default_sale_taxes(tmpl)

    def write(self, vals):
        policy_fields = ("hour_matrix_mode", "table_a_layout", "table_b_kind")
        snapshots = {rec.id: {f: rec[f] for f in policy_fields} for rec in self}
        rebuild_separator_sections = "separator_visual_mode" in vals
        res = super().write(vals)
        for rec in self:
            before = snapshots[rec.id]
            after = {f: rec[f] for f in policy_fields}
            if before != after:
                rec._apply_hour_policy_to_level_ranges(before, after)
        if "area_range_ids" in vals:
            for area in self:
                area.line_ids._sync_range_hour_lines()
            self._sync_range_rate_products()
            self._sync_product_level_range_hour_lines()
        if "complexity_level_ids" in vals or "product_category_id" in vals:
            for area in self:
                area.line_ids._ensure_quoter_product()
                # Crear configuraciones por nivel para productos existentes del área.
                area.line_ids._sync_product_level_ranges()
        if rebuild_separator_sections:
            SaleLine = self.env["sale.order.line"]
            orders = self.env["sale.order"].search(
                [
                    ("is_quotation", "=", True),
                    ("order_line.quoter_tab_area_id", "in", self.ids),
                ]
            )
            if orders:
                SaleLine.with_context(quoter_skip_separator_rebuild=True)._quoter_rebuild_separator_sections_for_orders(
                    orders
                )
        return res

    def _apply_hour_policy_to_level_ranges(self, before, after):
        """Propaga cambios de política de horas a todas las plantillas nivel×producto del área."""
        self.ensure_one()
        LevelRange = self.env["quoter.product.level.range"]
        lrs = LevelRange.search([("area_id", "=", self.id)])

        if after["hour_matrix_mode"] == "regular":
            for lr in lrs:
                lr.output_line_ids.write({"matrix_a_id": False})
            lrs.mapped("matrix_a_ids").unlink()
            lrs.mapped("matrix_b_ids").unlink()
            return

        became_combined = (
            before["hour_matrix_mode"] != "combined"
            and after["hour_matrix_mode"] == "combined"
        )
        if became_combined:
            for lr in lrs:
                lr._prepare_combined_defaults_from_final_hours()

        if after["table_b_kind"] != before["table_b_kind"]:
            for lr in lrs:
                lr._apply_table_b_kind_default_factors(
                    after["table_b_kind"], after["table_a_layout"]
                )

        if (
            after["table_a_layout"] == "compact"
            and before["table_a_layout"] != "compact"
        ):
            for lr in lrs:
                lr._unify_hours_a_compact_from_first_row()
                lr._normalize_matrix_b_for_percent_split_if_needed()

        lrs._apply_combined_final_all()

    def _sync_product_level_range_hour_lines(self):
        """Filas B / A / salida en plantillas quoter.product.level.range al cambiar rangos del área."""
        lr = self.env["quoter.product.level.range"].search([("area_id", "in", self.ids)])
        lr._sync_matrix_rows()

    def _complexity_levels_ordered(self):
        """Niveles asignados al área ordenados por secuencia (menor → mayor) e id."""
        self.ensure_one()
        return self.complexity_level_ids.sorted(key=lambda lev: (lev.sequence, lev.id))

    def get_hours_matrix_preview_data(self):
        """Datos para la matriz JS del formulario de área (horas resultado por producto / nivel / rango)."""
        self.ensure_one()
        can_edit_matrix = self.env.user.has_group("quoter.group_quoter_manager")
        matrix_read_only = not self.quoter_config_edit_mode or not can_edit_matrix
        ranges = self.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))
        levels = self._complexity_levels_ordered()
        mode_meta = self.fields_get(["hour_matrix_mode"])["hour_matrix_mode"]
        mode_label = dict(mode_meta["selection"]).get(self.hour_matrix_mode, "")
        labels = {
            "complexity": _("COMPLEJIDAD (en Hrs por tarea)"),
            "task": _("TAREA"),
            "mode": mode_label,
        }
        if not ranges or not levels:
            return {
                "labels": labels,
                "area_id": self.id,
                "matrix_read_only": matrix_read_only,
                "hour_matrix_mode": self.hour_matrix_mode,
                "table_a_layout": self.table_a_layout,
                "table_b_kind": self.table_b_kind,
                "show_matrix_ab": False,
                "range_ids": [],
                "ranges": [],
                "levels": [],
                "rows": [],
                "empty_message": _("Defina rangos del área y niveles de complejidad."),
            }
        LevelRange = self.env["quoter.product.level.range"]
        combined = self.hour_matrix_mode == "combined"
        compact_a = self.table_a_layout == "compact"
        b_kind_meta = self.fields_get(["table_b_kind"])["table_b_kind"]
        b_kind_label = dict(b_kind_meta["selection"]).get(self.table_b_kind, "")
        labels["output_title"] = _("Salida (horas resultado)")
        labels["matrix_a_title"] = _("Tabla A (horas base)")
        labels["matrix_b_title"] = _("Tabla B (%s)") % (b_kind_label or self.table_b_kind)
        if not self.quoter_config_edit_mode:
            labels["matrix_edit_hint"] = _(
                "Pulse «Abrir editor de tabla» en la cabecera del área para modificar la matriz. "
                "(Solo el grupo Quoter - Gerente.)"
            )
        rows_out = []
        for line in self.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            if not line.product_tmpl_id:
                continue
            tmpl_id = line.product_tmpl_id.id
            levels_hours = []
            levels_matrix_a = []
            levels_matrix_b = []
            levels_meta = []
            for lev in levels:
                lr = LevelRange.search(
                    [
                        ("product_tmpl_id", "=", tmpl_id),
                        ("complexity_level_id", "=", lev.id),
                        ("area_id", "=", self.id),
                    ],
                    limit=1,
                )
                zr = [0.0] * len(ranges)
                if not lr:
                    levels_hours.append(list(zr))
                    levels_matrix_a.append([0.0] if compact_a else list(zr))
                    levels_matrix_b.append(list(zr))
                    levels_meta.append(
                        {
                            "level_range_id": False,
                            "output_ids": [0] * len(ranges),
                            "matrix_a_ids": [0] * len(ranges),
                            "matrix_b_ids": [0] * len(ranges),
                        }
                    )
                    continue
                out_by_range = {
                    o.area_range_id.id: float(o.hours or 0.0) for o in lr.output_line_ids
                }
                levels_hours.append([round(out_by_range.get(r.id, 0.0), 2) for r in ranges])
                a_by_range = {
                    a.area_range_id.id: float(a.hours or 0.0) for a in lr.matrix_a_ids
                }
                if compact_a:
                    av = 0.0
                    if ranges:
                        av = float(a_by_range.get(ranges[0].id, 0.0) or 0.0)
                    if not av and a_by_range:
                        av = float(next(iter(a_by_range.values())))
                    levels_matrix_a.append([round(av, 2)])
                else:
                    levels_matrix_a.append([round(a_by_range.get(r.id, 0.0), 2) for r in ranges])
                b_by_range = {
                    b.area_range_id.id: float(b.factor or 0.0) for b in lr.matrix_b_ids
                }
                levels_matrix_b.append([round(b_by_range.get(r.id, 0.0), 2) for r in ranges])
                output_ids = []
                matrix_a_ids = []
                matrix_b_ids = []
                for r in ranges:
                    orec = lr.output_line_ids.filtered(lambda o, ar=r: o.area_range_id == ar)[:1]
                    output_ids.append(orec.id if orec else 0)
                    arec = lr.matrix_a_ids.filtered(lambda a, ar=r: a.area_range_id == ar)[:1]
                    matrix_a_ids.append(arec.id if arec else 0)
                    brec = lr.matrix_b_ids.filtered(lambda b, ar=r: b.area_range_id == ar)[:1]
                    matrix_b_ids.append(brec.id if brec else 0)
                levels_meta.append(
                    {
                        "level_range_id": lr.id,
                        "output_ids": output_ids,
                        "matrix_a_ids": matrix_a_ids,
                        "matrix_b_ids": matrix_b_ids,
                    }
                )
            rows_out.append(
                {
                    "line_name": line.name or line.product_tmpl_id.display_name,
                    "levels_hours": levels_hours,
                    "levels_matrix_a": levels_matrix_a,
                    "levels_matrix_b": levels_matrix_b,
                    "levels_meta": levels_meta,
                }
            )
        return {
            "labels": labels,
            "area_id": self.id,
            "matrix_read_only": matrix_read_only,
            "hour_matrix_mode": self.hour_matrix_mode,
            "table_a_layout": self.table_a_layout,
            "table_b_kind": self.table_b_kind,
            "show_matrix_ab": combined,
            "range_ids": [r.id for r in ranges],
            "ranges": [{"name": r.name} for r in ranges],
            "levels": [{"name": lev.name, "color": int(lev.color or 0)} for lev in levels],
            "rows": rows_out,
            "empty_message": _("No hay líneas con producto asociado."),
        }

    def matrix_preview_write_cell(self, level_range_id, area_range_id, write_kind, value):
        """Persistir celda desde la matriz JS (salida en regular; A y B en combinada)."""
        self.ensure_one()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(_("Solo el grupo Quoter - Gerente puede editar la matriz."))
        if not self.quoter_config_edit_mode:
            raise UserError(
                _(
                    "La configuración del área está bloqueada: solo un usuario del grupo "
                    "Quoter - Gerente puede abrir el editor de tabla desde la cabecera del área."
                )
            )
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise UserError(_("Valor numérico no válido.")) from None

        LevelRange = self.env["quoter.product.level.range"]
        lr = LevelRange.search(
            [
                ("id", "=", int(level_range_id)),
                ("area_id", "=", self.id),
            ],
            limit=1,
        )
        if not lr:
            raise UserError(_("Plantilla de nivel no válida para esta área."))

        ar_id = int(area_range_id)
        ar_rec = self.env["quoter.area.complexity.range"].browse(ar_id)
        if not ar_rec or ar_rec not in self.area_range_ids:
            raise UserError(_("El rango no pertenece al área."))

        combined = self.hour_matrix_mode == "combined"
        compact_a = self.table_a_layout == "compact"

        if write_kind == "output":
            if combined:
                raise UserError(
                    _("En modo combinado la salida se calcula desde las tablas A y B; edite esas tablas.")
                )
            out = lr.output_line_ids.filtered(lambda o: o.area_range_id.id == ar_id)[:1]
            if not out:
                raise UserError(_("No hay línea de salida para ese rango."))
            try:
                out.write({"hours": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            return True

        if write_kind == "matrix_a_compact":
            if not combined:
                raise UserError(_("La tabla A solo aplica en modo combinado."))
            if not lr.matrix_a_ids:
                raise UserError(_("No hay filas de tabla A para este nivel."))
            try:
                lr.matrix_a_ids.write({"hours": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            return True

        if write_kind == "matrix_a":
            if not combined:
                raise UserError(_("La tabla A solo aplica en modo combinado."))
            if compact_a:
                raise UserError(_("Use la celda unificada de tabla A para este formato."))
            arow = lr.matrix_a_ids.filtered(lambda a: a.area_range_id.id == ar_id)[:1]
            if not arow:
                raise UserError(_("No hay fila de tabla A para ese rango."))
            try:
                arow.write({"hours": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            return True

        if write_kind == "matrix_b":
            if not combined:
                raise UserError(_("La tabla B solo aplica en modo combinado."))
            brow = lr.matrix_b_ids.filtered(lambda b: b.area_range_id.id == ar_id)[:1]
            if not brow:
                raise UserError(_("No hay fila de tabla B para ese rango."))
            try:
                brow.write({"factor": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            return True

        raise UserError(_("Tipo de escritura no reconocido."))

    def action_open_quoter_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Líneas del cotizador"),
            "res_model": "quoter.service.line",
            "view_mode": "tree,form",
            "domain": [("area_id", "=", self.id)],
            "context": dict(self.env.context, default_area_id=self.id),
        }

    def action_open_quoter_products(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Productos del cotizador"),
            "res_model": "product.product",
            "view_mode": "tree,form",
            "domain": [
                ("product_tmpl_id.quoter_area_id", "=", self.id),
                ("is_quoter_range_rate_product", "=", False),
            ],
            "context": self.env.context,
        }

    def _quoter_validate_config_before_lock(self):
        """Exige reglas al cerrar edición (p. ej. % B que sumen 100 en A unificada + B porcentaje)."""
        self.ensure_one()
        lrs = self.env["quoter.product.level.range"].search([("area_id", "=", self.id)])
        split = lrs.filtered(lambda r: r._matrix_b_percent_split_mode())
        if split:
            split._validate_matrix_b_percent_split_total_on_save()

    def _quoter_recompute_after_config_save(self):
        """Tras validar: recalcular horas de salida en modo combinado (A×B). Solo desde «Cerrar editor de tabla»."""
        self.ensure_one()
        if self.hour_matrix_mode != "combined":
            return
        lrs = self.env["quoter.product.level.range"].search([("area_id", "=", self.id)])
        lrs._apply_combined_final_all()

    def action_quoter_area_unlock_config(self):
        self.ensure_one()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(
                _("Solo los usuarios del grupo Quoter - Gerente pueden abrir o cerrar el editor de tabla.")
            )
        self.write({"quoter_config_edit_mode": True})
        return True

    def action_quoter_area_lock_config(self):
        self.ensure_one()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(
                _("Solo los usuarios del grupo Quoter - Gerente pueden abrir o cerrar el editor de tabla.")
            )
        self._quoter_validate_config_before_lock()
        self._quoter_recompute_after_config_save()
        self.write({"quoter_config_edit_mode": False})
        # True recarga el formulario en el cliente web (display_notification suele fallar en botones type="object").
        return True

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

from .quoter_chatter import quoter_chatter_collect_changes, quoter_chatter_should_log


class QuoterSaleOrderArea(models.Model):
    _name = "quoter.sale.order.area"
    _description = "Bloque de cotización por área en pedido"
    _order = "sequence, area_id, id"

    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Pedido",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área",
        required=True,
        ondelete="restrict",
        index=True,
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=1,
        help="Orden del bloque respecto de otras áreas en el mismo pedido (1 = primero).",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Abierto"),
            ("published", "Cerrado"),
            ("cancel", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        copy=False,
    )
    complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel de complejidad",
        ondelete="set null",
    )
    complexity_level_frozen = fields.Boolean(
        string="Nivel bloqueado",
        default=False,
        copy=False,
        help="Tras guardar el nivel en una cotización ya persistida, no puede modificarse.",
    )
    branch_id = fields.Many2one(
        comodel_name="quoter.area.branch",
        string="Rama",
        ondelete="set null",
    )
    area_branch_ids = fields.Many2many(
        comodel_name="quoter.area.branch",
        related="area_id.branch_ids",
        string="Ramas del área",
        readonly=True,
    )
    area_use_branching = fields.Boolean(
        related="area_id.use_branching",
        string="Área usa ramas",
        readonly=True,
    )
    area_is_tax = fields.Boolean(
        string="Área TAX",
        related="area_id.is_tax_area",
        readonly=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="order_id.currency_id",
        string="Moneda",
        readonly=True,
    )
    quoter_user_is_assigned_manager = fields.Boolean(
        related="order_id.quoter_user_is_assigned_manager",
        string="Usuario es manager asignado",
        readonly=True,
    )
    quoter_user_is_assigned_partner = fields.Boolean(
        related="order_id.quoter_user_is_assigned_partner",
        string="Usuario es socio asignado",
        readonly=True,
    )
    global_discount_amount = fields.Float(
        string="Descuento % (área)",
        default=0.0,
        digits=(16, 4),
        help="Porcentaje de descuento del socio sobre el subtotal del área (productos + ajustes de línea).",
    )
    global_surcharge_amount = fields.Float(
        string="Recargo % (área)",
        default=0.0,
        digits=(16, 4),
        help="Porcentaje de aumento del socio sobre el subtotal del área (productos + ajustes de línea).",
    )
    area_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        related="area_id.complexity_level_ids",
        string="Niveles del área",
        readonly=True,
    )
    complexity_level_custom_label = fields.Char(
        related="area_id.complexity_level_custom_label",
        readonly=True,
    )
    area_allow_change_complexity_level = fields.Boolean(
        related="area_id.allow_change_complexity_level",
        readonly=True,
    )
    complexity_level_change_allowed = fields.Boolean(
        string="Puede cambiar nivel",
        compute="_compute_complexity_level_change_allowed",
    )

    order_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="quoter_block_id",
        string="Líneas de cotización",
        copy=False,
        domain=[("quoter_is_area_discount_total_line", "=", False)],
    )

    selectable_product_ids = fields.Many2many(
        comodel_name="product.product",
        compute="_compute_selectable_product_ids",
        string="Productos seleccionables",
    )

    block_editable = fields.Boolean(
        string="Bloque editable",
        compute="_compute_block_lock_flags",
    )
    structure_locked = fields.Boolean(
        string="Estructura bloqueada",
        compute="_compute_block_lock_flags",
    )
    lines_frozen = fields.Boolean(
        string="Líneas congeladas",
        compute="_compute_block_lock_flags",
    )

    caption_products = fields.Char(compute="_compute_footer_captions")
    caption_adjustments = fields.Char(compute="_compute_footer_captions")
    caption_discount = fields.Char(compute="_compute_footer_captions")
    caption_surcharge = fields.Char(compute="_compute_footer_captions")
    caption_total = fields.Char(compute="_compute_footer_captions")

    product_untaxed = fields.Monetary(
        string="Subtotal productos",
        compute="_compute_area_financials",
        currency_field="currency_id",
    )
    adjustment_untaxed = fields.Monetary(
        string="Subtotal ajustes",
        compute="_compute_area_financials",
        currency_field="currency_id",
    )
    discount_line_amount = fields.Monetary(
        string="Descuento área",
        compute="_compute_area_financials",
        currency_field="currency_id",
    )
    surcharge_line_amount = fields.Monetary(
        string="Recargo área",
        compute="_compute_area_financials",
        currency_field="currency_id",
    )
    total_untaxed = fields.Monetary(
        string="Total área",
        compute="_compute_area_financials",
        currency_field="currency_id",
    )

    area_summary_html = fields.Html(
        string="Resumen horas/tarifas",
        compute="_compute_area_summary_html",
        sanitize=False,
    )

    _sql_constraints = [
        (
            "quoter_sale_order_area_order_area_uniq",
            "unique(order_id, area_id)",
            "Ya existe un bloque para esta área en el pedido.",
        ),
    ]

    @api.constrains("complexity_level_id", "area_id")
    def _check_complexity_in_area(self):
        for rec in self:
            if rec.complexity_level_id and rec.complexity_level_id not in rec.area_id.complexity_level_ids:
                raise ValidationError(
                    _("El nivel debe pertenecer a los niveles configurados en el área «%s».")
                    % rec.area_id.display_name
                )

    @api.constrains("branch_id", "area_id")
    def _check_branch_in_area(self):
        for rec in self:
            if not rec.area_id:
                continue
            if rec.branch_id and rec.branch_id not in rec.area_id._effective_branch_ids():
                raise ValidationError(
                    _("La rama debe pertenecer a las ramas configuradas en el área «%s».")
                    % rec.area_id.display_name
                )

    @api.constrains("global_discount_amount", "global_surcharge_amount")
    def _check_non_negative_adjustments(self):
        for rec in self:
            if (rec.global_discount_amount or 0.0) < 0.0:
                raise ValidationError(_("El descuento (%) del área no puede ser negativo."))
            if (rec.global_surcharge_amount or 0.0) < 0.0:
                raise ValidationError(_("El recargo (%) del área no puede ser negativo."))

    @api.onchange("area_id")
    def _onchange_area_id_clear_level(self):
        if not self.area_id:
            return
        if self.complexity_level_id and self.complexity_level_id not in self.area_id.complexity_level_ids:
            self.complexity_level_id = False
        if not self.branch_id or self.branch_id not in self.area_id._effective_branch_ids():
            self.branch_id = self.area_id._resolve_matrix_branch()

    def _quoter_default_service_lines(self):
        """Líneas de servicio predeterminadas para el área.

        Nota: el nivel se aplica al elegir variante del mismo template; no filtramos aquí
        por `product_id.complexity_level_id` porque `product_id` puede ser la variante
        "predeterminada" del template y no necesariamente coincide con el nivel actual.
        """
        self.ensure_one()
        QuoterLine = self.env["quoter.service.line"]
        domain = [("area_id", "=", self.area_id.id), ("is_default_product", "=", True)]
        return QuoterLine.search(domain)

    def _quoter_variant_for_level(self, qline, level):
        """Devuelve la variante del template de `qline` para `level` (o fallback)."""
        self.ensure_one()
        tmpl = qline.product_tmpl_id or (qline.product_id and qline.product_id.product_tmpl_id)
        if not tmpl:
            return self.env["product.product"].browse()
        if level:
            variant = tmpl.product_variant_ids.filtered(lambda p, lvl=level: p.complexity_level_id == lvl)[:1]
            if variant:
                return variant
        # fallback: variante marcada como predeterminada o la primera
        variant = tmpl.product_variant_ids.filtered("is_default_quoter_product")[:1]
        if not variant:
            variant = tmpl.product_variant_ids[:1]
        return variant

    def _quoter_sync_lines_for_complexity_level(self):
        """Tras guardar el nivel: predeterminados por variante (no en onchange: rompe el formulario)."""
        Line = self.env["sale.order.line"]
        ctx = dict(
            self.env.context,
            quoter_skip_separator_rebuild=True,
            quoter_skip_chatter_log=True,
        )
        for rec in self:
            if rec.state not in (False, "draft"):
                continue
            order = rec.order_id
            area = rec.area_id
            level = rec.complexity_level_id
            if (
                not order
                or not isinstance(order.id, int)
                or not area
                or not order.is_quotation
                or not level
            ):
                continue
            default_lines = rec._quoter_default_service_lines()
            default_products = self.env["product.product"]
            for qline in default_lines:
                product = rec._quoter_variant_for_level(qline, level)
                if product and product.sale_ok:
                    default_products |= product

            all_default_area_products = (
                self.env["quoter.service.line"]
                .search([("area_id", "=", area.id), ("is_default_product", "=", True)])
                .mapped("product_id")
            )
            to_remove = order.order_line.filtered(
                lambda l, prods=all_default_area_products: l.quoter_tab_area_id == area
                and l.product_id in prods
            )
            removed_for_log = to_remove
            if to_remove:
                to_remove.with_context(ctx).unlink()

            existing_products = order.order_line.filtered(
                lambda l, a=area: l.quoter_tab_area_id == a
            ).mapped("product_id")
            created = Line.browse()
            for product in default_products - existing_products:
                nvals = {
                    "order_id": order.id,
                    "product_id": product.id,
                    "product_uom_qty": 1.0,
                    "product_uom": product.uom_id.id,
                    "quoter_tab_area_id": area.id,
                }
                if isinstance(rec.id, int):
                    nvals["quoter_block_id"] = rec.id
                created |= Line.with_context(ctx).create(nvals)
            if created or removed_for_log:
                rec._quoter_log_products_chatter(
                    created_lines=created,
                    removed_lines=removed_for_log,
                    header=_("%s: %s")
                    % (rec._quoter_complexity_level_label(), level.display_name),
                )
            if created:
                rec._quoter_rebuild_separator_sections()
                order._quoter_refresh_block_selectable_products()
            order._quoter_refresh_area_lines_hours_from_levels(area)
            rec._quoter_recalc_all_block_products_for_level()

    def _quoter_recalc_all_block_products_for_level(self):
        """Tras cambiar el nivel: variantes correctas, horas de plantilla y precios en todas las filas."""
        self.ensure_one()
        Line = self.env["sale.order.line"]
        QuoterLine = self.env["quoter.service.line"]
        ctx = dict(
            quoter_skip_separator_rebuild=True,
            quoter_skip_chatter_log=True,
        )
        for rec in self:
            if rec.state not in (False, "draft"):
                continue
            order = rec.order_id
            area = rec.area_id
            level = rec.complexity_level_id
            if (
                not order
                or not isinstance(order.id, int)
                or not area
                or not order.is_quotation
                or not level
            ):
                continue
            lines = rec.order_line_ids.filtered(
                lambda l: not l.display_type
                and not l.quoter_is_adjustment_line
                and not l.quoter_is_area_discount_total_line
                and l.product_id
            )
            for line in lines:
                tmpl = line.product_id.product_tmpl_id
                qline = QuoterLine.search(
                    [("area_id", "=", area.id), ("product_tmpl_id", "=", tmpl.id)],
                    limit=1,
                )
                if qline:
                    variant = rec._quoter_variant_for_level(qline, level)
                    if variant and variant != line.product_id:
                        line.with_context(ctx).write({"product_id": variant.id})
            order._quoter_refresh_area_lines_hours_from_levels(area)

    def _quoter_rebuild_separator_sections(self):
        """Fila sección por etiqueta y productos debajo; conserva ids de sección existentes."""
        ctx = dict(quoter_skip_separator_rebuild=True, quoter_skip_chatter_log=True)
        Line = self.env["sale.order.line"].with_context(ctx)
        for block in self:
            order = block.order_id
            area = block.area_id
            if (
                not order
                or not area
                or not order.is_quotation
                or not isinstance(order.id, int)
            ):
                continue
            area_lines = block.order_line_ids.exists()
            sections = area_lines.filtered(
                lambda l: l.display_type == "line_section"
                and l.quoter_separator_section_tag_id
            )
            base_lines = area_lines.filtered(lambda l: not l.display_type)
            tagged = base_lines.filtered(
                lambda l: l.quoter_separator_tag_id
                and l.product_id
                and not l.quoter_is_area_discount_total_line
            )
            untagged = base_lines.filtered(
                lambda l: not l.quoter_separator_tag_id
                and not l.quoter_is_area_discount_total_line
            )
            discount = base_lines.filtered("quoter_is_area_discount_total_line")
            if not tagged and not untagged and not discount:
                if sections:
                    sections.with_context(ctx).unlink()
                continue

            section_by_tag = {}
            for sec in sections.sorted(
                key=lambda l: (l.quoter_separator_section_tag_id.id, l.id)
            ):
                tid = sec.quoter_separator_section_tag_id.id
                if tid in section_by_tag:
                    sec.with_context(ctx).unlink()
                else:
                    section_by_tag[tid] = sec

            tag_order = []
            seen = set()
            for line in tagged.sorted(key=lambda l: (int(l.sequence or 0), l.id)):
                tid = line.quoter_separator_tag_id.id
                if tid not in seen:
                    seen.add(tid)
                    tag_order.append(line.quoter_separator_tag_id)
            needed_tag_ids = set(seen)
            for tid in list(section_by_tag.keys()):
                if tid not in needed_tag_ids:
                    section_by_tag[tid].with_context(ctx).unlink()
                    del section_by_tag[tid]

            style_mode = area.separator_visual_mode or "none"
            block_id = block.id if isinstance(block.id, int) else False
            ordered_rows = []
            for tag in tag_order:
                prods = tagged.filtered(
                    lambda l, t=tag: l.quoter_separator_tag_id == t
                ).sorted(key=lambda l: (int(l.sequence or 0), l.id))
                section = section_by_tag.get(tag.id)
                if not section or not section.exists():
                    section_vals = {
                        "order_id": order.id,
                        "display_type": "line_section",
                        "name": tag.display_name,
                        "quoter_tab_area_id": area.id,
                        "quoter_separator_section_tag_id": tag.id,
                        "quoter_separator_style_mode": style_mode,
                        "quoter_separator_color": int(tag.color or 0),
                    }
                    if block_id:
                        section_vals["quoter_block_id"] = block_id
                    section = Line.create(section_vals)
                    section_by_tag[tag.id] = section
                else:
                    patch = {
                        "name": tag.display_name,
                        "quoter_tab_area_id": area.id,
                        "quoter_separator_section_tag_id": tag.id,
                        "quoter_separator_style_mode": style_mode,
                        "quoter_separator_color": int(tag.color or 0),
                    }
                    if block_id:
                        patch["quoter_block_id"] = block_id
                    section.with_context(ctx).write(patch)
                ordered_rows.append(section)
                ordered_rows.extend(prods)
            ordered_rows.extend(
                list(untagged.sorted(key=lambda l: (int(l.sequence or 0), l.id)))
            )
            ordered_rows.extend(
                list(discount.sorted(key=lambda l: (int(l.sequence or 0), l.id)))
            )
            seq = 10
            for row in ordered_rows:
                if not row.exists():
                    continue
                if int(row.sequence or 0) != seq:
                    row.with_context(ctx).write({"sequence": seq})
                seq += 10
            block.invalidate_cache(["order_line_ids"])

    def _quoter_sort_lines_by_separator_tag(self):
        """Alias: mantiene llamadas antiguas."""
        return self._quoter_rebuild_separator_sections()

    @api.depends(
        "block_editable",
        "area_allow_change_complexity_level",
        "complexity_level_frozen",
    )
    def _compute_complexity_level_change_allowed(self):
        for rec in self:
            if not rec.block_editable:
                rec.complexity_level_change_allowed = False
            elif rec.area_allow_change_complexity_level:
                rec.complexity_level_change_allowed = True
            else:
                rec.complexity_level_change_allowed = not rec.complexity_level_frozen

    def _quoter_complexity_level_label(self):
        self.ensure_one()
        custom = (self.area_id.complexity_level_custom_label or "").strip()
        if custom:
            return custom
        return _("Nivel de complejidad") if self.area_is_tax else _("Nivel del área")

    _QUOTER_CHATTER_FIELDS = {
        "complexity_level_id": None,  # etiqueta dinámica en _quoter_log_block_changes
        "branch_id": _("Rama"),
        "global_discount_amount": _("Descuento %"),
        "global_surcharge_amount": _("Recargo %"),
        "state": _("Estado del bloque"),
        "sequence": _("Orden del bloque"),
        "complexity_level_frozen": _("Nivel bloqueado"),
    }
    _QUOTER_CHATTER_FLOAT_FIELDS = frozenset(
        {"global_discount_amount", "global_surcharge_amount"}
    )

    def _quoter_chatter_area_title(self):
        self.ensure_one()
        return self.area_id.display_name if self.area_id else _("Área")

    def _quoter_message_post_block(self, parts):
        """Publica en el chatter del pedido un mensaje agrupado por área."""
        self.ensure_one()
        if not parts:
            return
        order = self.order_id
        if not order or not order.is_quotation:
            return
        order._quoter_message_post(
            _("<b>%s</b><br/>%s") % (self._quoter_chatter_area_title(), "<br/>".join(parts))
        )

    @api.model
    def _quoter_format_chatter_pct(self, value):
        return "%.2f%%" % float(value or 0.0)

    @api.model
    def _quoter_selection_label(self, field_name, value):
        selection = dict(self._fields[field_name].selection)
        if not value:
            return selection.get("draft", _("Abierto"))
        return selection.get(value, value)

    def _quoter_product_names_for_chatter(self, products):
        return ", ".join(
            (p.display_name or p.name or str(p.id) for p in products if p)
        ) or "-"

    def _quoter_log_block_changes(self, vals):
        if not quoter_chatter_should_log(self.env):
            return
        labels = dict(self._QUOTER_CHATTER_FIELDS)
        for rec in self:
            order = rec.order_id
            if not order or not order.is_quotation:
                continue
            block_labels = dict(labels)
            if "complexity_level_id" in vals:
                block_labels["complexity_level_id"] = rec._quoter_complexity_level_label()
            parts = []
            for fname, label in block_labels.items():
                if fname not in vals or not label:
                    continue
                old = rec[fname]
                new = vals[fname]
                if fname == "state":
                    old_disp = rec._quoter_selection_label("state", old)
                    new_disp = rec._quoter_selection_label("state", new)
                    if old_disp == new_disp:
                        continue
                    parts.append("%s: %s → %s" % (label, old_disp, new_disp))
                elif fname in rec._QUOTER_CHATTER_FLOAT_FIELDS:
                    if float_compare(float(old or 0.0), float(new or 0.0), precision_digits=4) == 0:
                        continue
                    parts.append(
                        "%s: %s → %s"
                        % (
                            label,
                            rec._quoter_format_chatter_pct(old),
                            rec._quoter_format_chatter_pct(new),
                        )
                    )
                else:
                    sub = quoter_chatter_collect_changes(rec, {fname: new}, {fname: label})
                    parts.extend(sub)
            if parts:
                rec._quoter_message_post_block(parts)

    def _quoter_log_products_chatter(self, created_lines=None, removed_lines=None, header=None):
        """Resumen de altas/bajas de productos (predeterminados, nivel, botón)."""
        self.ensure_one()
        created_lines = created_lines or self.env["sale.order.line"]
        removed_lines = removed_lines or self.env["sale.order.line"]
        parts = []
        if header:
            parts.append(header)
        if removed_lines:
            parts.append(
                _("%s: %s")
                % (
                    _("Productos quitados"),
                    self._quoter_product_names_for_chatter(removed_lines.mapped("product_id")),
                )
            )
        if created_lines:
            parts.append(
                _("%s: %s")
                % (
                    _("Productos agregados"),
                    self._quoter_product_names_for_chatter(created_lines.mapped("product_id")),
                )
            )
        if parts:
            self._quoter_message_post_block(parts)

    def read(self, fields=None, load="_classic_read"):
        """Evita ids de líneas borradas que el form embebido aún referencia."""
        result = super().read(fields=fields, load=load)
        if fields is None or "order_line_ids" in fields:
            for values in result:
                block = self.browse(values["id"])
                Line = self.env["sale.order.line"]
                lines = block.order_line_ids.sorted(
                    key=lambda l: (int(l.sequence or 0), l.id)
                )
                values["order_line_ids"] = [
                    lid for lid in lines.ids if Line.browse(lid).exists()
                ]
        return result

    def write(self, vals):
        if "complexity_level_id" in vals:
            for rec in self:
                if (
                    rec.complexity_level_frozen
                    and not rec.area_id.allow_change_complexity_level
                ):
                    raise ValidationError(
                        _("El nivel del área no puede modificarse una vez guardado en la cotización.")
                    )
        vals = dict(vals or {})
        line_cmds = vals.pop("order_line_ids", None)
        if line_cmds is not None and len(self) == 1:
            line_cmds = self._quoter_sanitize_line_command_list(line_cmds)
        tracked = {k: v for k, v in vals.items() if k in self._QUOTER_CHATTER_FIELDS}
        adjustment_fields = {"global_discount_amount", "global_surcharge_amount"}
        if adjustment_fields & set(vals.keys()):
            for rec in self:
                old_discount = float(rec.global_discount_amount or 0.0)
                old_surcharge = float(rec.global_surcharge_amount or 0.0)
                new_discount = float(vals.get("global_discount_amount", old_discount) or 0.0)
                new_surcharge = float(vals.get("global_surcharge_amount", old_surcharge) or 0.0)
                changed = (
                    float_compare(new_discount, old_discount, precision_digits=4) != 0
                    or float_compare(new_surcharge, old_surcharge, precision_digits=4) != 0
                )
                if changed and rec.order_id:
                    rec.order_id._check_quoter_partner_adjustment_write_access()
        write_recs = self
        line_ctx = dict(
            quoter_skip_separator_rebuild=True,
            quoter_skip_chatter_log=True,
            quoter_skip_block_product_refresh=True,
        )
        if line_cmds is not None:
            write_recs = self.with_context(**line_ctx)
        unlink_ops = []
        other_line_ops = []
        removed_lines_for_chatter = self.env["sale.order.line"]
        if line_cmds:
            unlink_line_ids = set()
            for cmd in line_cmds:
                if (
                    isinstance(cmd, (list, tuple))
                    and len(cmd) >= 2
                    and cmd[0] in (2, 3)
                ):
                    lid = self._quoter_coerce_line_command_id(cmd[1])
                    if lid:
                        unlink_ops.append(cmd)
                        unlink_line_ids.add(lid)
                else:
                    other_line_ops.append(cmd)
            if unlink_line_ids:
                other_line_ops = self._quoter_filter_line_commands_excluding_line_ids(
                    other_line_ops, unlink_line_ids
                )
            if unlink_ops and len(self) == 1:
                removed_lines_for_chatter = self.env["sale.order.line"].browse(
                    list(unlink_line_ids)
                ).exists()
        res = True
        if unlink_ops:
            res = super(QuoterSaleOrderArea, write_recs).write({"order_line_ids": unlink_ops})
            if removed_lines_for_chatter and len(self) == 1:
                self._quoter_log_products_chatter(
                    removed_lines=removed_lines_for_chatter,
                    header=_("Productos eliminados"),
                )
            self.invalidate_cache(["order_line_ids"])
            self.mapped("order_id").invalidate_cache(fnames=["order_line"])
            if other_line_ops and len(self) == 1:
                other_line_ops = self._quoter_drop_missing_line_commands(
                    self._quoter_sanitize_line_command_list(other_line_ops)
                )
        write_vals = dict(vals)
        if other_line_ops:
            write_vals["order_line_ids"] = other_line_ops
        if write_vals:
            res = super(QuoterSaleOrderArea, write_recs).write(write_vals)
        if line_cmds is not None:
            self.invalidate_cache(["order_line_ids"])
            orders = self.mapped("order_id")
            orders.invalidate_cache(fnames=["order_line"])
            self.order_line_ids.exists()._quoter_validate_quotation_line_hours_sum()
            self._quoter_rebuild_separator_sections()
            for order in orders:
                order.flush(fnames=["order_line"])
            orders._quoter_refresh_block_selectable_products()
        if tracked:
            self._quoter_log_block_changes(tracked)
        if adjustment_fields & set(vals.keys()):
            for rec in self:
                if rec.order_id and rec.order_id.is_quotation:
                    rec.order_id._quoter_sync_area_discount_total_line()
        if "complexity_level_id" in vals and "order_line_ids" not in vals:
            self.filtered(
                lambda b: b.complexity_level_id
                and b.order_id
                and isinstance(b.order_id.id, int)
            )._quoter_sync_lines_for_complexity_level()
        elif "branch_id" in vals:
            for rec in self:
                if rec.order_id and rec.area_id:
                    rec.order_id._quoter_refresh_area_lines_hours_from_levels(rec.area_id)
        if "complexity_level_id" in vals and vals.get("complexity_level_id"):
            for rec in self:
                order = rec.order_id
                if (
                    order
                    and isinstance(order.id, int)
                    and not rec.area_id.allow_change_complexity_level
                ):
                    rec.complexity_level_frozen = True
        return res

    @api.model_create_multi
    def create(self, vals_list):
        pending_line_commands = []
        for vals in vals_list:
            vals = dict(vals or {})
            pending_line_commands.append(vals.pop("order_line_ids", None))
            if not vals.get("order_id"):
                default_order = self.env.context.get("default_order_id")
                if isinstance(default_order, int):
                    vals["order_id"] = default_order
            if vals.get("branch_id"):
                continue
            area = self.env["quoter.professional.area"].browse(vals.get("area_id"))
            if area:
                vals["branch_id"] = area._resolve_matrix_branch().id
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if rec.order_id and rec.order_id.is_quotation and rec.area_id:
                parts = [_("Bloque de cotización creado.")]
                if vals.get("complexity_level_id"):
                    level = rec.complexity_level_id
                    if level:
                        parts.append(
                            "%s: %s"
                            % (rec._quoter_complexity_level_label(), level.display_name)
                        )
                rec._quoter_message_post_block(parts)
        for rec, line_commands in zip(records, pending_line_commands):
            if line_commands:
                rec.with_context(
                    quoter_skip_separator_rebuild=True,
                    quoter_skip_chatter_log=True,
                    quoter_skip_block_product_refresh=True,
                ).write(
                    {
                        "order_line_ids": rec._quoter_sanitize_line_command_list(
                            line_commands
                        )
                    }
                )
        for rec in records:
            if rec.order_id and rec.order_id.is_quotation:
                rec.order_id._quoter_sync_area_discount_total_line()
            if (
                rec.complexity_level_id
                and rec.order_id
                and isinstance(rec.order_id.id, int)
            ):
                rec.complexity_level_frozen = True
        return records

    @api.model
    def _quoter_coerce_line_command_id(self, line_id):
        if isinstance(line_id, int):
            return line_id
        if isinstance(line_id, str) and line_id.isdigit():
            return int(line_id)
        return None

    @api.model
    def _quoter_line_ids_from_unlink_commands(self, commands):
        """Ids de sale.order.line que se borran con comandos (2)/(3) en el mismo write."""
        unlink_ids = set()
        for cmd in commands or []:
            if not isinstance(cmd, (list, tuple)) or len(cmd) < 2 or cmd[0] not in (2, 3):
                continue
            lid = self._quoter_coerce_line_command_id(cmd[1])
            if lid:
                unlink_ids.add(lid)
        return unlink_ids

    @api.model
    def _quoter_filter_line_commands_excluding_line_ids(self, commands, excluded_ids):
        """Quita updates/links sobre líneas que se eliminan en el mismo batch."""
        excluded = set(excluded_ids or [])
        if not excluded:
            return list(commands or [])
        filtered = []
        for cmd in commands or []:
            if not isinstance(cmd, (list, tuple)) or len(cmd) < 2:
                continue
            op = cmd[0]
            lid = self._quoter_coerce_line_command_id(cmd[1])
            if op in (1, 2, 3, 4) and lid in excluded:
                continue
            filtered.append(cmd)
        return filtered

    @api.model
    def _quoter_drop_missing_line_commands(self, commands):
        """Ignora comandos sobre líneas inexistentes (p. ej. ya borradas por RPC)."""
        if not commands:
            return []
        Line = self.env["sale.order.line"]
        kept = []
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)) or len(cmd) < 2:
                kept.append(cmd)
                continue
            if cmd[0] not in (1, 2, 3, 4):
                kept.append(cmd)
                continue
            lid = self._quoter_coerce_line_command_id(cmd[1])
            if lid and not Line.browse(lid).exists():
                continue
            kept.append(cmd)
        return kept

    def _quoter_sanitize_line_command_list(self, commands):
        """Completa campos requeridos en comandos de líneas del bloque."""
        self.ensure_one()
        if not commands or not isinstance(commands, list):
            return []
        Product = self.env["product.product"]
        Line = self.env["sale.order.line"]
        new_cmds = []
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)):
                continue
            lid = self._quoter_coerce_line_command_id(cmd[1]) if len(cmd) >= 2 else None
            if cmd[0] in (1, 2, 3, 4) and lid and not Line.browse(lid).exists():
                continue
            if cmd[0] in (2, 3, 4) and len(cmd) >= 2:
                line = Line.browse(lid) if lid else Line
                if not line.exists():
                    continue
                if cmd[0] in (2, 3) and line.display_type == "line_section" and line.quoter_separator_section_tag_id:
                    continue
            if cmd[0] == 0 and len(cmd) >= 3 and isinstance(cmd[2], dict):
                if cmd[2].get("display_type") == "line_section":
                    continue
            # (6, 0, ids) reemplaza todo el x2many y borra líneas que el cliente aún muestra.
            if cmd[0] == 6:
                continue
            if cmd[0] in (0, 1) and len(cmd) >= 3 and isinstance(cmd[2], dict):
                line_vals = dict(cmd[2])
                if not line_vals.get("display_type") and not line_vals.get("product_id"):
                    if cmd[0] == 0:
                        continue
                    # (1, id, vals): permitir actualización parcial (horas manuales, nota, etc.)
                    if cmd[0] == 1 and not line_vals:
                        continue
                if not line_vals.get("display_type"):
                    pid = line_vals.get("product_id")
                    product = Product.browse(pid) if pid else Product
                    if product and product.exists():
                        line_vals.setdefault("product_uom_qty", 1.0)
                        if not line_vals.get("product_uom"):
                            line_vals["product_uom"] = product.uom_id.id
                        if not line_vals.get("name"):
                            line_vals["name"] = (
                                product.get_product_multiline_description_sale()
                                or product.display_name
                            )
                if self.order_id and not line_vals.get("order_id"):
                    line_vals["order_id"] = self.order_id.id
                if self.area_id and not line_vals.get("quoter_tab_area_id"):
                    line_vals["quoter_tab_area_id"] = self.area_id.id
                if self.id and not line_vals.get("quoter_block_id"):
                    line_vals["quoter_block_id"] = self.id
                new_cmds.append((cmd[0], cmd[1], line_vals))
            else:
                new_cmds.append(cmd)
        return new_cmds

    def unlink(self):
        for rec in self:
            order = rec.order_id
            if order and order.is_quotation and rec.area_id:
                order._quoter_message_post(
                    _("<b>%s</b><br/>%s")
                    % (rec._quoter_chatter_area_title(), _("Bloque de cotización eliminado."))
                )
        orders = self.mapped("order_id").filtered("is_quotation")
        res = super().unlink()
        for order in orders:
            order._quoter_sync_area_discount_total_line()
        return res

    def action_quoter_load_default_products(self):
        self.ensure_one()
        # En formularios nuevos el bloque puede venir con state=False hasta el primer guardado.
        if self.state not in (False, "draft"):
            raise UserError(_("Solo se pueden cargar predeterminados en borrador."))
        order = self.order_id
        area = self.area_id
        default_lines = self._quoter_default_service_lines()
        if not default_lines:
            return True
        # Templates de predeterminados del área (para limpiar/swap si cambia el nivel).
        default_templates = (
            default_lines.mapped("product_tmpl_id")
            | default_lines.mapped("product_id.product_tmpl_id")
        ).filtered(lambda t: t)

        created_lines = self.env["sale.order.line"]
        # Variante canónica de cada línea de servicio (no medios/bajos/alto en el selector).
        for qline in default_lines:
            tmpl = qline.product_tmpl_id or (qline.product_id and qline.product_id.product_tmpl_id)
            product = qline.product_id or (tmpl.product_variant_id if tmpl else False)
            if not product:
                continue
            exists_exact = order.order_line.filtered(
                lambda l, a=area, p=product: l.quoter_tab_area_id == a and l.product_id == p
            )[:1]
            if exists_exact:
                continue

            line_new = self.env["sale.order.line"].new(
                {
                    "order_id": order,
                    "product_id": product.id,
                    "product_uom_qty": 1.0,
                    "quoter_tab_area_id": area.id,
                }
            )
            # Completa descripción, impuestos, uom, etc.
            if hasattr(line_new, "product_id_change"):
                line_new.product_id_change()
            # Algunos addons implementan _onchange_product_id, dispararlo si existe
            if hasattr(line_new, "_onchange_product_id"):
                line_new._onchange_product_id()
            vals = line_new._convert_to_write(line_new._cache)
            # Constraint SQL de sale.order.line exige UoM en líneas contables.
            # En algunos flujos de new()+onchange puede no venir en vals.
            vals.setdefault("order_id", order.id)
            vals.setdefault("product_id", product.id)
            vals.setdefault("product_uom_qty", 1.0)
            if not vals.get("product_uom"):
                vals["product_uom"] = product.uom_id.id
            if not vals.get("name"):
                vals["name"] = (
                    product.get_product_multiline_description_sale() or product.display_name
                )
            if isinstance(self.id, int):
                vals["quoter_block_id"] = self.id
            created_lines |= self.env["sale.order.line"].with_context(
                quoter_skip_separator_rebuild=True,
                quoter_skip_chatter_log=True,
                quoter_skip_block_product_refresh=True,
            ).create(vals)
        if created_lines:
            self._quoter_log_products_chatter(
                created_lines=created_lines,
                header=_("Carga de productos predeterminados."),
            )
            self._quoter_sort_lines_by_separator_tag()
            order.with_context(quoter_skip_block_product_refresh=False)._quoter_refresh_block_selectable_products()
        # Reaplica horas por nivel/rango en líneas del área creadas/actualizadas.
        order._quoter_refresh_area_lines_hours_from_levels(area)
        return True

    def _quoter_line_belongs_to_block(self, line):
        """True si la línea pertenece a este bloque (por block_id o área del pedido)."""
        self.ensure_one()
        if not line.exists() or line.order_id != self.order_id:
            return False
        if line.display_type == "line_section":
            return False
        if line.quoter_block_id:
            return line.quoter_block_id == self
        return bool(self.area_id and line.quoter_tab_area_id == self.area_id)

    def action_quoter_unlink_order_line(self, line_id):
        """Borra la línea en servidor de inmediato (evita id fantasma en el BasicModel)."""
        self.ensure_one()
        line = self.env["sale.order.line"].browse(line_id)
        if not self._quoter_line_belongs_to_block(line):
            return True
        if not line.display_type and not line.quoter_is_area_discount_total_line:
            product_name = (
                line.product_id.display_name
                if line.product_id
                else (line.name or _("Línea"))
            )
            self._quoter_message_post_block([_("Producto eliminado: %s") % product_name])
        ctx = dict(
            quoter_skip_separator_rebuild=True,
            quoter_skip_chatter_log=True,
            quoter_skip_block_product_refresh=True,
        )
        line.with_context(ctx).unlink()
        self.invalidate_cache(["order_line_ids"])
        if self.order_id:
            self.order_id.invalidate_cache(fnames=["order_line"])
        if self.order_id and self.order_id.is_quotation:
            self._quoter_rebuild_separator_sections()
            order = self.order_id
            order.invalidate_cache(fnames=["order_line"])
            order.flush(fnames=["order_line"])
            order._quoter_sync_area_discount_total_line()
            self.order_id._quoter_refresh_block_selectable_products()
        return True

    def action_quoter_publish(self):
        """Pasa el bloque a Cerrado (clave interna published)."""
        self.write({"state": "published"})
        return True

    def action_quoter_reopen(self):
        """Vuelve de Cerrado a Abierto para poder ajustar nivel, productos, etc."""
        for rec in self:
            if rec.state != "published":
                raise UserError(_("Solo se puede reabrir un bloque en estado Cerrado."))
        self.write({"state": "draft"})
        return True

    def action_quoter_cancel_block(self):
        self.write({"state": "cancel"})
        return True

    @api.depends("state")
    def _compute_block_lock_flags(self):
        for rec in self:
            st = rec.state or False
            rec.block_editable = st in (False, "draft")
            rec.structure_locked = st in ("published", "cancel")
            rec.lines_frozen = st == "cancel"

    @api.depends(
        "area_id",
        "complexity_level_id",
        "order_id.order_line.product_id",
        "order_id.order_line.quoter_tab_area_id",
        "order_id.order_line.quoter_block_id",
        "order_line_ids.product_id",
    )
    def _compute_selectable_product_ids(self):
        """Productos del área que aún no están en otra línea de la misma área."""
        Product = self.env["product.product"]
        empty = Product.browse()
        for rec in self:
            if not rec.area_id or not rec.complexity_level_id or not rec.order_id:
                rec.selectable_product_ids = empty
                continue
            rec.selectable_product_ids = Product.browse(
                Product._quoter_product_ids_for_area_picker(rec.area_id, rec.order_id)
            )

    @api.depends("area_id", "area_id.name")
    def _compute_footer_captions(self):
        for rec in self:
            aname = rec.area_id.name if rec.area_id else ""
            rec.caption_products = (_("Productos %s") % aname if aname else _("Productos")) + ":"
            rec.caption_adjustments = (_("Ajustes %s") % aname if aname else _("Ajustes")) + ":"
            rec.caption_discount = _("Descuento:")
            rec.caption_surcharge = _("Recargo:")
            rec.caption_total = _("Total:")

    @api.depends(
        "order_id.order_line",
        "order_id.order_line.price_subtotal",
        "order_id.order_line.quoter_tab_area_id",
        "order_id.order_line.quoter_is_adjustment_line",
        "order_id.order_line.display_type",
        "area_id",
        "global_discount_amount",
        "global_surcharge_amount",
    )
    def _compute_area_financials(self):
        for rec in self:
            order = rec.order_id
            area = rec.area_id
            if not order or not area:
                rec.product_untaxed = 0.0
                rec.adjustment_untaxed = 0.0
                rec.discount_line_amount = 0.0
                rec.surcharge_line_amount = 0.0
                rec.total_untaxed = 0.0
                continue
            olines = order.order_line.filtered(
                lambda l, a=area: not l.display_type and l.quoter_tab_area_id == a
            )
            prod = sum(olines.filtered(lambda l: not l.quoter_is_adjustment_line).mapped("price_subtotal"))
            adj = sum(olines.filtered(lambda l: l.quoter_is_adjustment_line).mapped("price_subtotal"))
            sub = prod + adj
            disc_pct, surcharge_pct = order._quoter_block_adjustment_amounts(rec)
            disc_amt = sub * (disc_pct / 100.0)
            surcharge_amt = sub * (surcharge_pct / 100.0)
            rec.product_untaxed = prod
            rec.adjustment_untaxed = adj
            rec.discount_line_amount = disc_amt
            rec.surcharge_line_amount = surcharge_amt
            rec.total_untaxed = sub - disc_amt + surcharge_amt

    @api.depends(
        "order_id.order_line",
        "order_id.order_line.quoter_tab_area_id",
        "order_id.order_line.quoter_is_adjustment_line",
        "order_id.order_line.quoter_range_hour_ids",
        "order_id.order_line.quoter_range_hour_ids.hours",
        "order_id.order_line.quoter_range_hour_ids.area_range_id",
        "order_id.order_line.name",
        "area_id",
        "area_id.area_range_ids",
        "global_discount_amount",
        "global_surcharge_amount",
        "order_id.partner_id",
        "order_id.pricelist_id",
        "order_id.date_order",
    )
    def _compute_area_summary_html(self):
        for rec in self:
            if not rec.area_id or not rec.order_id:
                rec.area_summary_html = False
            else:
                rec.area_summary_html = rec.order_id._quoter_build_area_summary_html(rec.area_id, rec)

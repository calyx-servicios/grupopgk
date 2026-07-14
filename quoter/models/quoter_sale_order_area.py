# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare

from .quoter_chatter import quoter_chatter_collect_changes, quoter_chatter_should_log
from .quoter_sale_order_workflow import QUOTER_WORKFLOW_APROBADOR_BLOCK_FIELDS


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
    manager_id = fields.Many2one(
        comodel_name="res.users",
        string="Gerente Responsable",
        copy=False,
        help="Gerente responsable de esta área en la cotización (independiente por área).",
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
    area_is_auditoria = fields.Boolean(
        string="Área Auditoría",
        related="area_id.is_auditoria_area",
        readonly=True,
    )
    area_is_formula = fields.Boolean(
        string="Área fórmula",
        related="area_id.is_formula_area",
        readonly=True,
    )
    area_is_payroll = fields.Boolean(
        string="Área Payroll",
        related="area_id.is_payroll_area",
        readonly=True,
    )
    area_hour_matrix_mode = fields.Selection(
        related="area_id.hour_matrix_mode",
        readonly=True,
    )
    area_is_formula_chain = fields.Boolean(
        string="Área fórmula en cadena",
        compute="_compute_area_is_formula_chain",
    )
    area_is_regular_manual = fields.Boolean(
        string="Área regular manual",
        compute="_compute_area_is_regular_manual",
    )
    area_show_formula_volume_fields = fields.Boolean(
        string="Mostrar columnas volumen fórmula",
        compute="_compute_area_show_formula_volume_fields",
    )
    user_can_view_block = fields.Boolean(
        string="Usuario puede ver bloque",
        compute="_compute_user_can_view_block",
    )

    @api.depends("area_hour_matrix_mode")
    def _compute_area_show_formula_volume_fields(self):
        for rec in self:
            rec.area_show_formula_volume_fields = (
                rec.area_hour_matrix_mode == "formula"
            )

    def _compute_user_can_view_block(self):
        """El usuario ve el bloque si no hay grupo en el área o si pertenece al grupo."""
        user = self.env.user
        for rec in self:
            group = rec.area_id.group_id if rec.area_id else False
            if not group:
                rec.user_can_view_block = True
            else:
                rec.user_can_view_block = group in user.groups_id

    area_is_finanzas = fields.Boolean(
        string="Área Finanzas",
        related="area_id.is_finanzas_area",
        readonly=True,
    )
    chain_employee_count = fields.Integer(
        string="Cantidad de empleados",
        default=1,
        help="Define qué tabla de la cadena aplica para calcular horas por rol.",
    )
    formula_matrix_section_title = fields.Char(
        string="Título tabla fórmula",
        compute="_compute_formula_matrix_section_title",
    )
    chain_matrix_section_title = fields.Char(
        string="Título tabla cadena",
        compute="_compute_chain_matrix_section_title",
    )

    @api.depends("area_hour_matrix_mode")
    def _compute_area_is_formula_chain(self):
        for rec in self:
            rec.area_is_formula_chain = rec.area_hour_matrix_mode == "formula_chain"

    @api.depends("area_hour_matrix_mode")
    def _compute_area_is_regular_manual(self):
        for rec in self:
            rec.area_is_regular_manual = rec.area_hour_matrix_mode == "regular_manual"

    def _quoter_apply_area_configured_complexity_level(self):
        """Asigna el nivel definido en configuración del área (p. ej. Finanzas)."""
        for rec in self:
            if rec.area_id.hour_matrix_mode != "regular_manual":
                continue
            level = rec.area_id._quoter_primary_complexity_level()
            if level and rec.complexity_level_id != level:
                rec.complexity_level_id = level

    @api.depends("area_id", "area_id.name")
    def _compute_chain_matrix_section_title(self):
        for rec in self:
            if not rec.area_is_formula_chain or not rec.area_id:
                rec.chain_matrix_section_title = False
                continue
            rec.chain_matrix_section_title = _(
                "Horas por rol (%(area)s) — cantidad de empleados"
            ) % {"area": rec.area_id.name or ""}
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
    quoter_workflow_can_edit_adjustments = fields.Boolean(
        related="order_id.quoter_workflow_can_edit_adjustments",
        string="Puede editar descuento/recargo",
        readonly=True,
    )
    quoter_is_first_auditoria = fields.Boolean(
        related="order_id.quoter_is_first_quotation",
        string="¿Es primera auditoría?",
        readonly=False,
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
    area_chain_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        related="area_id.chain_complexity_level_ids",
        string="Niveles cadena",
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
    show_block_complexity_level = fields.Boolean(
        compute="_compute_show_block_complexity_level",
    )
    show_block_chain_complexity_level = fields.Boolean(
        compute="_compute_show_block_chain_complexity_level",
    )
    area_bulk_line_load = fields.Boolean(
        related="area_id.bulk_line_load",
        string="Carga múltiple de líneas",
        readonly=True,
    )
    area_load_default_products = fields.Boolean(
        related="area_id.load_default_products",
        string="Cargar predeterminados (área)",
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

    bpa_summary_html = fields.Html(
        string="Desglose APB por sección",
        compute="_compute_bpa_summary_html",
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
            if not rec.complexity_level_id or not rec.area_id:
                continue
            if rec.area_id.hour_matrix_mode == "formula_chain":
                if (
                    rec.complexity_level_id
                    and rec.complexity_level_id
                    not in rec.area_id.chain_complexity_level_ids
                ):
                    raise ValidationError(
                        _(
                            "El nivel debe estar en la tabla de aumento %% "
                            "del área «%s»."
                        )
                        % rec.area_id.display_name
                    )
                continue
            if rec.complexity_level_id not in rec.area_id.complexity_level_ids:
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
            return {"domain": {"complexity_level_id": []}}
        if self.area_id.hour_matrix_mode == "regular_manual":
            allowed = self.area_id.complexity_level_ids
            level = self.area_id._quoter_primary_complexity_level()
            if level:
                self.complexity_level_id = level
            elif self.complexity_level_id and self.complexity_level_id not in allowed:
                self.complexity_level_id = False
            if not self.branch_id or self.branch_id not in self.area_id._effective_branch_ids():
                self.branch_id = self.area_id._resolve_matrix_branch()
            return {
                "domain": {
                    "complexity_level_id": [("id", "in", allowed.ids)],
                }
            }
        if self.area_id.hour_matrix_mode == "formula_chain":
            allowed = self.area_id.chain_complexity_level_ids
            if len(allowed) == 1:
                self.complexity_level_id = allowed[0]
            elif self.complexity_level_id and self.complexity_level_id not in allowed:
                self.complexity_level_id = False
            if not self.branch_id or self.branch_id not in self.area_id._effective_branch_ids():
                self.branch_id = self.area_id._resolve_matrix_branch()
            return {
                "domain": {
                    "complexity_level_id": [("id", "in", allowed.ids)],
                }
            }
        allowed = self.area_id.complexity_level_ids
        if len(allowed) == 1:
            self.complexity_level_id = allowed[0]
        elif self.complexity_level_id and self.complexity_level_id not in allowed:
            self.complexity_level_id = False
        if not self.branch_id or self.branch_id not in self.area_id._effective_branch_ids():
            self.branch_id = self.area_id._resolve_matrix_branch()
        return {
            "domain": {
                "complexity_level_id": [("id", "in", allowed.ids)],
            }
        }

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
            if not area.load_default_products:
                rec._quoter_recalc_all_block_products_for_level()
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
        ServiceLine = self.env["quoter.service.line"]
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
            block_id = block.id if isinstance(block.id, int) else False
            # Re-vincula líneas del área que quedaron fuera del bloque (datos históricos/caché).
            if block_id:
                stray_lines = order.order_line.filtered(
                    lambda l, a=area, b=block: l.quoter_tab_area_id == a
                    and l.quoter_block_id != b
                    and not l.quoter_is_area_discount_total_line
                )
                if stray_lines:
                    stray_lines.with_context(ctx).write({"quoter_block_id": block_id})

            area_lines = order.order_line.exists().filtered(
                lambda l, a=area, bid=block_id: l.quoter_tab_area_id == a
                and (not bid or (l.quoter_block_id and l.quoter_block_id.id == bid))
            )
            sections = area_lines.filtered(
                lambda l: l.display_type == "line_section"
                and l.quoter_separator_section_tag_id
            )
            base_lines = area_lines.filtered(lambda l: not l.display_type)

            # Algunas líneas quedan sin quoter_separator_tag_id por relación del producto;
            # tomar la etiqueta real desde quoter.service.line del área.
            service_by_tmpl = {}
            service_lines = ServiceLine.search([("area_id", "=", area.id)])
            for qsl in service_lines:
                if qsl.product_tmpl_id:
                    service_by_tmpl[qsl.product_tmpl_id.id] = qsl

            def _effective_tag(line):
                tag = line.quoter_separator_tag_id
                if tag:
                    return tag
                tmpl = line.product_id.product_tmpl_id if line.product_id else False
                if not tmpl:
                    return self.env["quoter.line.separator.tag"]
                qsl = service_by_tmpl.get(tmpl.id)
                return qsl.separator_tag_id if qsl and qsl.separator_tag_id else self.env["quoter.line.separator.tag"]

            tagged = base_lines.filtered(
                lambda l: _effective_tag(l)
                and l.product_id
                and not l.quoter_is_area_discount_total_line
            )
            untagged = base_lines.filtered(
                lambda l: not _effective_tag(l)
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

            tag_order = tagged.mapped(lambda l: _effective_tag(l)).filtered(
                lambda t: t
            ).sorted(key=lambda t: t.id)
            needed_tag_ids = set(tag_order.ids)
            for tid in list(section_by_tag.keys()):
                if tid not in needed_tag_ids:
                    section_by_tag[tid].with_context(ctx).unlink()
                    del section_by_tag[tid]

            style_mode = area.separator_visual_mode or "none"
            ordered_rows = []
            for tag in tag_order:
                prods = tagged.filtered(
                    lambda l, t=tag: _effective_tag(l) == t
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
        "area_level_ids",
        "area_is_formula",
        "area_is_formula_chain",
        "area_is_regular_manual",
    )
    def _compute_show_block_complexity_level(self):
        for rec in self:
            rec.show_block_complexity_level = bool(
                not rec.area_is_formula
                and not rec.area_is_formula_chain
                and not rec.area_is_regular_manual
                and len(rec.area_level_ids) > 1
            )

    @api.depends("area_chain_level_ids", "area_is_formula_chain")
    def _compute_show_block_chain_complexity_level(self):
        for rec in self:
            rec.show_block_chain_complexity_level = bool(
                rec.area_is_formula_chain and len(rec.area_chain_level_ids) > 1
            )

    @api.depends(
        "block_editable",
        "area_allow_change_complexity_level",
        "area_is_auditoria",
        "complexity_level_frozen",
    )
    def _compute_complexity_level_change_allowed(self):
        for rec in self:
            if not rec.block_editable:
                rec.complexity_level_change_allowed = False
            elif rec.area_is_auditoria or rec.area_allow_change_complexity_level:
                rec.complexity_level_change_allowed = True
            else:
                rec.complexity_level_change_allowed = not rec.complexity_level_frozen

    def _quoter_highest_complexity_level(self):
        self.ensure_one()
        if not self.area_id:
            return self.env["quoter.complexity.level"]
        return self.area_id.complexity_level_ids.sorted(key=lambda lev: lev.id, reverse=True)[:1]

    def _quoter_auto_assign_complexity_level(self):
        """Asigna nivel automático (único nivel del área o primera auditoría)."""
        for rec in self:
            if not rec.area_id:
                continue
            mode = rec.area_id.hour_matrix_mode
            if mode == "formula_chain":
                if not rec.complexity_level_id:
                    level = rec.area_id._chain_default_complexity_level()
                    if level:
                        rec.complexity_level_id = level
                continue
            if mode == "formula":
                if not rec.complexity_level_id:
                    level = rec.area_id._formula_default_complexity_level()
                    if level:
                        rec.complexity_level_id = level
                continue
            if mode == "regular_manual":
                rec._quoter_apply_area_configured_complexity_level()
                continue
            levels = rec.area_id.complexity_level_ids
            if len(levels) == 1 and not rec.complexity_level_id:
                rec.complexity_level_id = levels[0]
            elif (
                len(levels) > 1
                and not rec.complexity_level_id
                and rec.area_id.is_auditoria_area
                and rec.order_id
                and rec.order_id.quoter_is_first_quotation
            ):
                level = rec._quoter_highest_complexity_level()
                if level:
                    rec.complexity_level_id = level

    def _quoter_try_autoload_default_products(self):
        """Carga predeterminados si hay nivel y el bloque aún no tiene productos."""
        for rec in self:
            if (
                not rec.area_id
                or not rec.area_id.load_default_products
                or rec.area_id.hour_matrix_mode == "regular_manual"
                or not rec.complexity_level_id
            ):
                continue
            order = rec.order_id
            if not order or not order.is_quotation or not isinstance(order.id, int):
                continue
            if rec.state not in (False, "draft"):
                continue
            has_products = rec.order_line_ids.filtered(
                lambda l: not l.display_type and not l.quoter_is_area_discount_total_line
            )
            if not has_products:
                rec.action_quoter_load_default_products()

    @api.onchange("quoter_is_first_auditoria")
    def _onchange_quoter_is_first_auditoria(self):
        for rec in self:
            if not rec.area_id or not rec.area_id.is_auditoria_area:
                continue
            if rec.quoter_is_first_auditoria:
                level = rec._quoter_highest_complexity_level()
                if level:
                    rec.complexity_level_id = level

    def _quoter_apply_first_auditoria_effect(self):
        """Primera auditoría: riesgo más alto; predeterminados si el bloque está vacío."""
        for rec in self:
            if not rec.area_id or not rec.area_id.is_auditoria_area:
                continue
            if not rec.order_id or not rec.order_id.is_quotation:
                continue
            if rec.order_id.quoter_is_first_quotation:
                level = rec._quoter_highest_complexity_level()
                if level and rec.complexity_level_id != level:
                    rec.write({"complexity_level_id": level.id})
            else:
                rec._quoter_auto_assign_complexity_level()
            rec._quoter_try_autoload_default_products()
            if rec.complexity_level_id:
                rec._quoter_recalc_all_block_products_for_level()

    def _quoter_complexity_level_label(self):
        self.ensure_one()
        if self.area_id.is_auditoria_area:
            return _("Nivel de riesgo")
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
        vals = dict(vals or {})
        for rec in self:
            order = rec.order_id
            if (
                order
                and order.is_quotation
                and isinstance(order.id, int)
                and not self.env.context.get("quoter_workflow_transition")
            ):
                wf_vals = dict(vals)
                wf_vals.pop("order_line_ids", None)
                if wf_vals and not order._quoter_workflow_can_edit_content():
                    if not (
                        order.quoter_workflow_state in ("en_aprobacion", "aprobado_interno")
                        and order._quoter_user_is_aprobador_profile()
                        and set(wf_vals.keys()).issubset(QUOTER_WORKFLOW_APROBADOR_BLOCK_FIELDS)
                    ):
                        raise AccessError(
                            _(
                                "No puede modificar el bloque del área «%s» en el estado «%s»."
                            )
                            % (
                                rec.area_id.display_name,
                                order._quoter_workflow_state_label(
                                    order.quoter_workflow_state
                                ),
                            )
                        )
        first_auditoria_flag = None
        if "quoter_is_first_auditoria" in vals:
            first_auditoria_flag = bool(vals.pop("quoter_is_first_auditoria"))
            for rec in self:
                if rec.order_id:
                    rec.order_id.with_context(
                        quoter_skip_first_quotation_risk_levels=True
                    ).write({"quoter_is_first_quotation": first_auditoria_flag})
        if "complexity_level_id" in vals:
            for rec in self:
                if (
                    rec.complexity_level_frozen
                    and not rec.area_id.allow_change_complexity_level
                    and not rec.area_id.is_auditoria_area
                ):
                    raise ValidationError(
                        _("El nivel del área no puede modificarse una vez guardado en la cotización.")
                    )
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
        if first_auditoria_flag is not None:
            # El efecto de primera auditoría recrea/sincroniza líneas en servidor;
            # los comandos (1, id, vals) del form embebido suelen quedar obsoletos.
            other_line_ops = []
        if other_line_ops and len(self) == 1:
            other_line_ops = self._quoter_drop_missing_line_commands(
                self._quoter_sanitize_line_command_list(other_line_ops)
            )
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
        if (
            "complexity_level_id" in vals
            and line_cmds is None
            and first_auditoria_flag is None
        ):
            changed_blocks = self.filtered(
                lambda b: b.complexity_level_id
                and b.order_id
                and isinstance(b.order_id.id, int)
            )
            aud_blocks = changed_blocks.filtered(lambda b: b.area_id.is_auditoria_area)
            other_blocks = (
                changed_blocks - aud_blocks
            ).filtered(lambda b: not b.area_is_formula_chain)
            if other_blocks:
                other_blocks._quoter_sync_lines_for_complexity_level()
            if aud_blocks:
                aud_blocks._quoter_sync_lines_for_complexity_level()
                aud_blocks._quoter_recalc_all_block_products_for_level()
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
                    and not rec.area_id.is_auditoria_area
                ):
                    rec.complexity_level_frozen = True
        if first_auditoria_flag is True:
            self._quoter_apply_first_auditoria_effect()
        elif first_auditoria_flag is False:
            self._quoter_auto_assign_complexity_level()
            self._quoter_try_autoload_default_products()
        if "area_id" in vals:
            self.filtered("area_is_regular_manual")._quoter_apply_area_configured_complexity_level()
        if "chain_employee_count" in vals or "complexity_level_id" in vals:
            self.filtered("area_is_formula_chain")._quoter_apply_chain_hours_to_lines()
        return res

    @api.onchange("complexity_level_id")
    def _onchange_complexity_level_chain_hours(self):
        self.filtered("area_is_formula_chain")._quoter_apply_chain_hours_to_lines()

    @api.onchange("chain_employee_count")
    def _onchange_chain_employee_count(self):
        for rec in self:
            if (
                rec.area_is_formula_chain
                and rec.chain_employee_count
                and rec.chain_employee_count < 1
            ):
                rec.chain_employee_count = 1
            if rec.area_is_formula_chain and rec.order_line_ids:
                rec.order_line_ids._quoter_apply_chain_hours()

    def _quoter_apply_chain_hours_to_lines(self):
        """Propaga horas por rol desde tablas cadena (cantidad de empleados del bloque)."""
        lines = self.env["sale.order.line"]
        for block in self:
            area = block.area_id
            if not area or area.hour_matrix_mode != "formula_chain":
                continue
            block_lines = block.order_line_ids.filtered(
                lambda l: not l.display_type
                and l.product_id
                and not l.quoter_is_adjustment_line
                and getattr(l.product_id, "is_quoter_product", False)
            )
            lines |= block_lines
        if lines:
            lines._quoter_apply_chain_hours()
            for line in lines:
                if line.quoter_manual_load or line.quoter_manual_total_load:
                    continue
                price, _warn = line._quoter_compute_unit_price_from_ranges()
                line.with_context(
                    quoter_skip_chatter_log=True,
                    quoter_skip_block_product_refresh=True,
                ).write({"price_unit": price})

    def get_chain_quotation_preview_data(self):
        """Vista previa en cotización: tabla activa y horas por rol."""
        self.ensure_one()
        area = self.area_id
        if not area or area.hour_matrix_mode != "formula_chain":
            return {}
        count = int(self.chain_employee_count or 1)
        complexity_level = self.complexity_level_id
        table = area._chain_resolve_table_for_people(count)
        ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))
        prod_rows = []
        for line in self.order_line_ids.filtered(
            lambda l: not l.display_type
            and l.product_id
            and not l.quoter_is_adjustment_line
        ):
            tmpl = line.product_id.product_tmpl_id
            hours_map = area._chain_compute_hours_map_for_product(
                count, tmpl, complexity_level=complexity_level
            )
            prod_rows.append(
                {
                    "product_name": line.name or line.product_id.display_name,
                    "hours": [float(hours_map.get(r.id, 0.0)) for r in ranges],
                }
            )
        return {
            "block_id": self.id,
            "employee_count": count,
            "table_label": table.display_label if table else "",
            "table_id": table.id if table else False,
            "ranges": [{"id": r.id, "name": r.name} for r in ranges],
            "rows": prod_rows,
            "section_title": self.chain_matrix_section_title or "",
        }

    def matrix_preview_write_chain_employees(self, employee_count):
        self.ensure_one()
        try:
            val = int(float(employee_count or 1))
        except (TypeError, ValueError):
            raise UserError(_("Cantidad de empleados no válida.")) from None
        if val < 1:
            val = 1
        self.with_context(
            quoter_skip_chatter_log=True,
            quoter_skip_block_product_refresh=True,
        ).write({"chain_employee_count": val})
        self._quoter_apply_chain_hours_to_lines()
        return self.get_chain_quotation_preview_data()

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
            rec._quoter_auto_assign_complexity_level()
            if (
                rec.order_id
                and rec.order_id.quoter_is_first_quotation
                and rec.area_id.is_auditoria_area
            ):
                level = rec._quoter_highest_complexity_level()
                if level:
                    rec.complexity_level_id = level
            if (
                rec.complexity_level_id
                and rec.order_id
                and isinstance(rec.order_id.id, int)
                and not rec.area_id.is_auditoria_area
            ):
                rec.complexity_level_frozen = True
            if rec.area_id.hour_matrix_mode == "formula" and not rec.complexity_level_id:
                level = rec.area_id._formula_default_complexity_level()
                if level:
                    rec.complexity_level_id = level
            if (
                rec.area_id.hour_matrix_mode == "formula_chain"
                and not rec.complexity_level_id
            ):
                level = rec.area_id._chain_default_complexity_level()
                if level:
                    rec.complexity_level_id = level
        records._quoter_try_autoload_default_products()
        records.filtered("area_is_formula_chain")._quoter_apply_chain_hours_to_lines()
        records.filtered("area_is_regular_manual")._quoter_apply_area_configured_complexity_level()
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
                if cmd[0] == 1 and lid:
                    line_rec = Line.browse(lid)
                    if line_rec.exists() and line_rec.quoter_is_adjustment_line:
                        line_vals = dict(line_vals)
                        for fname in Line._QUOTER_RANGE_HOUR_FIELD_NAMES:
                            line_vals.pop(fname, None)
                        line_vals.pop("quoter_range_hour_ids", None)
                        line_vals.pop("quoter_total_hours", None)
                        line_vals.pop("price_unit", None)
                        if not line_vals:
                            continue
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

    def _quoter_resolve_product_for_block(self, product):
        """Variante del producto según nivel del bloque (o producto directo en área fórmula)."""
        self.ensure_one()
        product = product.exists()
        if not product:
            return product
        area = self.area_id
        if area.hour_matrix_mode in ("formula", "formula_chain", "regular_manual"):
            return product
        level = self.complexity_level_id
        if not level:
            raise UserError(
                _("Seleccione %(label)s antes de agregar productos.")
                % {"label": self._quoter_complexity_level_label()}
            )
        QuoterLine = self.env["quoter.service.line"]
        domain = [
            ("area_id", "=", area.id),
            "|",
            ("product_id", "=", product.id),
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
        ]
        qline = QuoterLine.search(domain, limit=1)
        if qline:
            variant = self._quoter_variant_for_level(qline, level)
            if variant:
                return variant
        return product

    def _quoter_prepare_sale_line_vals(self, product):
        """Valores listos para create() de sale.order.line en este bloque."""
        self.ensure_one()
        order = self.order_id
        area = self.area_id
        product = self._quoter_resolve_product_for_block(product)
        line_new = self.env["sale.order.line"].new(
            {
                "order_id": order,
                "product_id": product.id,
                "product_uom_qty": 1.0,
                "quoter_tab_area_id": area.id,
            }
        )
        if hasattr(line_new, "product_id_change"):
            line_new.product_id_change()
        if hasattr(line_new, "_onchange_product_id"):
            line_new._onchange_product_id()
        vals = line_new._convert_to_write(line_new._cache)
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
        if area.hour_matrix_mode == "formula":
            cfg = self.env["quoter.formula.product.config"].get_config_for_template(
                product.product_tmpl_id, area
            )
            if cfg and cfg.tipo_calculo == "fija":
                vals["quoter_formula_volume"] = 0.0
            else:
                vals["quoter_formula_volume"] = 1.0
        return vals

    def _quoter_bulk_add_lines_allowed(self):
        """Comprueba si el bloque puede usar carga múltiple (levanta UserError si no)."""
        self.ensure_one()
        if not self.area_id.bulk_line_load:
            raise UserError(_("La carga múltiple no está habilitada en esta área."))
        if self.state not in (False, "draft"):
            raise UserError(_("Solo se pueden agregar líneas en borrador."))
        if not isinstance(self.id, int):
            raise UserError(_("Guarde el bloque del área antes de cargar varios productos."))
        if not self.area_id or not self.order_id:
            raise UserError(_("Bloque o pedido incompleto."))
        if (
            self.area_id.hour_matrix_mode
            not in ("formula", "formula_chain", "regular_manual")
            and not self.complexity_level_id
        ):
            raise UserError(
                _(
                    "Seleccione el nivel del área y guarde el bloque antes de cargar productos."
                )
            )

    def _quoter_bulk_add_available_product_rows(self):
        """Lista de productos del área aún no usados en el bloque."""
        self.ensure_one()
        Product = self.env["product.product"]
        product_ids = Product._quoter_product_ids_for_area_picker(
            self.area_id, self.order_id
        )
        products = Product.browse(product_ids).sorted(
            key=lambda p: (p.display_name or "", p.id)
        )
        existing = self.order_id.order_line.filtered(
            lambda l, area=self.area_id: l.quoter_tab_area_id == area
            and l.product_id
            and not l.display_type
        )
        existing_product_ids = set(existing.mapped("product_id").ids)
        existing_tmpl_ids = set(existing.mapped("product_id.product_tmpl_id").ids)
        QuoterLine = self.env["quoter.service.line"]
        rows = []
        for product in products:
            if product.id in existing_product_ids:
                continue
            if product.product_tmpl_id.id in existing_tmpl_ids:
                continue
            qline = QuoterLine.search(
                [
                    ("area_id", "=", self.area_id.id),
                    "|",
                    ("product_id", "=", product.id),
                    ("product_tmpl_id", "=", product.product_tmpl_id.id),
                ],
                limit=1,
            )
            tag = qline.separator_tag_id if qline else self.env["quoter.line.separator.tag"]
            if tag:
                section_label = tag.name or ""
                separator_color = int(tag.color or 0)
                section_sort = (section_label or "").lower()
            else:
                section_label = _("Sin Etiqueta")
                separator_color = -1
                section_sort = "0_sin_etiqueta"
            rows.append(
                {
                    "product_id": product.id,
                    "section_name": section_label,
                    "section_label": section_label,
                    "separator_tag_id": tag.id if tag else False,
                    "separator_color": separator_color,
                    "section_sort": section_sort,
                    "product_name": product.display_name,
                }
            )
        rows.sort(
            key=lambda r: (
                r["section_sort"],
                (r["product_name"] or "").lower(),
                r["product_id"],
            )
        )
        return rows

    def _quoter_bulk_add_wizard_line_commands(self):
        self.ensure_one()
        self._quoter_bulk_add_lines_allowed()
        commands = [(5, 0, 0)]
        for row in self._quoter_bulk_add_available_product_rows():
            commands.append(
                (
                    0,
                    0,
                    {
                        "product_id": row["product_id"],
                        "product_name": row["product_name"],
                        "separator_tag_id": row["separator_tag_id"],
                        "section_label": row["section_label"],
                        "separator_color": row["separator_color"],
                        "section_sort": row["section_sort"],
                        "selected": True,
                    },
                )
            )
        return commands

    def action_quoter_open_bulk_add_wizard(self):
        """Abre el asistente para elegir varios productos del área."""
        self.ensure_one()
        self._quoter_bulk_add_lines_allowed()
        if not self._quoter_bulk_add_available_product_rows():
            raise UserError(_("No hay productos pendientes de cargar en este bloque."))
        # El diálogo lo abre JS en el form embebido (evita acción cliente que vacía la pantalla).
        return False

    def get_bulk_add_lines_data(self):
        """Productos del área aún no cargados (API legacy / JS)."""
        self.ensure_one()
        try:
            self._quoter_bulk_add_lines_allowed()
        except UserError as err:
            return {"enabled": False, "message": str(err.args[0])}
        rows = self._quoter_bulk_add_available_product_rows()
        return {
            "enabled": True,
            "products": [
                {
                    "product_id": r["product_id"],
                    "name": r["product_name"],
                    "section": r["section_label"],
                    "separator_color": r["separator_color"],
                }
                for r in rows
            ],
            "empty_message": _("No hay productos pendientes de cargar en este bloque."),
        }

    def action_quoter_bulk_add_lines(self, product_ids):
        """Crea líneas de pedido para los productos seleccionados y devuelve sync del bloque."""
        self.ensure_one()
        self._quoter_bulk_add_lines_allowed()
        order = self.order_id
        area = self.area_id
        ids = sorted({int(pid) for pid in (product_ids or []) if pid})
        if not ids:
            return self.action_quoter_get_block_order_line_sync()
        allowed = set(
            self.env["product.product"]._quoter_product_ids_for_area_picker(area, order)
        )
        ids = [pid for pid in ids if pid in allowed]
        if not ids:
            return self.action_quoter_get_block_order_line_sync()
        Product = self.env["product.product"]
        Line = self.env["sale.order.line"]
        ctx = dict(
            quoter_skip_separator_rebuild=True,
            quoter_skip_chatter_log=True,
            quoter_skip_block_product_refresh=True,
        )
        created_lines = Line.browse()
        for product in Product.browse(ids):
            vals = self._quoter_prepare_sale_line_vals(product)
            created_lines |= Line.with_context(ctx).create(vals)
        if created_lines:
            self._quoter_log_products_chatter(
                created_lines=created_lines,
                header=_("Carga múltiple de productos."),
            )
            self._quoter_sort_lines_by_separator_tag()
            order.with_context(quoter_skip_block_product_refresh=False)._quoter_refresh_block_selectable_products()
        order._quoter_refresh_area_lines_hours_from_levels(area)
        if created_lines:
            self._quoter_rebuild_separator_sections()
            order._quoter_sync_area_discount_total_line()
        return self.action_quoter_get_block_order_line_sync()

    def action_quoter_load_default_products(self):
        self.ensure_one()
        if not self.area_id.load_default_products:
            raise UserError(
                _(
                    "Esta área no utiliza carga de productos predeterminados. "
                    "Actívelo en la configuración del área si corresponde."
                )
            )
        if self.area_id.hour_matrix_mode == "regular_manual":
            raise UserError(
                _(
                    "El área Finanzas (regular manual) no utiliza productos predeterminados. "
                    "Agregue líneas manualmente."
                )
            )
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
            if area.hour_matrix_mode == "formula":
                cfg = self.env["quoter.formula.product.config"].get_config_for_template(
                    product.product_tmpl_id, area
                )
                if cfg and cfg.tipo_calculo == "fija":
                    vals["quoter_formula_volume"] = 0.0
                else:
                    vals["quoter_formula_volume"] = 1.0
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
        """Borra la línea en servidor de inmediato (evita id fantasma en el BasicModel).

        Devuelve la lista de res_id de líneas eliminadas del bloque, incluidas
        secciones de separador que _quoter_rebuild_separator_sections quite en cascada.
        """
        self.ensure_one()
        line = self.env["sale.order.line"].browse(line_id)
        if not self._quoter_line_belongs_to_block(line):
            return {"removed_ids": [], "line_ids": self.order_line_ids.ids}
        before_ids = set(self.order_line_ids.ids)
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
        after_ids = set(self.order_line_ids.ids)
        return {
            "removed_ids": list(before_ids - after_ids),
            "line_ids": self.order_line_ids.ids,
        }

    def action_quoter_get_block_order_line_sync(self):
        """Ids actuales de order_line_ids del bloque (fuente de verdad tras wizard/RPC)."""
        self.ensure_one()
        return {"line_ids": self.order_line_ids.ids}

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

    @api.depends("state", "order_id.quoter_workflow_state", "order_id.is_quotation")
    def _compute_block_lock_flags(self):
        for rec in self:
            st = rec.state or False
            wf = (
                rec.order_id.quoter_workflow_state
                if rec.order_id and rec.order_id.is_quotation
                else "en_preparacion"
            )
            workflow_editable = wf == "en_preparacion"
            rec.block_editable = st in (False, "draft") and workflow_editable
            rec.structure_locked = st in ("published", "cancel")
            rec.lines_frozen = st == "cancel" or not workflow_editable

    @api.depends("area_id", "area_id.name", "area_hour_matrix_mode")
    def _compute_formula_matrix_section_title(self):
        for rec in self:
            if rec.area_hour_matrix_mode != "formula" or not rec.area_id:
                rec.formula_matrix_section_title = False
                continue
            label = rec.area_id._quoter_formula_area_label()
            rec.formula_matrix_section_title = _(
                "Tabla %(area)s (volumen y horas por rol)"
            ) % {"area": label}

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
            if not rec.area_id or not rec.order_id:
                rec.selectable_product_ids = empty
                continue
            if rec.area_id.hour_matrix_mode in (
                "formula",
                "formula_chain",
                "regular_manual",
            ):
                rec.selectable_product_ids = Product.browse(
                    Product._quoter_product_ids_for_area_picker(rec.area_id, rec.order_id)
                )
                continue
            if not rec.complexity_level_id:
                rec.selectable_product_ids = empty
                continue
            rec.selectable_product_ids = Product.browse(
                Product._quoter_product_ids_for_area_picker(rec.area_id, rec.order_id)
            )

    def get_formula_matrix_preview_data(self):
        """Datos para tabla JS de fórmula en cotización (volumen × horas por rol)."""
        self.ensure_one()
        area = self.area_id
        FormulaConfig = self.env["quoter.formula.product.config"]
        Policy = self.env["quoter.hours.policy"]
        ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))
        range_cols = [{"id": r.id, "name": r.name} for r in ranges]
        rows = []
        lines = self.order_line_ids.filtered(
            lambda l: not l.display_type
            and l.product_id
            and not l.quoter_is_adjustment_line
            and getattr(l.product_id, "is_quoter_product", False)
        )
        for line in lines.sorted(key=lambda l: (l.sequence, l.id)):
            tmpl = line.product_id.product_tmpl_id
            config = FormulaConfig.get_config_for_template(tmpl, area)
            is_fixed = bool(config and config.tipo_calculo == "fija")
            volume = 0.0 if is_fixed else line._quoter_effective_formula_volume()
            hours_map = (
                line._quoter_formula_hours_map_for_config(config, area, volume)
                if config
                else {}
            )
            rows.append(
                {
                    "line_id": line.id,
                    "product_name": line.name or line.product_id.display_name,
                    "referencia": (config.referencia_volumen if config else "") or "",
                    "volume": volume,
                    "tipo_calculo": config.tipo_calculo if config else "formula",
                    "is_fixed": is_fixed,
                    "hours": [
                        line._quoter_apply_formula_output_hours(
                            area,
                            config,
                            volume,
                            float(hours_map.get(r.id, 0.0)),
                        )
                        for r in ranges
                    ],
                }
            )
        label = area._quoter_formula_area_label()
        return {
            "block_id": self.id,
            "area_id": area.id,
            "area_name": label,
            "section_title": self.formula_matrix_section_title
            or _("Tabla %(area)s (volumen y horas por rol)") % {"area": label},
            "matrix_read_only": bool(self.lines_frozen or not self.block_editable),
            "ranges": range_cols,
            "rows": rows,
            "empty_message": _(
                "Agregue productos en la lista para editar volúmenes de %(area)s."
            )
            % {"area": label},
        }

    def matrix_preview_write_formula_volume(self, line_id, volume):
        """Actualiza volumen de fórmula en línea y recalcula horas/precio."""
        self.ensure_one()
        line = self.env["sale.order.line"].browse(int(line_id)).exists()
        if not line or line.quoter_block_id != self:
            return self.get_formula_matrix_preview_data()
        area = self.area_id
        config = self.env["quoter.formula.product.config"].get_config_for_template(
            line.product_id.product_tmpl_id, area
        )
        if config and config.tipo_calculo == "fija":
            return self.get_formula_matrix_preview_data()
        vol = float(volume or 0.0)
        if vol <= 0.0:
            vol = 1.0
        line._quoter_persist_formula_volume_value(vol)
        price, _warn = line._quoter_compute_unit_price_from_ranges()
        line.with_context(quoter_skip_chatter_log=True).write({"price_unit": price})
        return self.get_formula_matrix_preview_data()

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

    @api.depends(
        "order_id.order_line",
        "order_id.order_line.price_subtotal",
        "order_id.order_line.quoter_tab_area_id",
        "order_id.order_line.quoter_separator_tag_id",
        "order_id.order_line.quoter_subtract_in_bpa",
        "order_id.order_line.quoter_range_hour_ids.hours",
        "order_id.order_line.quoter_range_hour_ids.area_range_id",
        "order_id.order_line.quoter_is_adjustment_line",
        "area_id",
        "area_id.area_range_ids",
        "area_id.is_payroll_area",
        "chain_employee_count",
        "order_id.partner_id",
        "order_id.pricelist_id",
        "order_id.date_order",
    )
    def _compute_bpa_summary_html(self):
        for rec in self:
            if not rec.area_id or not rec.order_id or not rec.area_id.is_payroll_area:
                rec.bpa_summary_html = False
            else:
                rec.bpa_summary_html = rec.order_id._quoter_build_bpa_summary_html(
                    rec.area_id, rec
                )

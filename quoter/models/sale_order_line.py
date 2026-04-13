# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

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

    quoter_range_hour_ids = fields.One2many(
        comodel_name="sale.order.line.range.hour",
        inverse_name="sale_line_id",
        string="Horas por rango",
        copy=True,
    )

    quoter_total_hours = fields.Float(
        string="Horas totales",
        compute="_compute_quoter_total_hours",
        store=True,
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

    @api.model_create_multi
    def create(self, vals_list):
        self._quoter_prepare_sequences_on_create_vals(vals_list)
        lines = super().create(vals_list)
        quoter_lines = lines.filtered(
            lambda l: l.order_id.is_quotation
            and l.quoter_tab_area_id
            and l.product_id
            and getattr(l.product_id, "is_quoter_product", False)
        )
        for line in quoter_lines:
            line._quoter_sync_range_hours()
            line._quoter_apply_level_template_hours()
        for line in quoter_lines:
            price, _warn = line._quoter_compute_unit_price_from_ranges()
            line.write({"price_unit": price})
        return lines

    def _quoter_block_level_for_line(self):
        self.ensure_one()
        order = self.order_id
        area = self.quoter_tab_area_id
        if not order or not area:
            return self.env["quoter.complexity.level"]
        block = order.quoter_area_block_ids.filtered(lambda b, a=area: b.area_id == a)[:1]
        return block.complexity_level_id if block else self.env["quoter.complexity.level"]

    def _quoter_apply_level_template_hours(self):
        """Copia horas de quoter.product.level.range (plantilla por nivel) a las filas de esta línea."""
        for line in self:
            if not line.order_id.is_quotation:
                continue
            if not line.product_id or not getattr(line.product_id, "is_quoter_product", False):
                continue
            area = line.quoter_tab_area_id
            if not area:
                continue
            level = line._quoter_block_level_for_line()
            if not level:
                continue
            tmpl = line.product_id.product_tmpl_id
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
                    row.hours = h

    @api.onchange("product_id")
    def _onchange_product_id_quoter_tab_area(self):
        tmpl = self.product_id.product_tmpl_id
        if self.product_id and tmpl and tmpl.quoter_area_id and not self.quoter_tab_area_id:
            self.quoter_tab_area_id = tmpl.quoter_area_id
        self._quoter_sync_range_hours()
        self._quoter_apply_level_template_hours()
        self._quoter_onchange_compute_price_from_ranges()

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
            if not self._quoter_block_level_for_line():
                return {"domain": {"product_id": [("id", "in", [])]}}
            area = self.quoter_tab_area_id
            svc_lines = self.env["quoter.service.line"].search([("area_id", "=", area.id)])
            product_ids = svc_lines.mapped("product_id").filtered(
                lambda p: p
                and p.sale_ok
                and not getattr(p, "is_quoter_range_rate_product", False)
            )
            domain = [
                ("sale_ok", "=", True),
                ("is_quoter_range_rate_product", "=", False),
                ("id", "in", product_ids.ids),
            ]
            return {"domain": {"product_id": domain}}
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
        res = super().write(vals)
        trigger_fields = {
            "product_id",
            "order_id",
            "quoter_tab_area_id",
            "quoter_range_hour_ids",
            "quoter_range_1_hours",
            "quoter_range_2_hours",
            "quoter_range_3_hours",
            "quoter_range_4_hours",
        }
        if set(vals.keys()) & trigger_fields:
            for line in self:
                if not line.product_id or not getattr(line.product_id, "is_quoter_product", False):
                    continue
                price, _warn = line._quoter_compute_unit_price_from_ranges()
                super(SaleOrderLine, line).write({"price_unit": price})
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
                line.quoter_range_hour_ids = [(5, 0, 0)]
                continue
            keep_ids = set(ranges.ids)
            existing_rows = line.quoter_range_hour_ids
            existing_by_range = {h.area_range_id.id: h for h in existing_rows if h.area_range_id}

            # En registros nuevos (NewId) no podemos hacer create/unlink en BD.
            in_db = isinstance(line.id, int)
            if in_db:
                # borrar filas que ya no aplican (por cambio de área o rangos)
                existing_rows.filtered(lambda h: h.area_range_id.id not in keep_ids).unlink()
                existing = set(line.quoter_range_hour_ids.mapped("area_range_id").ids)
                for r in ranges:
                    if r.id not in existing:
                        self.env["sale.order.line.range.hour"].create(
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
        for line in self:
            ranges = line._quoter_first_area_ranges(limit=4)
            if len(ranges) < index_1based:
                continue
            r = ranges[index_1based - 1]
            row = line.quoter_range_hour_ids.filtered(lambda h: h.area_range_id == r)[:1]
            if row:
                row.hours = value or 0.0
                continue
            if isinstance(line.id, int):
                self.env["sale.order.line.range.hour"].create(
                    {"sale_line_id": line.id, "area_range_id": r.id, "hours": value or 0.0}
                )
            else:
                # en memoria (NewId): agregar fila
                line.quoter_range_hour_ids = [
                    (0, 0, {"area_range_id": r.id, "hours": value or 0.0})
                ]

    def _inverse_quoter_range_1_hours(self):
        self._quoter_set_range_hours_by_index(1, self.quoter_range_1_hours)

    def _inverse_quoter_range_2_hours(self):
        self._quoter_set_range_hours_by_index(2, self.quoter_range_2_hours)

    def _inverse_quoter_range_3_hours(self):
        self._quoter_set_range_hours_by_index(3, self.quoter_range_3_hours)

    def _inverse_quoter_range_4_hours(self):
        self._quoter_set_range_hours_by_index(4, self.quoter_range_4_hours)

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
                self.invalidate_recordset(["sequence"])
                return candidate
        return seq

    def _quoter_validate_adjustment_create_permissions(self):
        self.ensure_one()
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
        new_line = self.create(
            {
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
        )
        new_line._quoter_sync_range_hours()
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

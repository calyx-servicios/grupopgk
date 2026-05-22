# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo import _, api, fields, models
from odoo.exceptions import MissingError, UserError, ValidationError
from odoo.tools.float_utils import float_is_zero
from odoo.tools import html_escape
from odoo.tools.misc import formatLang

from .quoter_chatter import (
    quoter_chatter_collect_changes,
    quoter_chatter_format_value,
    quoter_chatter_should_log,
)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    _QUOTER_ORDER_CHATTER_FIELDS = {
        "quoter_manager_id": _("Gerente responsable"),
        "quoter_partner_id": _("Socio asignado"),
        "quoter_q_competitors": _("Pregunta: otros estudios"),
        "quoter_q_budget": _("Pregunta: presupuesto del cliente"),
        "quoter_q_current_payment": _("Pregunta: pago al proveedor actual"),
        "quoter_q_notes": _("Observaciones estratégicas"),
        "date_order": _("Fecha de cotización"),
        "validity_date": _("Fecha de expiración"),
        "payment_term_id": _("Condición de pago"),
        "client_order_ref": _("Referencia del cliente"),
        "note": _("Notas"),
    }
    
    is_quotation = fields.Boolean(
        string="Es Cotización",
        default=lambda self: bool(self.env.context.get("default_is_quotation")),
        help="Indica si esta orden es una cotización profesional",
    )
    quoter_menu_context = fields.Boolean(
        compute="_compute_quoter_menu_context",
        string="Contexto menú Cotizador",
        help="True cuando la vista se abre con el contexto del menú Cotizador.",
    )
    
    quotation_sequence = fields.Char(
        string="Número de Cotización",
        readonly=True,
        copy=False,
        help="Número secuencial de cotización",
    )
    quoter_form_title = fields.Char(
        string="Referencia visible",
        compute="_compute_quoter_form_title",
        help="En cotizaciones profesionales muestra el número de cotización en el título del formulario.",
    )

    # Cabecera preventa PGK
    quoter_manager_id = fields.Many2one(
        comodel_name="res.users",
        string="Gerente responsable",
        copy=False,
        help="Usuario responsable (grupo Quoter - Gerente).",
    )
    quoter_partner_id = fields.Many2one(
        comodel_name="res.users",
        string="Socio asignado",
        copy=False,
        help="Usuario socio (grupo Quoter - Socio).",
    )

    quoter_user_can_edit_manager = fields.Boolean(
        compute="_compute_quoter_user_can_edit_fields",
    )
    quoter_user_can_edit_partner = fields.Boolean(
        compute="_compute_quoter_user_can_edit_fields",
    )
    quoter_user_is_assigned_manager = fields.Boolean(
        compute="_compute_quoter_user_can_edit_fields",
        string="Usuario es gerente asignado",
    )
    quoter_user_is_assigned_partner = fields.Boolean(
        compute="_compute_quoter_user_can_edit_fields",
        string="Usuario es socio asignado",
    )
    quoter_manager_candidate_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_quoter_candidate_users",
        string="Usuarios candidatos gerente",
    )
    quoter_partner_candidate_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_quoter_candidate_users",
        string="Usuarios candidatos socio",
    )

    # Preguntas estratégicas (max 140)
    quoter_q_competitors = fields.Char(
        string="¿Conoce si hay otros estudios presentándose a cotizar estos servicios?",
        size=140,
        copy=False,
    )
    quoter_q_budget = fields.Char(
        string="¿Conoce si el cliente cuenta con un presupuesto estimado o tiene información adicional del cliente?",
        size=140,
        copy=False,
    )
    quoter_q_current_payment = fields.Char(
        string="¿Conoce cuánto está pagando el cliente al proveedor actual?",
        size=140,
        copy=False,
    )
    quoter_q_notes = fields.Char(
        string="Otras observaciones que considere importante mencionar",
        size=140,
        copy=False,
    )

    quoter_area_ids = fields.Many2many(
        comodel_name="quoter.professional.area",
        relation="sale_order_quoter_area_rel",
        column1="order_id",
        column2="area_id",
        string="Áreas",
        domain="[('active', '=', True), ('cerrado', '=', True)]",
        help="Áreas de la cotización (máx. 5). Cada una tiene su pestaña en el cotizador.",
    )
    quoter_primary_area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área principal",
        compute="_compute_quoter_search_helper_fields",
        store=True,
    )
    quoter_primary_complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Complejidad principal",
        compute="_compute_quoter_search_helper_fields",
        store=True,
    )
    quoter_footer_area_discount_amount = fields.Monetary(
        string="Descuento/Recargo (áreas)",
        currency_field="currency_id",
        compute="_compute_quoter_footer_area_discount_amount",
        help="Total de la línea de pedido que agrupa descuentos/recargos globales por área (sin impuestos).",
    )

    @api.depends("is_quotation")
    def _compute_quoter_user_can_edit_fields(self):
        can_mgr = self.env.user.has_group("quoter.group_quoter_manager") or self.env.user.has_group("base.group_system")
        can_partner = self.env.user.has_group("quoter.group_quoter_partner") or self.env.user.has_group("base.group_system")
        current_user = self.env.user
        for order in self:
            order.quoter_user_can_edit_manager = bool(can_mgr)
            order.quoter_user_can_edit_partner = bool(can_partner)
            order.quoter_user_is_assigned_manager = bool(
                can_mgr and order.quoter_manager_id and order.quoter_manager_id == current_user
            )
            order.quoter_user_is_assigned_partner = bool(
                can_partner
                and order.quoter_partner_id
                and order.quoter_partner_id == current_user
            )

    def _check_quoter_partner_adjustment_write_access(self):
        """Descuento/recargo % por área: solo socio asignado (grupo Socio) o administrador."""
        self.ensure_one()
        if self.env.user.has_group("base.group_system"):
            return
        if not self.env.user.has_group("quoter.group_quoter_partner"):
            raise UserError(
                _("Solo usuarios del grupo Quoter - Socio pueden editar el porcentaje de descuento o recargo por área.")
            )
        if not self.quoter_partner_id:
            raise UserError(
                _("Defina un Socio asignado en la cotización para poder cargar porcentaje de descuento o recargo por área.")
            )
        if self.quoter_partner_id != self.env.user:
            raise UserError(
                _("Solo el socio asignado en la cotización puede editar el porcentaje de descuento o recargo por área.")
            )

    @api.depends()
    def _compute_quoter_candidate_users(self):
        User = self.env["res.users"]
        manager_group = self.env.ref("quoter.group_quoter_manager", raise_if_not_found=False)
        partner_group = self.env.ref("quoter.group_quoter_partner", raise_if_not_found=False)
        manager_users = User.browse()
        partner_users = User.browse()
        if manager_group:
            manager_users = manager_group.users.filtered(
                lambda u: u.active and not u.share
            )
        if partner_group:
            partner_users = partner_group.users.filtered(
                lambda u: u.active and not u.share
            )
        for order in self:
            order.quoter_manager_candidate_user_ids = manager_users
            order.quoter_partner_candidate_user_ids = partner_users

    def _check_quoter_responsibles_write_access(self, vals):
        """Valida que gerente/socio elegidos pertenezcan a su grupo (cualquiera puede asignarlos)."""
        if not vals:
            return
        manager_group = self.env.ref("quoter.group_quoter_manager", raise_if_not_found=False)
        partner_group = self.env.ref("quoter.group_quoter_partner", raise_if_not_found=False)
        if "quoter_manager_id" in vals and vals.get("quoter_manager_id"):
            manager_user = self.env["res.users"].browse(vals["quoter_manager_id"])
            if manager_group and manager_group not in manager_user.groups_id:
                raise UserError(
                    _("El usuario seleccionado en Gerente responsable debe pertenecer a Quoter - Gerente.")
                )
        if "quoter_partner_id" in vals and vals.get("quoter_partner_id"):
            partner_user = self.env["res.users"].browse(vals["quoter_partner_id"])
            if partner_group and partner_group not in partner_user.groups_id:
                raise UserError(
                    _("El usuario seleccionado en Socio asignado debe pertenecer a Quoter - Socio.")
                )

    @api.constrains(
        "quoter_q_competitors",
        "quoter_q_budget",
        "quoter_q_current_payment",
        "quoter_q_notes",
    )
    def _check_quoter_questions_length(self):
        for order in self:
            for fname in (
                "quoter_q_competitors",
                "quoter_q_budget",
                "quoter_q_current_payment",
                "quoter_q_notes",
            ):
                val = getattr(order, fname) or ""
                if len(val) > 140:
                    raise UserError(_("El campo no puede superar 140 caracteres."))

    @api.constrains(
        "is_quotation",
        "quoter_q_competitors",
        "quoter_q_budget",
        "quoter_q_current_payment",
        "quoter_q_notes",
    )
    def _check_quoter_strategic_questions_required(self):
        for order in self.filtered("is_quotation"):
            for fname in (
                "quoter_q_competitors",
                "quoter_q_budget",
                "quoter_q_current_payment",
                "quoter_q_notes",
            ):
                if not (getattr(order, fname) or "").strip():
                    raise UserError(
                        _("Las preguntas estratégicas son obligatorias en cotizaciones del cotizador.")
                    )

    def _quoter_order_line_existing(self):
        """Líneas del pedido que siguen en BD (evita MissingError tras borrar en bloque embebido)."""
        self.ensure_one()
        return self.order_line.exists()

    @api.constrains(
        "order_line",
        "order_line.quoter_is_adjustment_line",
        "order_line.quoter_adjustment_note",
        "order_line.display_type",
    )
    def _check_quoter_adjustment_notes_required(self):
        for order in self.filtered("is_quotation"):
            missing = order._quoter_order_line_existing().filtered(
                lambda l: not l.display_type
                and l.quoter_is_adjustment_line
                and not (l.quoter_adjustment_note or "").strip()
            )
            if missing:
                raise UserError(
                    _(
                        "Todas las líneas de ajuste deben tener observación. "
                        "Complete la observación en cada línea de ajuste antes de guardar."
                    )
                )

    quoter_area_block_ids = fields.One2many(
        comodel_name="quoter.sale.order.area",
        inverse_name="order_id",
        string="Bloques cotizador por área",
        copy=True,
    )
    # Solo UI (pestaña / JS): datos reales viven en quoter.sale.order.area.
    quoter_primary_tab_area_name = fields.Char(
        compute="_compute_quoter_primary_tab_area_meta",
        string="Nombre área pestaña principal",
    )
    quoter_area_block_count = fields.Integer(
        compute="_compute_quoter_primary_tab_area_meta",
        string="Cantidad de bloques cotizador",
    )

    def _quoter_area_blocks_ordered(self):
        """Bloques por secuencia de bloque + área; tolera NewId."""
        self.ensure_one()

        def sort_key(block):
            area = block.area_id
            seq = block.sequence or 0
            area_seq = (area.sequence or 0) if area else 0
            rid = area.id if area else False
            if isinstance(rid, int):
                return (seq, area_seq, 0, rid)
            origin = getattr(rid, "origin", None)
            if origin is not None:
                return (seq, area_seq, 0, int(origin))
            return (seq, area_seq, 1, str(rid))

        return self.quoter_area_block_ids.sorted(key=sort_key)

    @api.depends(
        "quoter_area_block_ids",
        "quoter_area_block_ids.sequence",
        "quoter_area_block_ids.area_id",
        "quoter_area_block_ids.area_id.name",
    )
    def _compute_quoter_primary_tab_area_meta(self):
        empty_block = self.env["quoter.sale.order.area"]
        for order in self:
            blocks = order._quoter_area_blocks_ordered()
            order.quoter_area_block_count = len(blocks)
            first = blocks[:1]
            block = first[0] if first else empty_block
            order.quoter_primary_tab_area_name = (
                (block.area_id.name if block and block.area_id else "") or ""
            )

    def _quoter_refresh_block_selectable_products(self):
        """Invalida listas de productos en bloques (p. ej. tras cambiar quoter.service.line)."""
        if self.env.context.get("quoter_skip_block_product_refresh"):
            return
        blocks = self.mapped("quoter_area_block_ids")
        if not blocks:
            return
        blocks.invalidate_cache(["selectable_product_ids"])

    # Se eliminó la lógica de "variantes por nivel" del pedido:
    # el producto real es único; la relación nivel+rango se gestiona en un modelo separado.

    def _quoter_refresh_area_lines_hours_from_levels(self, area):
        """Replica horas de quoter.product.level.range según el nivel del bloque del área."""
        self.ensure_one()
        if not area:
            return
        lines = self.order_line.filtered(
            lambda l, a=area: l.quoter_tab_area_id == a
            and l.product_id
            and getattr(l.product_id, "is_quoter_product", False)
            and not l.quoter_manual_load
            and not l.quoter_manual_total_load
        )
        for line in lines:
            line._quoter_sync_range_hours()
            line._quoter_apply_level_template_hours()
            price, _warn = line._quoter_compute_unit_price_from_ranges()
            line.write({"price_unit": price})

    def _quoter_sync_date_of_issue_from_order_date(self):
        """Cotización: fecha de emisión = fecha de cotización."""
        if "date_of_issue" not in self._fields:
            return
        for order in self.filtered("is_quotation"):
            if order.date_order:
                order.date_of_issue = order.date_order

    def _quoter_compute_validity_date_from_payment_term(self):
        """Cotización: vencimiento = fecha cotización + plazo de pago."""
        for order in self.filtered("is_quotation"):
            if not order.payment_term_id or not order.date_order:
                continue
            ref_dt = order.date_order
            if isinstance(ref_dt, str):
                ref_dt = fields.Datetime.from_string(ref_dt)
            ref_date = ref_dt.date() if hasattr(ref_dt, "date") else ref_dt
            terms = order.payment_term_id.compute(value=1.0, date_ref=ref_date)
            if terms:
                order.validity_date = terms[-1][0]

    def _quoter_message_post(self, body):
        """Registra en el chatter del pedido cambios del cotizador."""
        self.ensure_one()
        if not body or not hasattr(self, "message_post"):
            return
        self.message_post(body=body, subtype_xmlid="mail.mt_note")

    def _quoter_log_order_field_changes(self, vals):
        """Chatter al modificar campos del cotizador en el pedido."""
        if not vals or not quoter_chatter_should_log(self.env):
            return
        labels = self._QUOTER_ORDER_CHATTER_FIELDS
        tracked = {k: v for k, v in vals.items() if k in labels}
        if not tracked:
            return
        for order in self.filtered("is_quotation"):
            parts = quoter_chatter_collect_changes(order, tracked, labels)
            if parts:
                order._quoter_message_post(
                    _("<b>Cotización</b><br/>%s") % "<br/>".join(parts)
                )

    def _quoter_log_order_created(self):
        """Chatter al crear una cotización con datos del cotizador."""
        if not quoter_chatter_should_log(self.env):
            return
        labels = self._QUOTER_ORDER_CHATTER_FIELDS
        for order in self.filtered("is_quotation"):
            parts = []
            for fname, label in labels.items():
                val = order[fname]
                if val in (False, None, ""):
                    continue
                parts.append(
                    "%s: %s" % (label, quoter_chatter_format_value(order, fname, val))
                )
            if parts:
                order._quoter_message_post(
                    _("<b>Cotización creada</b><br/>%s") % "<br/>".join(parts)
                )

    @api.constrains("is_quotation", "date_order", "validity_date")
    def _check_quoter_validity_after_quotation_date(self):
        for order in self.filtered("is_quotation"):
            if not order.date_order or not order.validity_date:
                continue
            qdate = fields.Datetime.to_datetime(order.date_order).date()
            if order.validity_date < qdate:
                raise ValidationError(
                    _("La fecha de expiración no puede ser anterior a la fecha de cotización.")
                )

    def _quoter_resequence_area_blocks(self):
        for order in self:
            ordered_areas = order.quoter_area_ids.sorted(key=lambda a: (a.sequence or 0, a.id))
            for idx, area in enumerate(ordered_areas, start=1):
                block = order.quoter_area_block_ids.filtered(lambda b, a=area: b.area_id == a)[:1]
                if block and block.sequence != idx:
                    block.sequence = idx

    def _quoter_align_block_branches_with_area(self):
        """Si el área cambia sus ramas, alinea la rama seleccionada en cada bloque."""
        for order in self:
            for block in order.quoter_area_block_ids.filtered(lambda b: b.area_id):
                valid_branches = block.area_id._effective_branch_ids()
                if block.branch_id and block.branch_id in valid_branches:
                    continue
                block.branch_id = block.area_id._resolve_matrix_branch().id

    @api.depends(
        "quoter_area_ids",
        "quoter_area_ids.sequence",
        "quoter_area_block_ids",
        "quoter_area_block_ids.area_id",
        "quoter_area_block_ids.area_id.sequence",
        "quoter_area_block_ids.complexity_level_id",
    )
    def _compute_quoter_search_helper_fields(self):
        for order in self:
            ordered_areas = order.quoter_area_ids.sorted(key=lambda a: (a.sequence, a.id))
            primary_area = ordered_areas[:1]
            level = self.env["quoter.complexity.level"]
            if primary_area:
                block = order.quoter_area_block_ids.filtered(
                    lambda b, a=primary_area: b.area_id == a
                )[:1]
                level = block.complexity_level_id if block else self.env["quoter.complexity.level"]
            order.quoter_primary_area_id = primary_area
            order.quoter_primary_complexity_level_id = level

    @api.model
    def _quoter_block_adjustment_amounts(self, block):
        """Devuelve (descuento %, recargo %) no negativos; compatible con datos legacy."""
        if not block:
            return 0.0, 0.0
        raw_discount = float(block.global_discount_amount or 0.0)
        raw_surcharge = float(getattr(block, "global_surcharge_amount", 0.0) or 0.0)
        # Legacy: recargo como valor negativo en descuento.
        if raw_discount < 0.0:
            raw_surcharge += abs(raw_discount)
            raw_discount = 0.0
        return max(0.0, raw_discount), max(0.0, raw_surcharge)

    def _quoter_slot_subtotals_untaxed(self, area):
        """Subtotal productos y subtotal líneas de ajuste (sin impuestos) para un área."""
        self.ensure_one()
        if not area:
            return 0.0, 0.0
        olines = self.order_line.filtered(
            lambda l, a=area: not l.display_type and l.quoter_tab_area_id == a
        )
        prod = sum(olines.filtered(lambda l: not l.quoter_is_adjustment_line).mapped("price_subtotal"))
        adj = sum(olines.filtered(lambda l: l.quoter_is_adjustment_line).mapped("price_subtotal"))
        return float(prod or 0.0), float(adj or 0.0)

    @api.model
    def _quoter_format_number_es(self, value, decimals=2):
        """Número con separador de miles tipo es_AR (sin depender del usuario)."""
        fmt = "{:,.%sf}" % int(decimals)
        s = fmt.format(float(value or 0.0))
        return s.replace(",", "X").replace(".", ",").replace("X", ".")

    def _quoter_slot_hours_base_and_adjustment(self, area, limit=4):
        """Suma horas por rango: [base por rango], [ajuste por rango]."""
        self.ensure_one()
        base = [0.0] * limit
        adj = [0.0] * limit
        if not area:
            return base, adj
        ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:limit]
        range_ids = [r.id for r in ranges]
        if not range_ids:
            return base, adj
        lines = self.order_line.filtered(
            lambda l, a=area: not l.display_type and l.quoter_tab_area_id == a
        )
        for line in lines:
            by_range = {
                h.area_range_id.id: float(h.hours or 0.0)
                for h in line.quoter_range_hour_ids
                if h.area_range_id
            }
            target = adj if line.quoter_is_adjustment_line else base
            for idx, rid in enumerate(range_ids):
                if idx < limit:
                    target[idx] += by_range.get(rid, 0.0)
        return base, adj

    def _quoter_slot_range_rates(self, area, limit=4):
        """Tarifa/h por rango (lista misma longitud que rangos del área)."""
        self.ensure_one()
        rates = [0.0] * limit
        if not area:
            return rates, self.env["quoter.area.complexity.range"].browse()
        ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:limit]
        pl = area.pricelist_id or self.pricelist_id
        if not pl:
            return rates, ranges
        partner = self.partner_id or self.env["res.partner"]
        tmpl_model = self.env["product.template"]
        for idx, range_rec in enumerate(ranges):
            if idx >= limit:
                break
            tmpl = tmpl_model.search(
                [
                    ("is_quoter_range_rate_product", "=", True),
                    ("quoter_range_rate_area_id", "=", area.id),
                    ("quoter_range_rate_range_id", "=", range_rec.id),
                ],
                limit=1,
            )
            variant = tmpl.product_variant_id if tmpl else self.env["product.product"]
            if not variant:
                continue
            rates[idx] = float(
                pl.get_product_price(
                    variant,
                    1.0,
                    partner,
                    date=self.date_order,
                    uom_id=variant.uom_id.id,
                )
                or 0.0
            )
        return rates, ranges

    def _quoter_build_area_summary_html(self, area, block):
        """Resumen por rango (estilo filas/columnas tipo planilla, sin tabla HTML)."""
        self.ensure_one()
        if not area:
            return False
        limit = 4
        base_h, adj_h = self._quoter_slot_hours_base_and_adjustment(area, limit=limit)
        rates, ranges = self._quoter_slot_range_rates(area, limit=limit)
        disc_pct, sur_pct = self._quoter_block_adjustment_amounts(block)
        rate_factor = 1.0 - (disc_pct / 100.0) + (sur_pct / 100.0)
        tot_h = [base_h[i] + adj_h[i] for i in range(limit)]
        adj_rates = [max(0.0, rates[i] * rate_factor) for i in range(limit)]
        base_vals = [base_h[i] * rates[i] for i in range(limit)]
        final_vals = [tot_h[i] * adj_rates[i] for i in range(limit)]

        def esc(t):
            return html_escape(t or "")

        col_labels = []
        for i in range(limit):
            if i < len(ranges) and ranges[i]:
                col_labels.append(esc(ranges[i].name or str(i + 1)))
            else:
                col_labels.append("—")
        col_labels.append(esc(_("Total")))

        def cells_numeric(values, decimals=2, money=False, total_mode="sum"):
            out = []
            for i in range(limit):
                pref = "$" if money else ""
                out.append(pref + self._quoter_format_number_es(values[i], decimals=decimals))
            if total_mode == "sum":
                tot = sum(values)
                pref = "$" if money else ""
                out.append(pref + self._quoter_format_number_es(tot, decimals=decimals))
            else:
                out.append("—")
            return out

        def cells_pct_same(pct, decimals=2):
            s = self._quoter_format_number_es(pct, decimals=decimals) + "%"
            return [s] * (limit + 1)

        olines = self.order_line.filtered(
            lambda l, a=area: not l.display_type and l.quoter_tab_area_id == a
        )
        adj_lines = olines.filtered(lambda l: l.quoter_is_adjustment_line)
        if len(adj_lines) == 1:
            adj_title = _("Ajuste de horas - %s") % (
                adj_lines[0].name or adj_lines[0].product_id.display_name or ""
            )
        elif adj_lines:
            adj_title = _("Ajuste de horas (suma de %s líneas)") % len(adj_lines)
        else:
            adj_title = _("Ajuste de horas")

        rows_html = []
        # Misma base tipográfica que el bloque oe_subtotal_footer (sin "small", tamaño heredado del formulario).
        style_grid = (
            "display:grid;"
            "grid-template-columns:minmax(11rem,16rem) repeat(5, minmax(4.5rem, 1fr));"
            "column-gap:.5rem;row-gap:.4rem;align-items:center;"
            "font-size:inherit;line-height:1.45;"
        )
        style_hdr = "font-weight:600;font-size:inherit;color:#1f2937;"
        style_lbl = "font-weight:400;font-size:inherit;"
        style_lbl_total = "font-weight:700;font-size:inherit;"
        style_cell = (
            "text-align:right;font-variant-numeric:tabular-nums;"
            "font-size:inherit;font-weight:400;"
        )
        style_cell_total = (
            "text-align:right;font-variant-numeric:tabular-nums;"
            "font-size:inherit;font-weight:700;"
        )

        hdr = [f'<div style="{style_hdr}"></div>']
        for lab in col_labels:
            hdr.append(f'<div style="{style_hdr}{style_cell}">{lab}</div>')
        rows_html.append(f'<div style="{style_grid}">{"".join(hdr)}</div>')

        def add_row(label, cell_strings, strong=False):
            ls = style_lbl_total if strong else style_lbl
            cs = style_cell_total if strong else style_cell
            parts = [f'<div style="{ls}">{esc(label)}</div>']
            for c in cell_strings:
                parts.append(f'<div style="{cs}">{esc(c)}</div>')
            rows_html.append(f'<div style="{style_grid}">{"".join(parts)}</div>')

        add_row(_("Totales (horas)"), cells_numeric(base_h, decimals=2))
        add_row(_("Tarifa online"), cells_numeric(rates, decimals=2, money=True, total_mode="none"))
        add_row(_("Valor total"), cells_numeric(base_vals, decimals=2, money=True))
        rows_html.append(
            '<div class="mt-2 mb-1" '
            'style="font-weight:600;font-size:inherit;line-height:1.45;color:#1f2937;">'
            f"{esc(_('Ajuste de horas'))}</div>"
        )
        add_row(adj_title, cells_numeric(adj_h, decimals=2))
        add_row(_("Totales horas"), cells_numeric(tot_h, decimals=2))
        add_row(_("Tarifa online"), cells_numeric(rates, decimals=2, money=True, total_mode="none"))
        add_row(_("Descuento"), cells_pct_same(disc_pct))
        add_row(_("Recargo"), cells_pct_same(sur_pct))
        add_row(_("Tarifa ajustada"), cells_numeric(adj_rates, decimals=2, money=True, total_mode="none"))
        add_row(_("Valor total"), cells_numeric(final_vals, decimals=2, money=True), strong=True)

        return (
            '<div class="o_quoter_area_summary" style="width:52rem;max-width:100%;margin-left:auto;margin-right:0;font-size:inherit;color:#1f2937;">'
            + "".join(rows_html)
            + "</div>"
        )

    @api.depends()
    def _compute_quoter_menu_context(self):
        active = bool(self.env.context.get("quoter_use_cot_sequence"))
        for order in self:
            order.quoter_menu_context = active

    @api.depends(
        "is_quotation",
        "order_line",
        "order_line.price_subtotal",
        "order_line.quoter_is_area_discount_total_line",
        "order_line.display_type",
    )
    def _compute_quoter_footer_area_discount_amount(self):
        for order in self:
            if not order.is_quotation:
                order.quoter_footer_area_discount_amount = 0.0
                continue
            lines = order.order_line.filtered(
                lambda l: l.quoter_is_area_discount_total_line and not l.display_type
            )
            order.quoter_footer_area_discount_amount = sum(lines.mapped("price_subtotal"))

    @api.depends_context("lang")
    @api.depends(
        "order_line.tax_id",
        "order_line.price_unit",
        "amount_total",
        "amount_untaxed",
        "is_quotation",
        "order_line.price_subtotal",
        "order_line.quoter_is_area_discount_total_line",
        "order_line.display_type",
    )
    def _compute_tax_totals_json(self):
        """Añade fila Descuento/Recargo (áreas) al JSON del widget de totales (misma clave que en factura)."""
        super()._compute_tax_totals_json()
        untaxed_amount_label = _("Untaxed Amount")
        for order in self:
            if not order.tax_totals_json:
                continue
            totals = json.loads(order.tax_totals_json)
            extra_rows = [
                row
                for row in totals.get("extra_rows", [])
                if row.get("key") != "quoter_area_discount"
            ]
            area_amount = 0.0
            if order.is_quotation:
                area_amount = sum(
                    order.order_line.filtered(
                        lambda l: l.quoter_is_area_discount_total_line
                        and not l.display_type
                    ).mapped("price_subtotal")
                )
            rounding = (
                order.currency_id.rounding
                or order.company_id.currency_id.rounding
                or 0.01
            )
            if rounding <= 0:
                rounding = 0.01
            if not float_is_zero(
                area_amount,
                precision_rounding=rounding,
            ):
                extra_rows.append(
                    {
                        "key": "quoter_area_discount",
                        "label": _("Descuento/Recargo (áreas)"),
                        "amount": area_amount,
                        "formatted_amount": formatLang(
                            self.env,
                            area_amount,
                            currency_obj=order.currency_id,
                        ),
                        "after_subtotal": untaxed_amount_label,
                    }
                )
            if extra_rows:
                totals["extra_rows"] = extra_rows
            else:
                totals.pop("extra_rows", None)
            order.tax_totals_json = json.dumps(totals)

    @api.depends("is_quotation", "quotation_sequence", "name")
    def _compute_quoter_form_title(self):
        for order in self:
            if order.is_quotation:
                order.quoter_form_title = (
                    order.quotation_sequence or order.name or ""
                )
            else:
                order.quoter_form_title = False

    def name_get(self):
        res = super().name_get()
        if not res:
            return res
        by_id = {oid: name for oid, name in res}
        out = []
        for record in self:
            disp = by_id.get(record.id, record.name or "")
            if record.is_quotation and record.quotation_sequence:
                disp = record.quotation_sequence
            out.append((record.id, disp))
        return out

    def _quoter_sale_name_is_placeholder(self):
        """Nombre aún no asignado por el flujo estándar (evita pisar un S... ya generado)."""
        self.ensure_one()
        mark = _("New")
        name = (self.name or "").strip()
        return not name or name == mark

    def _quoter_prepare_vals_for_create(self, vals):
        """Cotización: solo consume ``quoter.quotation`` (Q…).

        Se asigna ``name`` igual al número Q para que ``sale.order``:create no llame a la secuencia
        estándar de pedidos (evita saltos 8183–8184 al crear una cotización entre dos ventas).

        - ``is_quotation`` puede no venir en el primer ``create`` del formulario.
        - La acción del menú Cotizador envía ``default_is_quotation`` y ``quoter_use_cot_sequence``.
        """
        ctx = self.env.context
        if ctx.get("quoter_use_cot_sequence"):
            vals["is_quotation"] = True
        elif "is_quotation" not in vals and "default_is_quotation" in ctx:
            vals["is_quotation"] = ctx["default_is_quotation"]
        if not vals.get("is_quotation"):
            return
        if not vals.get("quotation_sequence"):
            vals["quotation_sequence"] = (
                self.env["ir.sequence"].next_by_code("quoter.quotation") or "/"
            )
        vals["name"] = vals["quotation_sequence"]

    def _quoter_guard_quotation_name_before_sale_create(self, vals):
        """Refuerzo: si ``sale.order``:create ve ``name`` == _('New'), consume ``sale.order``.

        Odoo 15 usa ``model_create_multi`` y vuelve a fusionar defaults; además el orden de
        herencias puede dejar ``name`` en placeholder pese a ser cotización PGK.

        Repite la lógica de contexto de ``_quoter_prepare_vals_for_create`` para no depender
        del orden entre ambos si en el futuro se refactoriza.
        """
        ctx = self.env.context
        if ctx.get("quoter_use_cot_sequence"):
            vals["is_quotation"] = True
        elif "is_quotation" not in vals and "default_is_quotation" in ctx:
            vals["is_quotation"] = ctx["default_is_quotation"]
        if not vals.get("is_quotation"):
            return
        mark = _("New")
        name = vals.get("name")
        if name and name != mark:
            return
        if not vals.get("quotation_sequence"):
            vals["quotation_sequence"] = (
                self.env["ir.sequence"].next_by_code("quoter.quotation") or "/"
            )
        vals["name"] = vals["quotation_sequence"]

    def _quoter_apply_default_sales_setup(self, vals):
        """Completa valores por defecto de cabecera desde Ajustes del Cotizador."""
        if not vals.get("is_quotation"):
            return
        icp = self.env["ir.config_parameter"].sudo()
        defaults_map = (
            ("pricelist_id", "quoter.default_pricelist_id", "product.pricelist"),
            ("payment_term_id", "quoter.default_payment_term_id", "account.payment.term"),
            ("team_id", "quoter.default_team_id", "crm.team"),
        )
        for field_name, param_key, model_name in defaults_map:
            if field_name not in self._fields or vals.get(field_name):
                continue
            raw_id = icp.get_param(param_key)
            if not raw_id:
                continue
            try:
                rec_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            rec = self.env[model_name].browse(rec_id)
            if rec.exists():
                vals[field_name] = rec.id

    def _quoter_apply_hidden_fields_policy(self, vals, force=False):
        """Para cotizaciones, limpia campos ocultos de la UI."""
        if not force and not vals.get("is_quotation"):
            return
        for field_name in ("note", "internal_notes"):
            if field_name in self._fields:
                vals[field_name] = False
        # Campo custom de "socio" (distinto a Socio asignado): oculto y desactivado.
        if "partner" in self._fields:
            vals["partner"] = False
        # Pestaña de firma del cliente oculta para cotizaciones.
        if "require_signature" in self._fields:
            vals["require_signature"] = False

    @api.model_create_multi
    def create(self, vals_list):
        # Normalizar como BaseModel (dict único → lista de un elemento).
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            self._check_quoter_responsibles_write_access(vals)
            merged = self._add_missing_default_values(dict(vals or {}))
            vals.clear()
            vals.update(merged)
            self._quoter_prepare_vals_for_create(vals)
            self._quoter_guard_quotation_name_before_sale_create(vals)
            self._quoter_apply_default_sales_setup(vals)
            self._quoter_apply_hidden_fields_policy(vals)
            self._quoter_sanitize_quoter_area_block_commands(vals)
            if vals.get("is_quotation") or self.env.context.get("default_is_quotation"):
                cmds = self._quoter_filter_quotation_order_line_commands(vals.get("order_line"))
                if cmds:
                    vals["order_line"] = cmds
                    self._quoter_sanitize_order_line_commands(vals)
                else:
                    vals.pop("order_line", None)
            else:
                self._quoter_sanitize_order_line_commands(vals)
        records = super().create(vals_list)
        for order, vals in zip(records, vals_list):
            order._sync_quoter_area_blocks()
            order._quoter_autoload_default_products_after_save(trigger_vals=vals)
            if order.is_quotation:
                order._quoter_sync_area_discount_total_line()
                order._quoter_sync_date_of_issue_from_order_date()
                order._quoter_compute_validity_date_from_payment_term()
        records.filtered("is_quotation")._quoter_reconcile_area_ids_from_blocks()
        records.filtered("is_quotation")._quoter_log_order_created()
        return records

    def write(self, vals):
        self._check_quoter_responsibles_write_access(vals)
        if vals:
            vals = self._quoter_protect_area_ids_write_vals(vals)
        if vals and "quoter_area_block_ids" in vals:
            vals = dict(vals)
            self._quoter_sanitize_quoter_area_block_commands(vals)
        if vals and "order_line" in vals:
            vals = dict(vals)
            if self.filtered("is_quotation"):
                # Las líneas de cotización se editan solo en quoter.sale.order.area (form embebido).
                vals.pop("order_line", None)
            else:
                self._quoter_sanitize_order_line_commands(vals)
        quotation_write = self.filtered(
            lambda o: o.is_quotation and isinstance(o.id, int)
        )
        if quotation_write:
            quotation_write.invalidate_cache(fnames=["order_line"])
        if vals is not None and self.env.context.get("quoter_use_cot_sequence"):
            vals = dict(vals)
            vals["is_quotation"] = True
        if vals and (
            vals.get("is_quotation")
            or any(order.is_quotation for order in self)
        ):
            vals = dict(vals)
            self._quoter_apply_hidden_fields_policy(
                vals, force=not vals.get("is_quotation")
            )
        date_triggers = {"date_order", "payment_term_id"}
        area_change_snapshots = []
        if vals and "quoter_area_ids" in vals:
            for order in self:
                if order.is_quotation or vals.get("is_quotation"):
                    area_change_snapshots.append((order, order.quoter_area_ids))
        try:
            res = super().write(vals)
        except MissingError:
            if not quotation_write:
                raise
            quotation_write.invalidate_cache(fnames=["order_line"])
            safe_vals = dict(vals or {})
            safe_vals.pop("order_line", None)
            res = super().write(safe_vals)
        if vals:
            self.filtered(lambda o: o.is_quotation)._quoter_log_order_field_changes(vals)
        if area_change_snapshots:
            for order, old_areas in area_change_snapshots:
                if not order.is_quotation:
                    continue
                new_areas = order.quoter_area_ids
                added = new_areas - old_areas
                removed = old_areas - new_areas
                parts = []
                if added:
                    parts.append(
                        _("Áreas agregadas al presupuesto: %s")
                        % ", ".join(added.mapped("name"))
                    )
                if removed:
                    parts.append(
                        _("Áreas quitadas del presupuesto: %s")
                        % ", ".join(removed.mapped("name"))
                    )
                if parts:
                    order._quoter_message_post("<br/>".join(parts))
        if date_triggers & set(vals.keys()):
            self.filtered("is_quotation")._quoter_sync_date_of_issue_from_order_date()
            self.filtered("is_quotation")._quoter_compute_validity_date_from_payment_term()
        if "quoter_area_ids" in vals or "is_quotation" in vals:
            self._sync_quoter_area_blocks()
        self.filtered("is_quotation")._quoter_reconcile_area_ids_from_blocks()
        if vals:
            self._quoter_autoload_default_products_after_save(trigger_vals=vals)
        # Refuerzo: sincronizar siempre después de guardar para evitar que comandos
        # de order_line del formulario pisen la línea técnica.
        quotation_orders = self.filtered(
            lambda o: o.is_quotation and isinstance(o.id, int)
        )
        if quotation_orders:
            quotation_orders.invalidate_cache(["order_line"])
            quotation_orders._quoter_sync_area_discount_total_line()
        # Solo registros ya guardados (id entero). Con NewId aún no hay fila en BD:
        # pedir la secuencia aquí consumía Q... al editar el formulario antes del 1er guardado.
        missing_seq = self.filtered(
            lambda o: o.is_quotation
            and not o.quotation_sequence
            and isinstance(o.id, int)
        )
        if missing_seq:
            seq_env = self.env["ir.sequence"]
            for order in missing_seq:
                qref = seq_env.next_by_code("quoter.quotation") or "/"
                patch = {"quotation_sequence": qref}
                if order._quoter_sale_name_is_placeholder():
                    patch["name"] = qref
                super(SaleOrder, order).write(patch)
        return res

    def _quoter_autoload_default_products_after_save(self, trigger_vals=None):
        """Al guardar: predeterminados solo cuando cambian las áreas (no en cada create/write)."""
        trigger_vals = trigger_vals or {}
        if "quoter_area_ids" not in trigger_vals:
            return
        if self.env.context.get("quoter_skip_autoload_default_products"):
            return

        ctx = dict(
            self.env.context,
            quoter_skip_block_product_refresh=True,
            quoter_skip_autoload_default_products=True,
        )
        for order in self.with_context(ctx):
            if not order.is_quotation:
                continue
            blocks = order.quoter_area_block_ids.filtered(
                lambda b: b.state in (False, "draft") and b.complexity_level_id
            )
            for block in blocks:
                block.action_quoter_load_default_products()
            order._quoter_refresh_block_selectable_products()

    def _quoter_load_default_products_onchange(self):
        """En el formulario: cargar líneas predeterminadas por área (sin depender del nivel)."""
        self.ensure_one()
        if not self.is_quotation:
            return
        QuoterLine = self.env["quoter.service.line"]
        for area in self.quoter_area_ids:
            default_lines = QuoterLine.search(
                [("area_id", "=", area.id), ("is_default_product", "=", True)]
            )
            for qline in default_lines:
                tmpl = qline.product_tmpl_id or (
                    qline.product_id and qline.product_id.product_tmpl_id
                )
                product = tmpl.product_variant_id if tmpl else qline.product_id
                if not product:
                    continue
                exists = self.order_line.filtered(
                    lambda l, a=area, p=product: l.quoter_tab_area_id == a and l.product_id == p
                )[:1]
                if exists:
                    continue
                line_new = self.env["sale.order.line"].new(
                    {
                        "order_id": self,
                        "product_id": product.id,
                        "product_uom_qty": 1.0,
                        "quoter_tab_area_id": area.id,
                    }
                )
                if hasattr(line_new, "product_id_change"):
                    line_new.product_id_change()
                if hasattr(line_new, "_onchange_product_id"):
                    line_new._onchange_product_id()
                self.order_line += line_new

    @api.model
    def _quoter_area_ids_cmds_clear_all(self, commands):
        """True si los comandos vacían por completo el many2many de áreas."""
        if not commands:
            return True
        if not isinstance(commands, list):
            return False
        if commands == [(5, 0, 0)]:
            return True
        if len(commands) == 1:
            cmd = commands[0]
            if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 6:
                return not bool(cmd[2])
        return False

    def _quoter_protect_area_ids_write_vals(self, vals):
        """Evita que un guardado del formulario borre áreas ya elegidas por error de cliente."""
        if not vals or "quoter_area_ids" not in vals:
            return vals
        if self._quoter_area_ids_cmds_clear_all(vals["quoter_area_ids"]):
            if any(
                o.is_quotation and o.quoter_area_block_ids.mapped("area_id")
                for o in self
            ):
                vals = dict(vals)
                vals.pop("quoter_area_ids", None)
        return vals

    def _quoter_reconcile_area_ids_from_blocks(self):
        """Tras guardar: si hay bloques con área, el m2m de cabecera debe coincidir."""
        for order in self.filtered("is_quotation"):
            block_areas = order.quoter_area_block_ids.mapped("area_id")
            if not block_areas:
                continue
            if set(block_areas.ids) != set(order.quoter_area_ids.ids):
                order.quoter_area_ids = block_areas

    def _quoter_sanitize_quoter_area_block_commands(self, vals, order=None):
        """Descarta comandos x2many inválidos sobre ``quoter_area_block_ids``.

        El formulario embebido del one2many puede dejar en el BasicModel un ``(0, 0, vals)``
        sin ``area_id``; al guardar el pedido desde otra pestaña Odoo intentaría crear el
        bloque y falla por el campo obligatorio. Aquí filtramos esos comandos y evitamos
        que el cliente borre ``area_id`` en un ``(1, id, vals)``.
        """
        cmds = vals.get("quoter_area_block_ids")
        if not cmds or not isinstance(cmds, list):
            return vals
        order_rec = (order or self)[:1]
        order_id = order_rec.id if order_rec and isinstance(order_rec.id, int) else False
        new_cmds = []
        for cmd in cmds:
            if isinstance(cmd, (list, tuple)) and len(cmd) >= 1:
                op = cmd[0]
                if op == 0 and len(cmd) >= 3 and isinstance(cmd[2], dict):
                    sub = dict(cmd[2])
                    if not sub.get("area_id"):
                        continue
                    if not order_id:
                        # Cotización nueva (sin id en BD): el onchange deja (0,0) sin
                        # pedido; _sync_quoter_area_blocks los crea tras el create.
                        continue
                    sub.setdefault("order_id", order_id)
                    new_cmds.append((0, 0, sub))
                    continue
                if op == 1 and len(cmd) >= 3 and isinstance(cmd[2], dict):
                    sub = dict(cmd[2])
                    if "area_id" in sub and not sub.get("area_id"):
                        sub.pop("area_id", None)
                    # Las líneas del bloque se guardan solo en el form embebido; evita ids
                    # de sección borrados en el BasicModel del pedido padre.
                    if "order_line_ids" in sub:
                        sub.pop("order_line_ids", None)
                    if not sub:
                        continue
                    new_cmds.append((1, cmd[1], sub))
                    continue
            new_cmds.append(cmd)
        if not new_cmds and cmds:
            vals.pop("quoter_area_block_ids", None)
        else:
            vals["quoter_area_block_ids"] = new_cmds
        return vals

    def read(self, fields=None, load="_classic_read"):
        """En cotizaciones el pedido no edita líneas de bloques (solo vía form embebido)."""
        result = super().read(fields=fields, load=load)
        if fields is None or "order_line" in fields:
            Line = self.env["sale.order.line"]
            for values in result:
                order = self.browse(values["id"])
                if not order.is_quotation:
                    continue
                # sudo: filtrar ids fantasma sin fallar si alguna línea no es legible.
                parent_lines = order.sudo().order_line.filtered(
                    lambda l: not l.quoter_block_id
                )
                values["order_line"] = [
                    lid
                    for lid in parent_lines.sorted(
                        key=lambda l: (int(l.sequence or 0), l.id)
                    ).ids
                    if Line.sudo().browse(lid).exists()
                ]
        return result

    @api.model
    def _quoter_filter_onchange_order_line_values(self, commands):
        """Quita comandos/ids de líneas borradas o del cotizador embebido (antes del onchange)."""
        if not commands or not isinstance(commands, list):
            return commands or []
        Line = self.env["sale.order.line"]
        filtered = []
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)):
                continue
            op = cmd[0]
            if op == 6 and len(cmd) >= 3 and isinstance(cmd[2], (list, tuple)):
                ids = [lid for lid in cmd[2] if isinstance(lid, int)]
                if not ids:
                    filtered.append((6, 0, []))
                    continue
                lines = Line.browse(ids).exists()
                parent_ids = lines.filtered(lambda l: not l.quoter_block_id).ids
                filtered.append((6, 0, parent_ids))
                continue
            if op in (1, 2, 3, 4) and len(cmd) >= 2:
                line = Line.browse(cmd[1])
                if not line.exists() or line.quoter_block_id:
                    continue
            if op == 0 and len(cmd) >= 3 and isinstance(cmd[2], dict):
                sub = cmd[2]
                if sub.get("quoter_block_id") or sub.get("quoter_tab_area_id"):
                    continue
            filtered.append(cmd)
        return filtered

    def onchange(self, values, field_name, field_onchange):
        """Evita MissingError cuando el cliente pide onchange con líneas ya borradas en bloque."""
        values = dict(values or {})
        is_quotation = values.get("is_quotation")
        if is_quotation is None and self:
            is_quotation = self[:1].is_quotation
        if is_quotation:
            if self:
                self.invalidate_cache(fnames=["order_line"])
            if values.get("order_line"):
                values["order_line"] = self._quoter_filter_onchange_order_line_values(
                    values["order_line"]
                )
        try:
            result = super().onchange(values, field_name, field_onchange)
        except MissingError:
            if not is_quotation:
                raise
            result = {
                "warning": {
                    "title": _("Registro actualizado"),
                    "message": _(
                        "Se eliminó una línea de la cotización; recargue el formulario si los totales no coinciden."
                    ),
                },
            }
        if not result or not isinstance(result, dict):
            return result
        order_vals = result.get("value") or {}
        if is_quotation and order_vals.get("order_line"):
            order_vals["order_line"] = self._quoter_filter_onchange_order_line_values(
                order_vals["order_line"]
            )
            result["value"] = order_vals
        elif is_quotation and "value" in result and not order_vals:
            # Evita que el cliente interprete value:{} como borrar todo el formulario.
            result.pop("value", None)
        return result

    def _quoter_filter_quotation_order_line_commands(self, commands):
        """Descarta comandos del pedido sobre líneas que gestiona quoter.sale.order.area."""
        if not commands or not isinstance(commands, list):
            return []
        Line = self.env["sale.order.line"]
        filtered = []
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)):
                filtered.append(cmd)
                continue
            op = cmd[0]
            if op == 6:
                continue
            if op in (1, 2, 3, 4) and len(cmd) >= 2:
                line = Line.browse(cmd[1])
                if not line.exists() or line.quoter_block_id:
                    continue
            if op == 0 and len(cmd) >= 3 and isinstance(cmd[2], dict):
                sub = cmd[2]
                if sub.get("quoter_block_id") or sub.get("quoter_tab_area_id"):
                    continue
            filtered.append(cmd)
        return filtered

    def _quoter_sanitize_order_line_commands(self, vals):
        """Completa campos mínimos en comandos de order_line para no violar constraints SQL."""
        cmds = vals.get("order_line")
        if not cmds or not isinstance(cmds, list):
            return vals
        Product = self.env["product.product"]
        new_cmds = []
        for cmd in cmds:
            if (
                isinstance(cmd, (list, tuple))
                and len(cmd) >= 3
                and cmd[0] in (0, 1)
                and isinstance(cmd[2], dict)
            ):
                line_vals = dict(cmd[2])
                if not line_vals.get("display_type"):
                    product_id = line_vals.get("product_id")
                    product = Product.browse(product_id) if product_id else Product
                    if product and product.exists():
                        line_vals.setdefault("product_uom_qty", 1.0)
                        if not line_vals.get("product_uom"):
                            line_vals["product_uom"] = product.uom_id.id
                        if not line_vals.get("name"):
                            line_vals["name"] = (
                                product.get_product_multiline_description_sale()
                                or product.display_name
                            )
                new_cmds.append((cmd[0], cmd[1], line_vals))
                continue
            new_cmds.append(cmd)
        vals["order_line"] = new_cmds
        return vals

    def _sync_quoter_area_blocks(self):
        Block = self.env["quoter.sale.order.area"]
        for order in self:
            if not order.is_quotation:
                order.quoter_area_block_ids.unlink()
                continue
            keep = order.quoter_area_ids
            order.quoter_area_block_ids.filtered(lambda b: b.area_id not in keep).unlink()
            have = order.quoter_area_block_ids.mapped("area_id")
            for area in keep:
                if area not in have:
                    Block.create(
                        {
                            "order_id": order.id,
                            "area_id": area.id,
                            "branch_id": area._resolve_matrix_branch().id,
                        }
                    )
            order._quoter_resequence_area_blocks()
            order._quoter_align_block_branches_with_area()

    def _quoter_area_discount_line_product(self):
        return self.env.ref("quoter.product_quoter_area_discount_sum", raise_if_not_found=False)

    def _quoter_sync_area_discount_total_line(self):
        """Sincroniza una sola línea contable con el neto Descuento/Recargo de áreas."""
        self.ensure_one()
        if not self.is_quotation:
            return
        product = self._quoter_area_discount_line_product()
        if not product:
            return
        line_model = self.env["sale.order.line"]
        discount_lines = self._quoter_order_line_existing().filtered(
            "quoter_is_area_discount_total_line"
        )
        total_discount = 0.0
        total_surcharge = 0.0
        for block in self.quoter_area_block_ids:
            if not block.area_id:
                continue
            prod, adj = self._quoter_slot_subtotals_untaxed(block.area_id)
            sub = prod + adj
            disc_pct, surcharge_pct = self._quoter_block_adjustment_amounts(block)
            total_discount += sub * (disc_pct / 100.0)
            total_surcharge += sub * (surcharge_pct / 100.0)
        # Neto: descuento resta, recargo suma.
        line_amount = float(total_surcharge or 0.0) - float(total_discount or 0.0)
        rounding = self.currency_id.rounding or 0.01
        if float_is_zero(line_amount, precision_rounding=rounding):
            if discount_lines:
                discount_lines.unlink()
            return
        vals = {
            "order_id": self.id,
            "company_id": self.company_id.id,
            "product_id": product.id,
            "name": _("Descuento/Recargo global de áreas"),
            "product_uom_qty": 1.0,
            "product_uom": product.uom_id.id,
            "price_unit": line_amount,
            "tax_id": [(6, 0, [])],
            "discount": 0.0,
            "quoter_is_area_discount_total_line": True,
        }
        if discount_lines:
            discount_lines[0].write(vals)
            if len(discount_lines) > 1:
                discount_lines[1:].unlink()
        else:
            vals["sequence"] = (
                max(self._quoter_order_line_existing().mapped("sequence") or [0]) + 1
            )
            line_model.create(vals)

    def action_confirm(self):
        for order in self:
            if order.is_quotation:
                draft_blocks = order.quoter_area_block_ids.filtered(
                    lambda b: b.state == "draft"
                )
                if draft_blocks:
                    raise UserError(
                        _(
                            "No puede confirmar: hay cotización por área abierta (sin cerrar): %s."
                        )
                        % ", ".join(draft_blocks.mapped("area_id.display_name"))
                    )
                order._quoter_sync_area_discount_total_line()
        return super().action_confirm()

    @api.onchange("is_quotation")
    def _onchange_is_quotation(self):
        if not self.is_quotation:
            self.quoter_area_ids = [(5, 0, 0)]
            self.quoter_area_block_ids = [(5, 0, 0)]

    @api.onchange("date_order", "payment_term_id", "is_quotation")
    def _onchange_quoter_dates_and_payment_term(self):
        if self.is_quotation:
            self._quoter_sync_date_of_issue_from_order_date()
            self._quoter_compute_validity_date_from_payment_term()

    @api.onchange("quoter_area_ids")
    def _onchange_quoter_area_ids(self):
        if not self.quoter_area_ids:
            self.quoter_area_block_ids = [(5, 0, 0)]
            return
        self._sync_quoter_area_blocks_onchange()
        self._quoter_align_block_branches_with_area()
        self._quoter_load_default_products_onchange()

    def _sync_quoter_area_blocks_onchange(self):
        selected = set(self.quoter_area_ids.ids)
        cmds = []
        for block in self.quoter_area_block_ids:
            if block.area_id.id not in selected:
                cmds.append((2, block.id))
        existing = set(self.quoter_area_block_ids.mapped("area_id").ids) & selected
        for aid in selected:
            if aid not in existing:
                area = self.env["quoter.professional.area"].browse(aid)
                nvals = {
                    "area_id": aid,
                    "branch_id": area._resolve_matrix_branch().id if area else False,
                }
                if isinstance(self.id, int):
                    nvals["order_id"] = self.id
                cmds.append((0, 0, nvals))
        if cmds:
            self.quoter_area_block_ids = cmds
        self._quoter_resequence_area_blocks()

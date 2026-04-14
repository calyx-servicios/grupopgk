# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
        default=10,
        help="Orden de las pestañas del cotizador para este pedido (1=primera, 2=segunda...).",
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
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="order_id.currency_id",
        string="Moneda",
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

    @api.constrains("global_discount_amount", "global_surcharge_amount")
    def _check_non_negative_adjustments(self):
        for rec in self:
            if (rec.global_discount_amount or 0.0) < 0.0:
                raise ValidationError(_("El descuento (%) del área no puede ser negativo."))
            if (rec.global_surcharge_amount or 0.0) < 0.0:
                raise ValidationError(_("El recargo (%) del área no puede ser negativo."))

    @api.onchange("area_id")
    def _onchange_area_id_clear_level(self):
        if self.area_id and self.complexity_level_id:
            if self.complexity_level_id not in self.area_id.complexity_level_ids:
                self.complexity_level_id = False

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

    @api.onchange("complexity_level_id")
    def _onchange_complexity_level_load_defaults(self):
        """Al seleccionar nivel, cargar productos predeterminados del área/nivel."""
        for rec in self:
            if rec.state != "draft":
                continue
            order = rec.order_id
            area = rec.area_id
            if not order or not area or not order.is_quotation:
                continue

            default_lines = rec._quoter_default_service_lines()
            default_products = default_lines.mapped("product_id").filtered(lambda p: p and p.sale_ok)

            # Limpiar solo líneas predeterminadas de esta área (no tocar las manuales).
            # Se identifica como "predeterminada" si el producto está marcado como predeterminado en quoter.service.line del área.
            all_default_area_products = (
                self.env["quoter.service.line"]
                .search([("area_id", "=", area.id), ("is_default_product", "=", True)])
                .mapped("product_id")
            )
            to_remove = order.order_line.filtered(
                lambda l: l.quoter_tab_area_id == area and l.product_id in all_default_area_products
            )
            if to_remove:
                order.order_line -= to_remove

            # Agregar faltantes (sin duplicar).
            existing_products = order.order_line.filtered(lambda l: l.quoter_tab_area_id == area).mapped(
                "product_id"
            )
            missing = default_products - existing_products
            for product in missing:
                order.order_line += self.env["sale.order.line"].new(
                    {
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": 1.0,
                        "product_uom": product.uom_id.id,
                        "quoter_tab_area_id": area.id,
                    }
                )

            order._quoter_refresh_area_lines_hours_from_levels(area)

    def write(self, vals):
        if {"global_discount_amount", "global_surcharge_amount"} & set(vals.keys()):
            for rec in self:
                if rec.order_id:
                    rec.order_id._check_quoter_partner_adjustment_write_access()
        res = super().write(vals)
        if {"global_discount_amount", "global_surcharge_amount"} & set(vals.keys()):
            for rec in self:
                if rec.order_id and rec.order_id.is_quotation:
                    rec.order_id._quoter_sync_area_discount_total_line()
        if "complexity_level_id" in vals:
            for rec in self:
                if rec.order_id and rec.area_id:
                    rec.order_id._quoter_refresh_area_lines_hours_from_levels(rec.area_id)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.order_id and rec.order_id.is_quotation:
                rec.order_id._quoter_sync_area_discount_total_line()
        return records

    def unlink(self):
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
            self.env["sale.order.line"].create(vals)
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

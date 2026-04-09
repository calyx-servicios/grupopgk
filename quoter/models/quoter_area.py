# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models


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
        string="Cerrado",
        default=False,
        groups="base.group_system",
        help="Solo administradores Odoo: marca de control para evitar cambios accidentales "
        "en la configuración del área.",
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
        res = super().write(vals)
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
        return res

    def _sync_product_level_range_hour_lines(self):
        """Filas de horas en plantillas quoter.product.level.range al cambiar rangos del área."""
        lr = self.env["quoter.product.level.range"].search([("area_id", "in", self.ids)])
        lr._sync_range_hour_lines()

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

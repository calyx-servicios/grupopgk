# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class QuoterProductLevelRangeHour(models.Model):
    _name = "quoter.product.level.range.hour"
    _description = "Horas por rango real (plantilla producto + nivel)"
    _order = "area_range_sequence, id"

    level_range_id = fields.Many2one(
        comodel_name="quoter.product.level.range",
        string="Plantilla nivel",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rango del área",
        required=True,
        ondelete="restrict",
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
            "uniq_level_range_area_range",
            "UNIQUE(level_range_id, area_range_id)",
            "Ya hay horas cargadas para ese rango en esta plantilla de nivel.",
        )
    ]

    @api.constrains("area_range_id", "level_range_id")
    def _check_range_in_area(self):
        for row in self:
            area = row.level_range_id.area_id
            if area and row.area_range_id and row.area_range_id not in area.area_range_ids:
                raise ValidationError(
                    _("El rango debe estar entre los rangos configurados en el área del producto.")
                )


class QuoterProductLevelRange(models.Model):
    _name = "quoter.product.level.range"
    _description = "Rangos por nivel para producto del área (cotizador)"
    _order = "complexity_level_id, id"

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Producto (plantilla)",
        required=True,
        ondelete="cascade",
        index=True,
    )
    canonical_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto cotizador",
        compute="_compute_canonical_product_id",
        store=False,
        help="Variante principal usada en el pedido (línea de servicio del área).",
    )
    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área",
        related="product_tmpl_id.quoter_area_id",
        store=True,
        readonly=True,
    )
    complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel",
        required=True,
        ondelete="restrict",
        index=True,
    )

    range_hour_ids = fields.One2many(
        comodel_name="quoter.product.level.range.hour",
        inverse_name="level_range_id",
        string="Horas por rango del área",
    )
    total_hours = fields.Float(
        string="Horas totales",
        compute="_compute_total_hours",
        store=False,
    )

    # Columnas lista: hasta 4 rangos del área (orden sequence, id) — editan range_hour_ids.
    slot_1_range_name = fields.Char(
        string="Nombre rango 1",
        compute="_compute_slot_range_names",
        store=False,
    )
    slot_1_hours = fields.Float(
        string="Horas (rango 1)",
        compute="_compute_slot_hours",
        inverse="_inverse_slot_1_hours",
        store=False,
    )
    slot_2_range_name = fields.Char(
        string="Nombre rango 2",
        compute="_compute_slot_range_names",
        store=False,
    )
    slot_2_hours = fields.Float(
        string="Horas (rango 2)",
        compute="_compute_slot_hours",
        inverse="_inverse_slot_2_hours",
        store=False,
    )
    slot_3_range_name = fields.Char(
        string="Nombre rango 3",
        compute="_compute_slot_range_names",
        store=False,
    )
    slot_3_hours = fields.Float(
        string="Horas (rango 3)",
        compute="_compute_slot_hours",
        inverse="_inverse_slot_3_hours",
        store=False,
    )
    slot_4_range_name = fields.Char(
        string="Nombre rango 4",
        compute="_compute_slot_range_names",
        store=False,
    )
    slot_4_hours = fields.Float(
        string="Horas (rango 4)",
        compute="_compute_slot_hours",
        inverse="_inverse_slot_4_hours",
        store=False,
    )

    _sql_constraints = [
        (
            "uniq_product_level",
            "unique(product_tmpl_id, complexity_level_id)",
            "Ya existe una configuración para este producto y nivel.",
        )
    ]

    @api.depends("range_hour_ids", "range_hour_ids.hours")
    def _compute_total_hours(self):
        for rec in self:
            rec.total_hours = sum(rec.range_hour_ids.mapped("hours"))

    def _area_ranges_slot(self, index):
        """Rango del área en posición index (0..3), o vacío."""
        self.ensure_one()
        if index < 0 or index > 3:
            return self.env["quoter.area.complexity.range"]
        if not self.area_id:
            return self.env["quoter.area.complexity.range"]
        ranges = self.area_id.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:4]
        if index >= len(ranges):
            return self.env["quoter.area.complexity.range"]
        return ranges[index]

    @api.depends(
        "area_id",
        "area_id.area_range_ids",
        "area_id.area_range_ids.sequence",
        "area_id.area_range_ids.name",
    )
    def _compute_slot_range_names(self):
        for rec in self:
            for i in range(4):
                ar = rec._area_ranges_slot(i)
                rec["slot_%d_range_name" % (i + 1)] = ar.name if ar else ""

    @api.depends(
        "area_id",
        "area_id.area_range_ids",
        "range_hour_ids",
        "range_hour_ids.hours",
        "range_hour_ids.area_range_id",
    )
    def _compute_slot_hours(self):
        for rec in self:
            for i in range(4):
                ar = rec._area_ranges_slot(i)
                if not ar:
                    rec["slot_%d_hours" % (i + 1)] = 0.0
                    continue
                row = rec.range_hour_ids.filtered(
                    lambda h, a=ar: h.area_range_id == a
                )[:1]
                rec["slot_%d_hours" % (i + 1)] = row.hours if row else 0.0

    def _write_slot_hours(self, slot_index, value):
        for rec in self:
            rec._sync_range_hour_lines()
            ar = rec._area_ranges_slot(slot_index)
            if not ar:
                continue
            row = rec.range_hour_ids.filtered(
                lambda h, a=ar: h.area_range_id == a
            )[:1]
            if row:
                row.hours = float(value or 0.0)

    def _inverse_slot_1_hours(self):
        self._write_slot_hours(0, self.slot_1_hours)

    def _inverse_slot_2_hours(self):
        self._write_slot_hours(1, self.slot_2_hours)

    def _inverse_slot_3_hours(self):
        self._write_slot_hours(2, self.slot_3_hours)

    def _inverse_slot_4_hours(self):
        self._write_slot_hours(3, self.slot_4_hours)

    @api.depends("product_tmpl_id")
    def _compute_canonical_product_id(self):
        QuoterLine = self.env["quoter.service.line"]
        for rec in self:
            qsl = QuoterLine.search([("product_tmpl_id", "=", rec.product_tmpl_id.id)], limit=1)
            rec.canonical_product_id = qsl.product_id if qsl else False

    @api.constrains("complexity_level_id", "area_id")
    def _check_level_in_area(self):
        for rec in self:
            if rec.area_id and rec.complexity_level_id and rec.complexity_level_id not in rec.area_id.complexity_level_ids:
                raise ValidationError(
                    _("El nivel debe pertenecer a los niveles configurados en el área «%s».")
                    % rec.area_id.display_name
                )

    def _sync_range_hour_lines(self):
        """Alinear filas con los rangos del área (máx. 4)."""
        Line = self.env["quoter.product.level.range.hour"]
        for rec in self:
            area = rec.area_id
            if not area:
                rec.range_hour_ids.unlink()
                continue
            ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:4]
            keep_ids = set(ranges.ids)
            rec.range_hour_ids.filtered(lambda h: h.area_range_id.id not in keep_ids).unlink()
            existing = set(rec.range_hour_ids.mapped("area_range_id").ids)
            for ar in ranges:
                if ar.id not in existing:
                    Line.create(
                        {
                            "level_range_id": rec.id,
                            "area_range_id": ar.id,
                            "hours": 0.0,
                        }
                    )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_range_hour_lines()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "product_tmpl_id" in vals:
            self._sync_range_hour_lines()
        return res

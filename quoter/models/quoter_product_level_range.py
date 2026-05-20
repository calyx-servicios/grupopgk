# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class QuoterProductLevelRangeMatrixB(models.Model):
    """Tabla B (factor % o multiplicador por rol). Sin dependencias ascendentes."""

    _name = "quoter.product.level.range.matrix.b"
    _description = "Cotizador — matriz B (factor por rol)"
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
        string="Rol del área",
        required=True,
        ondelete="restrict",
        index=True,
    )
    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )
    factor = fields.Float(
        string="Factor tabla B",
        default=0.0,
        help="Porcentaje: final = A × (factor ÷ 100). Multiplicador: final = A × factor.",
    )

    _sql_constraints = [
        (
            "uniq_plr_matrix_b_range",
            "UNIQUE(level_range_id, area_range_id)",
            "Ya existe un factor B para ese rol en esta plantilla.",
        )
    ]

    @api.constrains("area_range_id", "level_range_id")
    def _check_range_in_area(self):
        for row in self:
            area = row.level_range_id.area_id
            if area and row.area_range_id and row.area_range_id not in area.area_range_ids:
                raise ValidationError(
                    _("El rol debe estar entre los roles configurados en el área del producto.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        Policy = self.env["quoter.hours.policy"]
        if not Policy._quoter_skip_strict_hours_validation():
            for vals in vals_list:
                if "factor" in vals:
                    kind = "percent"
                    if vals.get("level_range_id"):
                        lr = self.env["quoter.product.level.range"].browse(
                            vals["level_range_id"]
                        )
                        if lr:
                            kind = lr._table_b_kind()
                    Policy.validate_matrix_b_factor_positive(vals["factor"], kind)
        recs = super().create(vals_list)
        if not self.env.context.get("quoter_skip_b_percent_validation"):
            for lr in recs.mapped("level_range_id"):
                if lr.area_id and lr.area_id.quoter_config_edit_mode:
                    continue
                lr._check_matrix_b_percent_split_cap()
        return recs

    def write(self, vals):
        if "factor" in vals:
            Policy = self.env["quoter.hours.policy"]
            if not Policy._quoter_skip_strict_hours_validation() and not self.env.context.get(
                "quoter_skip_b_percent_validation"
            ):
                for row in self:
                    Policy.validate_matrix_b_factor_positive(
                        vals.get("factor", row.factor),
                        row.level_range_id._table_b_kind(),
                    )
        res = super().write(vals)
        if "factor" in vals and not self.env.context.get("quoter_skip_b_percent_validation"):
            for lr in self.mapped("level_range_id"):
                if lr.area_id and lr.area_id.quoter_config_edit_mode:
                    continue
                lr._check_matrix_b_percent_split_cap()
        if "factor" in vals:
            lrs = self.mapped("level_range_id")
            ars = self.mapped("area_range_id")
            outs = self.env["quoter.product.level.range.output"].search(
                [
                    ("level_range_id", "in", lrs.ids),
                    ("area_range_id", "in", ars.ids),
                ]
            )
            outs._recompute_combined_hours()
        return res


class QuoterProductLevelRangeMatrixA(models.Model):
    """Tabla A (horas base por rol). La B del mismo rol se usa solo por coincidencia de rol."""

    _name = "quoter.product.level.range.matrix.a"
    _description = "Cotizador — matriz A (horas base por rol)"
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
        string="Rol del área",
        required=True,
        ondelete="restrict",
        index=True,
    )
    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )
    matrix_b_id = fields.Many2one(
        comodel_name="quoter.product.level.range.matrix.b",
        string="Fila tabla B (obsoleto)",
        required=False,
        ondelete="set null",
        index=True,
    )
    hours = fields.Float(string="Horas tabla A", default=0.0)

    output_line_ids = fields.One2many(
        comodel_name="quoter.product.level.range.output",
        inverse_name="matrix_a_id",
        string="Salida de horas",
    )

    _sql_constraints = [
        (
            "uniq_plr_matrix_a_range",
            "UNIQUE(level_range_id, area_range_id)",
            "Ya existe tabla A para ese rol en esta plantilla.",
        )
    ]

    @api.constrains("area_range_id", "level_range_id", "matrix_b_id")
    def _check_b_matches_range(self):
        for row in self:
            if not row.matrix_b_id:
                continue
            if row.matrix_b_id.level_range_id != row.level_range_id:
                raise ValidationError(_("La fila B debe pertenecer a la misma plantilla de nivel."))
            if row.matrix_b_id.area_range_id != row.area_range_id:
                raise ValidationError(_("La fila B debe ser del mismo rol que la tabla A."))
            area = row.level_range_id.area_id
            if area and row.area_range_id not in area.area_range_ids:
                raise ValidationError(
                    _("El rol debe estar entre los roles configurados en el área del producto.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        Policy = self.env["quoter.hours.policy"]
        if not Policy._quoter_skip_strict_hours_validation():
            for vals in vals_list:
                if "hours" in vals:
                    Policy.validate_hours_strictly_positive(
                        vals["hours"], _("Horas tabla A")
                    )
        return super().create(vals_list)

    def write(self, vals):
        if "hours" in vals:
            Policy = self.env["quoter.hours.policy"]
            if not Policy._quoter_skip_strict_hours_validation():
                Policy.validate_hours_strictly_positive(vals["hours"], _("Horas tabla A"))
        res = super().write(vals)
        if "hours" in vals:
            self.output_line_ids._recompute_combined_hours()
        return res


class QuoterProductLevelRangeOutput(models.Model):
    """Horas que usa el cotizador / pedido. En modo combinado se calculan desde A → B; en regular se editan aquí."""

    _name = "quoter.product.level.range.output"
    _description = "Cotizador — horas finales por rol (salida)"
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
        string="Rol del área",
        required=True,
        ondelete="restrict",
        index=True,
    )
    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )
    matrix_a_id = fields.Many2one(
        comodel_name="quoter.product.level.range.matrix.a",
        string="Fila tabla A",
        ondelete="set null",
        index=True,
        help="Si está definida y el área es combinada, las horas se calculan desde A y B.",
    )
    hours = fields.Float(string="Horas finales", default=0.0)

    _sql_constraints = [
        (
            "uniq_plr_output_range",
            "UNIQUE(level_range_id, area_range_id)",
            "Ya hay una salida de horas para ese rol en esta plantilla.",
        )
    ]

    @api.constrains("area_range_id", "level_range_id")
    def _check_range_in_area(self):
        for row in self:
            area = row.level_range_id.area_id
            if area and row.area_range_id and row.area_range_id not in area.area_range_ids:
                raise ValidationError(
                    _("El rol debe estar entre los roles configurados en el área del producto.")
                )

    def _recompute_combined_hours(self):
        for rec in self:
            lr = rec.level_range_id
            if not lr.area_id or lr.area_id.hour_matrix_mode != "combined":
                continue
            if not rec.matrix_a_id:
                continue
            brow = lr.matrix_b_ids.filtered(
                lambda b, ar=rec.area_range_id: b.area_range_id == ar
            )[:1]
            if not brow:
                continue
            h = lr._final_hours_from_a_and_b(
                rec.matrix_a_id.hours,
                brow.factor,
            )
            if float(rec.hours or 0.0) != float(h):
                super(QuoterProductLevelRangeOutput, rec).write({"hours": h})

    @api.model_create_multi
    def create(self, vals_list):
        Policy = self.env["quoter.hours.policy"]
        if not Policy._quoter_skip_strict_hours_validation():
            for vals in vals_list:
                if "hours" in vals:
                    Policy.validate_hours_strictly_positive(
                        vals["hours"], _("Horas finales")
                    )
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("quoter_skip_output_hours_guard"):
            res = super().write(vals)
            if "matrix_a_id" in vals:
                self._recompute_combined_hours()
            return res
        if "hours" in vals:
            Policy = self.env["quoter.hours.policy"]
            if not Policy._quoter_skip_strict_hours_validation():
                locked = self.filtered(lambda r: r._is_combined_locked())
                unlocked = self - locked
                if unlocked:
                    Policy.validate_hours_strictly_positive(
                        vals["hours"], _("Horas finales")
                    )
        if "hours" not in vals:
            res = super().write(vals)
            if "matrix_a_id" in vals:
                self._recompute_combined_hours()
            return res
        locked = self.filtered(lambda r: r._is_combined_locked())
        unlocked = self - locked
        res = True
        if unlocked:
            res = super(QuoterProductLevelRangeOutput, unlocked).write(vals)
        if locked:
            vals_no_h = {k: v for k, v in vals.items() if k != "hours"}
            if vals_no_h:
                res = super(QuoterProductLevelRangeOutput, locked).write(vals_no_h) and res
        if "matrix_a_id" in vals:
            self._recompute_combined_hours()
        return res

    def _is_combined_locked(self):
        self.ensure_one()
        return (
            self.level_range_id.area_id
            and self.level_range_id.area_id.hour_matrix_mode == "combined"
            and bool(self.matrix_a_id)
        )


class QuoterProductLevelRange(models.Model):
    _name = "quoter.product.level.range"
    _description = "Roles por nivel para producto del área (cotizador)"
    _order = "complexity_level_sequence, id"

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
    area_quoter_config_edit_mode = fields.Boolean(
        related="area_id.quoter_config_edit_mode",
        string="Área en edición de configuración",
        readonly=True,
    )
    complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel",
        required=True,
        ondelete="restrict",
        index=True,
    )
    branch_id = fields.Many2one(
        comodel_name="quoter.area.branch",
        string="Rama",
        required=False,
        ondelete="restrict",
        index=True,
        default=lambda self: self.env.ref(
            "quoter.quoter_area_branch_unique", raise_if_not_found=False
        ),
    )
    complexity_level_sequence = fields.Integer(
        string="Secuencia nivel",
        related="complexity_level_id.sequence",
        store=True,
        readonly=True,
        index=True,
    )
    area_hour_matrix_mode = fields.Selection(
        related="area_id.hour_matrix_mode",
        string="Modo tabla (área)",
        readonly=True,
    )
    area_table_a_layout = fields.Selection(
        related="area_id.table_a_layout",
        string="Formato A (área)",
        readonly=True,
    )
    area_table_b_kind = fields.Selection(
        related="area_id.table_b_kind",
        string="Tipo B (área)",
        readonly=True,
    )
    area_table_b_percent_mode = fields.Selection(
        related="area_id.table_b_percent_mode",
        string="Modo porcentaje B (área)",
        readonly=True,
    )

    matrix_b_ids = fields.One2many(
        comodel_name="quoter.product.level.range.matrix.b",
        inverse_name="level_range_id",
        string="Tabla B",
    )
    matrix_a_ids = fields.One2many(
        comodel_name="quoter.product.level.range.matrix.a",
        inverse_name="level_range_id",
        string="Tabla A",
    )
    output_line_ids = fields.One2many(
        comodel_name="quoter.product.level.range.output",
        inverse_name="level_range_id",
        string="Horas finales (salida)",
    )

    compact_hours_a = fields.Float(
        string="Horas únicas (tabla A unificada)",
        compute="_compute_compact_hours_a",
        inverse="_inverse_compact_hours_a",
        store=False,
        readonly=False,
        digits=(12, 2),
        help="Política definida en el área. Replica horas en todas las filas A al guardar.",
    )
    matrix_b_factor_sum = fields.Float(
        string="Suma porcentajes tabla B",
        compute="_compute_matrix_b_factor_sum",
        digits=(12, 2),
        readonly=True,
        help="Solo en modo tabla A unificada y tipo B porcentaje: la suma debe ser 100 al guardar.",
    )

    total_hours = fields.Float(
        string="Horas totales",
        compute="_compute_total_hours",
        store=False,
    )

    slot_1_range_name = fields.Char(
        string="Nombre rol 1",
        compute="_compute_slot_range_names",
        store=False,
    )
    slot_1_hours = fields.Float(
        string="Rol 1",
        compute="_compute_slot_hours",
        inverse="_inverse_slot_1_hours",
        store=False,
    )
    slot_2_range_name = fields.Char(
        string="Nombre rol 2",
        compute="_compute_slot_range_names",
        store=False,
    )
    slot_2_hours = fields.Float(
        string="Rol 2",
        compute="_compute_slot_hours",
        inverse="_inverse_slot_2_hours",
        store=False,
    )
    slot_3_range_name = fields.Char(
        string="Nombre rol 3",
        compute="_compute_slot_range_names",
        store=False,
    )
    slot_3_hours = fields.Float(
        string="Rol 3",
        compute="_compute_slot_hours",
        inverse="_inverse_slot_3_hours",
        store=False,
    )
    slot_4_range_name = fields.Char(
        string="Nombre rol 4",
        compute="_compute_slot_range_names",
        store=False,
    )
    slot_4_hours = fields.Float(
        string="Rol 4",
        compute="_compute_slot_hours",
        inverse="_inverse_slot_4_hours",
        store=False,
    )

    _sql_constraints = [
        (
            "uniq_product_level",
            "unique(product_tmpl_id, complexity_level_id, branch_id)",
            "Ya existe una configuración para este producto, nivel y rama.",
        )
    ]

    @api.depends("output_line_ids", "output_line_ids.hours")
    def _compute_total_hours(self):
        for rec in self:
            rec.total_hours = sum(rec.output_line_ids.mapped("hours"))

    @api.depends(
        "area_id.hour_matrix_mode",
        "area_id.table_a_layout",
        "matrix_a_ids",
        "matrix_a_ids.hours",
        "matrix_a_ids.area_range_id",
        "matrix_a_ids.area_range_sequence",
    )
    def _compute_compact_hours_a(self):
        for rec in self:
            if rec._is_area_combined_compact_a():
                lines = rec.matrix_a_ids.sorted(
                    key=lambda l: (l.area_range_sequence, l.area_range_id.id, l.id)
                )
                rec.compact_hours_a = lines[0].hours if lines else 0.0
            else:
                rec.compact_hours_a = 0.0

    @api.depends(
        "matrix_b_ids.factor",
        "area_id.hour_matrix_mode",
        "area_id.table_b_kind",
        "area_id.table_a_layout",
        "area_id.table_b_percent_mode",
    )
    def _compute_matrix_b_factor_sum(self):
        for rec in self:
            if rec._matrix_b_percent_split_mode():
                rec.matrix_b_factor_sum = sum(rec.matrix_b_ids.mapped("factor"))
            else:
                rec.matrix_b_factor_sum = 0.0

    def _is_area_combined_compact_a(self):
        self.ensure_one()
        return (
            self.area_id
            and self.area_id.hour_matrix_mode == "combined"
            and self.area_id.table_a_layout in ("compact", "global")
        )

    def _matrix_b_percent_split_mode(self):
        """A unificada + B porcentaje exacto: los % se reparten y deben sumar 100."""
        self.ensure_one()
        return (
            self.area_id
            and self.area_id.hour_matrix_mode == "combined"
            and self.area_id.table_a_layout in ("compact", "global")
            and self.area_id.table_b_kind == "percent"
            and self.area_id.table_b_percent_mode == "exact"
        )

    def _check_matrix_b_percent_split_cap(self):
        """Mientras se editan factores B, la suma no puede superar 100."""
        self.ensure_one()
        if not self._matrix_b_percent_split_mode() or not self.matrix_b_ids:
            return
        s = sum(float(x.factor or 0.0) for x in self.matrix_b_ids)
        if float_compare(s, 100.0, precision_rounding=0.01) > 0:
            raise ValidationError(
                _(
                    "Con tabla A unificada y tipo B porcentaje, la suma de porcentajes "
                    "no puede superar 100 (ahora: %(total).2f)."
                )
                % {"total": s}
            )

    def _validate_matrix_b_percent_split_total_on_save(self):
        """Al guardar la plantilla nivel, la suma de B debe ser exactamente 100."""
        for rec in self:
            if not rec._matrix_b_percent_split_mode() or not rec.matrix_b_ids:
                continue
            s = sum(float(x.factor or 0.0) for x in rec.matrix_b_ids)
            if float_compare(s, 100.0, precision_rounding=0.01) != 0:
                raise ValidationError(
                    _(
                        "Con tabla A unificada y tipo B porcentaje, los porcentajes deben "
                        "sumar 100 al guardar (suma actual: %(total).2f)."
                    )
                    % {"total": s}
                )

    def _apply_table_b_kind_default_factors(
        self, table_b_kind, table_a_layout, table_b_percent_mode="exact"
    ):
        """Valores por defecto de factores B al cambiar el tipo en el área."""
        self.ensure_one()
        ctx = dict(self.env.context, quoter_skip_b_percent_validation=True)
        if table_b_kind == "formula":
            self.with_context(ctx).matrix_b_ids.write({"factor": 0.0})
            return
        if table_b_kind == "multiplier":
            self.with_context(ctx).matrix_b_ids.write({"factor": 1.0})
            return
        n = len(self.matrix_b_ids)
        if n and table_a_layout in ("compact", "global") and table_b_percent_mode == "exact":
            self.with_context(ctx).matrix_b_ids.write({"factor": 100.0 / n})
        else:
            self.with_context(ctx).matrix_b_ids.write({"factor": 100.0})

    def _normalize_matrix_b_for_percent_split_if_needed(self):
        """Reparto uniforme 100%% cuando aplica modo reparto por porcentajes."""
        self.ensure_one()
        if not self._matrix_b_percent_split_mode():
            return
        n = len(self.matrix_b_ids)
        if not n:
            return
        self.with_context(quoter_skip_b_percent_validation=True).matrix_b_ids.write(
            {"factor": 100.0 / n}
        )

    def _inverse_compact_hours_a(self):
        for rec in self:
            if not rec._is_area_combined_compact_a():
                continue
            val = self.env["quoter.hours.policy"].validate_hours_strictly_positive(
                rec.compact_hours_a, _("Horas tabla A")
            )
            rec._sync_matrix_rows()
            rec.matrix_a_ids.write({"hours": val})
            rec.output_line_ids._recompute_combined_hours()

    def _table_b_kind(self):
        self.ensure_one()
        return self.area_id.table_b_kind if self.area_id else "percent"

    def _final_hours_from_a_and_b(self, hours_a, factor_b):
        """Horas finales a partir de A y B según política del área."""
        self.ensure_one()
        a = float(hours_a or 0.0)
        b = float(factor_b or 0.0)
        kind = self._table_b_kind()
        if kind == "percent":
            return a * (b / 100.0) if b else 0.0
        if kind == "multiplier":
            return a * b
        return a

    def _apply_combined_output_hours(self):
        self.output_line_ids._recompute_combined_hours()

    def _apply_combined_final_all(self):
        for rec in self:
            rec._apply_combined_output_hours()

    def _prepare_combined_defaults_from_final_hours(self):
        self.ensure_one()
        self._sync_matrix_rows()
        outs = self.output_line_ids.sorted(
            key=lambda o: (o.area_range_sequence, o.area_range_id.id, o.id)
        )
        if not outs:
            return
        if not any(float(o.matrix_a_id.hours or 0.0) for o in outs if o.matrix_a_id):
            for o in outs:
                if o.matrix_a_id:
                    o.matrix_a_id.hours = float(o.hours or 0.0)
        kind = self._table_b_kind()
        if not any(float(b.factor or 0.0) for b in self.matrix_b_ids):
            ctx = dict(
                self.env.context,
                quoter_skip_b_percent_validation=True,
                quoter_allow_zero_hours=True,
            )
            if kind == "formula":
                self.with_context(ctx).matrix_b_ids.write({"factor": 0.0})
            elif kind == "multiplier":
                self.with_context(ctx).matrix_b_ids.write({"factor": 1.0})
            elif (
                kind == "percent"
                and self.area_id
                and self.area_id.table_a_layout in ("compact", "global")
                and self.area_id.table_b_percent_mode == "exact"
                and self.matrix_b_ids
            ):
                n = len(self.matrix_b_ids)
                self.with_context(ctx).matrix_b_ids.write({"factor": 100.0 / n})
            else:
                default_b = 100.0 if kind == "percent" else 1.0
                self.with_context(ctx).matrix_b_ids.write({"factor": default_b})
        self._apply_combined_output_hours()

    def _unify_hours_a_compact_from_first_row(self):
        self.ensure_one()
        lines = self.matrix_a_ids.sorted(
            key=lambda l: (l.area_range_sequence, l.area_range_id.id, l.id)
        )
        if not lines:
            return
        v = float(lines[0].hours or 0.0)
        lines.write({"hours": v})
        self.output_line_ids._recompute_combined_hours()

    def action_open_hour_matrices(self):
        self.ensure_one()
        view = self.env.ref("quoter.view_quoter_product_level_range_form_matrices")
        return {
            "type": "ir.actions.act_window",
            "name": _("Tablas A, B y horas finales"),
            "res_model": "quoter.product.level.range",
            "view_mode": "form",
            "res_id": self.id,
            "view_id": view.id,
            "target": "new",
        }

    def _area_ranges_slot(self, index):
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
        "output_line_ids",
        "output_line_ids.hours",
        "output_line_ids.area_range_id",
    )
    def _compute_slot_hours(self):
        for rec in self:
            for i in range(4):
                ar = rec._area_ranges_slot(i)
                if not ar:
                    rec["slot_%d_hours" % (i + 1)] = 0.0
                    continue
                row = rec.output_line_ids.filtered(
                    lambda h, a=ar: h.area_range_id == a
                )[:1]
                rec["slot_%d_hours" % (i + 1)] = row.hours if row else 0.0

    def _write_slot_hours(self, slot_index, value):
        for rec in self:
            if rec.area_id and rec.area_id.hour_matrix_mode == "combined":
                continue
            rec._sync_matrix_rows()
            ar = rec._area_ranges_slot(slot_index)
            if not ar:
                continue
            row = rec.output_line_ids.filtered(
                lambda h, a=ar: h.area_range_id == a
            )[:1]
            if row:
                hours = self.env["quoter.hours.policy"].validate_hours_strictly_positive(
                    value, _("Horas finales")
                )
                row.with_context(quoter_skip_output_hours_guard=True).write(
                    {
                        "hours": hours,
                        "matrix_a_id": False,
                    }
                )

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

    @api.constrains("complexity_level_id", "area_id", "branch_id")
    def _check_level_in_area(self):
        for rec in self:
            if rec.area_id and rec.complexity_level_id and rec.complexity_level_id not in rec.area_id.complexity_level_ids:
                raise ValidationError(
                    _("El nivel debe pertenecer a los niveles configurados en el área «%s».")
                    % rec.area_id.display_name
                )
            if rec.area_id and rec.branch_id and rec.branch_id not in rec.area_id._effective_branch_ids():
                raise ValidationError(
                    _("La rama debe pertenecer a las ramas configuradas en el área «%s».")
                    % rec.area_id.display_name
                )

    @api.model
    def _default_branch_for_vals(self, vals):
        branch = False
        area = False
        branch_id = vals.get("branch_id")
        if branch_id:
            branch = self.env["quoter.area.branch"].browse(branch_id)
        product_tmpl_id = vals.get("product_tmpl_id")
        if product_tmpl_id:
            tmpl = self.env["product.template"].browse(product_tmpl_id)
            area = tmpl.quoter_area_id
        if area:
            if branch and branch in area._effective_branch_ids():
                return branch.id
            return area._resolve_matrix_branch().id
        if branch:
            return branch.id
        default_branch = self.env.ref("quoter.quoter_area_branch_unique", raise_if_not_found=False)
        return default_branch.id if default_branch else False

    def _sync_matrix_rows(self):
        """Por rol del área (máx. 4): modo regular solo salida; modo combinado B y A por rol + salida."""
        B = self.env["quoter.product.level.range.matrix.b"]
        A = self.env["quoter.product.level.range.matrix.a"]
        O = self.env["quoter.product.level.range.output"]
        for rec in self:
            area = rec.area_id
            if not area:
                rec.matrix_b_ids.unlink()
                rec.matrix_a_ids.unlink()
                rec.output_line_ids.unlink()
                continue
            ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:4]
            keep_ids = set(ranges.ids)
            rec.output_line_ids.filtered(lambda o: o.area_range_id.id not in keep_ids).unlink()
            rec.matrix_a_ids.filtered(lambda a: a.area_range_id.id not in keep_ids).unlink()
            rec.matrix_b_ids.filtered(lambda b: b.area_range_id.id not in keep_ids).unlink()
            combined = area.hour_matrix_mode == "combined"
            for ar in ranges:
                if combined:
                    brow = rec.matrix_b_ids.filtered(lambda b: b.area_range_id == ar)[:1]
                    zero_ctx = dict(self.env.context, quoter_allow_zero_hours=True)
                    if not brow:
                        brow = B.with_context(zero_ctx).create(
                            {
                                "level_range_id": rec.id,
                                "area_range_id": ar.id,
                                "factor": 0.0,
                            }
                        )
                    arow = rec.matrix_a_ids.filtered(lambda a: a.area_range_id == ar)[:1]
                    if not arow:
                        arow = A.with_context(zero_ctx).create(
                            {
                                "level_range_id": rec.id,
                                "area_range_id": ar.id,
                                "hours": 0.0,
                            }
                        )
                    orow = rec.output_line_ids.filtered(lambda o: o.area_range_id == ar)[:1]
                    if not orow:
                        O.with_context(zero_ctx).create(
                            {
                                "level_range_id": rec.id,
                                "area_range_id": ar.id,
                                "matrix_a_id": arow.id,
                                "hours": 0.0,
                            }
                        )
                    else:
                        vals = {}
                        if not orow.matrix_a_id:
                            vals["matrix_a_id"] = arow.id
                        if vals:
                            orow.write(vals)
                else:
                    rec.matrix_a_ids.filtered(lambda a: a.area_range_id == ar).unlink()
                    rec.matrix_b_ids.filtered(lambda b: b.area_range_id == ar).unlink()
                    orow = rec.output_line_ids.filtered(lambda o: o.area_range_id == ar)[:1]
                    if not orow:
                        O.with_context(
                            quoter_allow_zero_hours=True
                        ).create(
                            {
                                "level_range_id": rec.id,
                                "area_range_id": ar.id,
                                "matrix_a_id": False,
                                "hours": 0.0,
                            }
                        )
                    elif orow.matrix_a_id:
                        orow.write({"matrix_a_id": False})
            if combined:
                rec._apply_combined_output_hours()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("branch_id"):
                vals["branch_id"] = self._default_branch_for_vals(vals)
        recs = super().create(vals_list)
        recs._sync_matrix_rows()
        combined = recs.filtered(
            lambda r: r.area_id and r.area_id.hour_matrix_mode == "combined"
        )
        for lr in combined:
            lr._prepare_combined_defaults_from_final_hours()
        recs.mapped("area_id")._apply_matrix_b_advanced_rules_to_level_ranges(recs)
        return recs

    def write(self, vals):
        if "branch_id" not in vals:
            for rec in self.filtered(lambda r: not r.branch_id):
                rec.branch_id = rec._default_branch_for_vals(
                    {"product_tmpl_id": rec.product_tmpl_id.id}
                )
        res = super().write(vals)
        if "product_tmpl_id" in vals:
            self._sync_matrix_rows()
        self.filtered(
            lambda r: r.area_id and r.area_id.hour_matrix_mode == "combined"
        )._apply_combined_output_hours()
        self.mapped("area_id")._apply_matrix_b_advanced_rules_to_level_ranges(self)
        if (
            not self.env.context.get("quoter_skip_b_percent_validation")
            and "product_tmpl_id" not in vals
        ):
            to_validate = self.filtered(
                lambda r: r._matrix_b_percent_split_mode()
                and r.area_id
                and not r.area_id.quoter_config_edit_mode
            )
            if to_validate:
                to_validate._validate_matrix_b_percent_split_total_on_save()
        return res

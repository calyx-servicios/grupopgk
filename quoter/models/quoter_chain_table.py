# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .quoter_chain_table_line_param import (
    CHAIN_LABEL_EMPLOYEES,
    CHAIN_LABEL_PARENT,
    CHAIN_PARAM_N,
    CHAIN_PARAM_SYMBOL,
    CHAIN_PARAM_VALOR,
)


class QuoterChainTable(models.Model):
    _name = "quoter.chain.table"
    _description = "Tabla de cadena (cantidad de empleados)"
    _order = "people_min, sequence, id"

    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    people_min = fields.Integer(
        string="Cantidad mínima de empleados",
        required=True,
        default=1,
        help="Se calcula automáticamente (1 en la primera tabla; anterior máx. + 1).",
    )
    people_max = fields.Integer(
        string="Cantidad máxima de empleados",
        default=0,
        help="Tope del tramo. 0 = sin tope (solo última tabla).",
    )
    delta = fields.Integer(
        string="Delta",
        default=1,
        required=True,
        help="Divisor de la fórmula: nº/delta×(empleados−valor).",
    )
    line_ids = fields.One2many(
        comodel_name="quoter.chain.table.line",
        inverse_name="table_id",
        string="Celdas producto × rol",
    )
    display_label = fields.Char(
        string="Etiqueta",
        compute="_compute_display_label",
    )
    tab_label = fields.Char(
        string="Pestaña",
        compute="_compute_display_label",
    )

    _sql_constraints = [
        (
            "uniq_chain_table_area_min",
            "UNIQUE(area_id, people_min)",
            "Ya existe un tramo con ese mínimo en el área.",
        ),
    ]

    @api.depends("people_min", "people_max")
    def _compute_display_label(self):
        for rec in self:
            if rec.people_max and rec.people_max >= rec.people_min:
                rec.display_label = _("%(min)s – %(max)s") % {
                    "min": rec.people_min,
                    "max": rec.people_max,
                }
                rec.tab_label = _("%(min)s a %(max)s") % {
                    "min": rec.people_min,
                    "max": rec.people_max,
                }
            else:
                rec.display_label = _("Desde %(min)s") % {"min": rec.people_min}
                rec.tab_label = _("Desde %(min)s") % {"min": rec.people_min}

    @api.constrains("people_min", "people_max", "delta")
    def _check_bounds(self):
        for rec in self:
            if rec.people_min < 1:
                raise ValidationError(_("El mínimo calculado debe ser al menos 1."))
            if rec.people_max and rec.people_max < rec.people_min:
                raise ValidationError(
                    _("La cantidad máxima no puede ser menor que la mínima del tramo.")
                )
            if int(rec.delta or 0) < 1:
                raise ValidationError(_("Delta debe ser al menos 1."))

    def _parent_table(self):
        self.ensure_one()
        tables = self.area_id._chain_tables_ordered()
        idx = list(tables.ids).index(self.id)
        if idx <= 0:
            return self.browse()
        return tables[idx - 1]

    def _is_first_table(self):
        self.ensure_one()
        tables = self.area_id._chain_tables_ordered()
        return bool(tables and tables[0].id == self.id)

    def _product_templates_for_sync(self):
        self.ensure_one()
        area = self.area_id
        if not area:
            return self.env["product.template"]
        return area.line_ids.filtered("product_tmpl_id").mapped("product_tmpl_id")

    @api.model
    def _drop_legacy_chain_line_sql_constraints(self):
        """Elimina UNIQUE(tabla, rol) previo al modelo producto×rol."""
        self.env.cr.execute(
            """
            ALTER TABLE quoter_chain_table_line
            DROP CONSTRAINT IF EXISTS
            quoter_chain_table_line_uniq_chain_line_table_range
            """
        )

    def _sync_lines_for_products(self):
        self._drop_legacy_chain_line_sql_constraints()
        Line = self.env["quoter.chain.table.line"]
        for table in self:
            area = table.area_id
            if not area:
                continue
            is_first = table._is_first_table()
            ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))
            products = table._product_templates_for_sync()
            keep_keys = {(p.id, r.id) for p in products for r in ranges}
            table.line_ids.filtered(
                lambda ln, k=keep_keys: (ln.product_tmpl_id.id, ln.area_range_id.id)
                not in k
            ).unlink()
            existing = {
                (ln.product_tmpl_id.id, ln.area_range_id.id): ln
                for ln in table.line_ids
                if ln.product_tmpl_id and ln.area_range_id
            }
            for product in products:
                for ar in ranges:
                    if (product.id, ar.id) in existing:
                        line = existing[(product.id, ar.id)]
                        if is_first and line.value_kind != "fixed":
                            line.write({"value_kind": "fixed"})
                        continue
                    Line.create(
                        {
                            "table_id": table.id,
                            "product_tmpl_id": product.id,
                            "area_range_id": ar.id,
                            "value_kind": "fixed",
                            "fixed_value": 0.0,
                        }
                    )

    def _inherit_lines_from_parent(self):
        """Copia tipo, valor fijo y parámetros de fórmula desde la tabla anterior."""
        for table in self:
            parent = table._parent_table()
            if not parent:
                continue
            parent_by_key = {
                (ln.product_tmpl_id.id, ln.area_range_id.id): ln
                for ln in parent.line_ids
                if ln.product_tmpl_id and ln.area_range_id
            }
            for line in table.line_ids:
                key = (line.product_tmpl_id.id, line.area_range_id.id)
                parent_line = parent_by_key.get(key)
                if parent_line:
                    line._copy_config_from_line(parent_line)

    @api.model_create_multi
    def create(self, vals_list):
        tables = super().create(vals_list)
        tables.mapped("area_id")._chain_recompute_table_bounds()
        tables._sync_lines_for_products()
        tables._inherit_lines_from_parent()
        return tables

    def write(self, vals):
        res = super().write(vals)
        if "people_max" in vals or "delta" in vals:
            self.mapped("area_id")._chain_recompute_table_bounds()
        return res

    def unlink(self):
        areas = self.mapped("area_id")
        res = super().unlink()
        areas._chain_recompute_table_bounds()
        return res


class QuoterChainTableLine(models.Model):
    _name = "quoter.chain.table.line"
    _description = "Celda producto × rol en tabla de cadena"
    _order = "product_tmpl_id, area_range_sequence, id"

    table_id = fields.Many2one(
        comodel_name="quoter.chain.table",
        string="Tabla",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_id = fields.Many2one(
        related="table_id.area_id",
        store=True,
        readonly=True,
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Producto",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rol",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )
    value_kind = fields.Selection(
        selection=[
            ("fixed", "Fijo"),
            ("formula", "Fórmula"),
        ],
        string="Tipo",
        default="fixed",
        required=True,
    )
    fixed_value = fields.Float(
        string="Valor fijo",
        default=0.0,
    )
    param_ids = fields.One2many(
        comodel_name="quoter.chain.table.line.param",
        inverse_name="chain_line_id",
        string="Parámetros fórmula",
    )
    formula_expression = fields.Char(
        string="Fórmula",
        compute="_compute_formula_expression",
    )
    multiplier = fields.Float(
        string="Factor (obsoleto)",
        default=1.0,
        help="Obsoleto; use parámetros de fórmula.",
    )

    _sql_constraints = [
        (
            "uniq_chain_line_table_product_range",
            "UNIQUE(table_id, product_tmpl_id, area_range_id)",
            "Solo una celda por producto y rol en cada tabla.",
        ),
    ]

    @api.depends("value_kind", "fixed_value", "param_ids", "param_ids.value")
    def _compute_formula_expression(self):
        for rec in self:
            rec.formula_expression = rec.get_formula_expression_ui().get("composed") or ""

    @api.constrains("fixed_value")
    def _check_fixed_non_negative(self):
        for rec in self:
            if (rec.fixed_value or 0.0) < 0.0:
                raise ValidationError(_("El valor fijo no puede ser negativo."))

    @api.constrains("value_kind", "table_id")
    def _check_formula_requires_parent(self):
        for rec in self:
            if rec.value_kind != "formula":
                continue
            if not rec.table_id._parent_table():
                raise ValidationError(
                    _("La primera tabla solo admite valores fijos.")
                )

    @api.constrains("product_tmpl_id", "area_range_id", "table_id")
    def _check_product_and_range_in_area(self):
        for rec in self:
            area = rec.table_id.area_id
            if not area:
                continue
            if rec.area_range_id not in area.area_range_ids:
                raise ValidationError(_("El rol no pertenece al área."))
            if rec.product_tmpl_id not in area.line_ids.mapped("product_tmpl_id"):
                raise ValidationError(
                    _("El producto debe estar en la pestaña Productos del área.")
                )

    def _get_param_record(self, code):
        self.ensure_one()
        return self.param_ids.filtered(lambda p, c=code: p.code == c)[:1]

    def _get_param_value(self, code, default=0.0):
        self.ensure_one()
        param = self._get_param_record(code)
        return float(param.value or 0.0) if param else float(default)

    def _set_param_value(self, code, value):
        self.ensure_one()
        val = float(value or 0.0)
        param = self._get_param_record(code)
        if param:
            param.write({"value": val})
        else:
            self.env["quoter.chain.table.line.param"].create(
                {
                    "chain_line_id": self.id,
                    "code": code,
                    "value": val,
                    "sequence": 10 if code == CHAIN_PARAM_N else 20,
                }
            )

    def _ensure_formula_params(self):
        for line in self:
            if line.value_kind != "formula":
                continue
            for code, seq in ((CHAIN_PARAM_N, 10), (CHAIN_PARAM_VALOR, 20)):
                if not line._get_param_record(code):
                    line._set_param_value(code, 1.0 if code == CHAIN_PARAM_N else 0.0)

    def _copy_config_from_line(self, source_line):
        """Replica fijo o fórmula (con parámetros) desde otra celda equivalente."""
        self.ensure_one()
        source = source_line.exists()
        if not source:
            return
        self.write(
            {
                "value_kind": source.value_kind,
                "fixed_value": source.fixed_value,
            }
        )
        if source.value_kind == "formula":
            self._ensure_formula_params()
            for param in source.param_ids:
                self._set_param_value(param.code, param.value)
        else:
            self.param_ids.unlink()

    def _format_num(self, n):
        x = float(n or 0.0)
        if x == int(x):
            return str(int(x))
        return ("%.4f" % x).rstrip("0").rstrip(".")

    def _chain_formula_param_values(self, for_edit=False):
        """Valores nº y umbral para la plantilla de fórmula cadena."""
        self.ensure_one()
        if self.value_kind == "formula":
            self._ensure_formula_params()
            return (
                self._get_param_value(CHAIN_PARAM_N, 1.0),
                self._get_param_value(CHAIN_PARAM_VALOR, 0.0),
            )
        if for_edit:
            return (1.0, 0.0)
        return (0.0, 0.0)

    def _build_chain_formula_expression_ui(self, employee_count=None, for_edit=False):
        self.ensure_one()
        table = self.table_id
        delta = max(1, int(table.delta or 1))
        emp = int(employee_count if employee_count is not None else 1)
        n_val, v_val = self._chain_formula_param_values(for_edit=for_edit)
        parent_lbl = CHAIN_LABEL_PARENT
        emp_lbl = CHAIN_LABEL_EMPLOYEES
        parts = [
            {"type": "text", "content": "="},
            {"type": "text", "content": parent_lbl},
            {"type": "text", "content": "+"},
            {"type": "param", "code": CHAIN_PARAM_N, "value": n_val, "label": CHAIN_PARAM_SYMBOL},
            {"type": "text", "content": "/%s×(" % self._format_num(delta)},
            {"type": "text", "content": emp_lbl},
            {"type": "text", "content": "-"},
            {
                "type": "param",
                "code": CHAIN_PARAM_VALOR,
                "value": v_val,
                "label": CHAIN_PARAM_SYMBOL,
            },
            {"type": "text", "content": ")"},
        ]
        composed = "=%s+%s/%s×(%s-%s)" % (
            parent_lbl,
            self._format_num(n_val),
            self._format_num(delta),
            emp_lbl,
            self._format_num(v_val),
        )
        preview = self.get_computed_value(employee_count=emp)
        return {
            "template": "chain_formula",
            "employee_count": emp,
            "delta": delta,
            "result_value": preview,
            "parts": parts,
            "composed": composed,
        }

    def get_formula_expression_ui(self, employee_count=None):
        self.ensure_one()
        emp = int(employee_count if employee_count is not None else 1)
        if self.value_kind == "fixed":
            return {
                "template": "fixed",
                "employee_count": emp,
                "result_value": float(self.fixed_value or 0.0),
                "parts": [],
                "composed": _("Fijo: %s") % self._format_num(self.fixed_value),
            }
        return self._build_chain_formula_expression_ui(employee_count=emp)

    def _cache_key(self):
        self.ensure_one()
        return (self.table_id.id, self.product_tmpl_id.id, self.area_range_id.id)

    def _get_formula_fixed_base_value(self, cache=None):
        """Recorre tablas padre hasta la celda fija equivalente (producto × rol)."""
        self.ensure_one()
        cache = cache if cache is not None else {}
        fk = ("_fixed_base",) + self._cache_key()
        if fk in cache:
            return cache[fk]
        base = 0.0
        table = self.table_id._parent_table()
        while table:
            pline = table.line_ids.filtered(
                lambda ln, self=self: ln.product_tmpl_id == self.product_tmpl_id
                and ln.area_range_id == self.area_range_id
            )[:1]
            if pline and pline.value_kind == "fixed":
                base = float(pline.fixed_value or 0.0)
                break
            table = table._parent_table()
        cache[fk] = base
        return base

    def get_computed_value(self, cache=None, employee_count=None):
        self.ensure_one()
        cache = cache if cache is not None else {}
        if employee_count is not None:
            cache["_employee_count"] = int(employee_count or 0)
        emp = int(cache.get("_employee_count", 0) or 0)
        key = self._cache_key()
        if key in cache:
            return cache[key]
        if self.table_id._is_first_table():
            val = float(self.fixed_value or 0.0)
        elif self.value_kind == "fixed":
            val = float(self.fixed_value or 0.0)
        else:
            base_val = self._get_formula_fixed_base_value(cache=cache)
            self._ensure_formula_params()
            n_val = self._get_param_value(CHAIN_PARAM_N, 0.0)
            v_val = self._get_param_value(CHAIN_PARAM_VALOR, 0.0)
            delta = max(1, int(self.table_id.delta or 1))
            val = base_val + (n_val / float(delta)) * (emp - v_val)
        cache[key] = val
        return val

    def get_edit_popup_data(self, employee_count=None, complexity_level=None):
        self.ensure_one()
        area = self.area_id
        emp = int(
            employee_count
            if employee_count is not None
            else (area.chain_test_employee_count or 1)
        )
        level = area._chain_resolve_complexity_level(complexity_level)
        parent_preview = 0.0
        parent_table = self.table_id._parent_table()
        is_first = self.table_id._is_first_table()
        if parent_table and self.value_kind == "formula":
            parent_preview = self._get_formula_fixed_base_value()
        if is_first:
            expr = self.get_formula_expression_ui(employee_count=emp)
        else:
            expr = self._build_chain_formula_expression_ui(
                employee_count=emp, for_edit=True
            )
        computed_preview = self.get_computed_value(employee_count=emp)
        computed_preview = area._chain_hours_with_complexity_increase(
            computed_preview, complexity_level=level
        )
        computed_preview = area._apply_output_hours_minimum(computed_preview)
        return {
            "line_id": self.id,
            "product_name": self.product_tmpl_id.display_name or "",
            "role_name": self.area_range_id.name or "",
            "value_kind": "fixed" if is_first else self.value_kind,
            "fixed_value": self.fixed_value,
            "expression": expr,
            "parent_value": parent_preview,
            "computed_preview": computed_preview,
            "complexity_increase_percent": area._chain_complexity_increase_percent(
                level
            ),
            "has_parent_table": bool(parent_table) and not is_first,
            "is_first_table": is_first,
            "delta": int(self.table_id.delta or 1),
            "employee_count": emp,
        }

    def apply_popup_values(self, value_kind, fixed_value=None, param_values=None):
        self.ensure_one()
        if self.table_id._is_first_table():
            value_kind = "fixed"
        if value_kind not in ("fixed", "formula"):
            raise UserError(_("Tipo de valor no válido."))
        vals = {"value_kind": value_kind}
        if value_kind == "fixed":
            vals["fixed_value"] = float(fixed_value or 0.0)
            self.write(vals)
            return
        if not self.table_id._parent_table():
            raise UserError(_("La primera tabla solo admite valores fijos."))
        self.write(vals)
        self._ensure_formula_params()
        items = param_values or []
        if isinstance(items, dict):
            items = [{"code": k, "value": v} for k, v in items.items()]
        for item in items:
            code = (item.get("code") or "").strip()
            if code not in (CHAIN_PARAM_N, CHAIN_PARAM_VALOR):
                continue
            try:
                val = float(item.get("value") or 0.0)
            except (TypeError, ValueError):
                raise ValidationError(_("Valor numérico no válido.")) from None
            if val < 0.0:
                raise ValidationError(_("Los parámetros no pueden ser negativos."))
            self._set_param_value(code, val)

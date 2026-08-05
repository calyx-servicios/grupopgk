# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class QuoterProfessionalAreaChain(models.Model):
    _inherit = "quoter.professional.area"

    chain_table_ids = fields.One2many(
        comodel_name="quoter.chain.table",
        inverse_name="area_id",
        string="Tablas cadena (empleados)",
    )
    chain_test_employee_count = fields.Integer(
        string="Empleados de prueba (config)",
        default=1,
        help="Solo vista previa en configuración del área.",
    )
    chain_test_complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel de complejidad (prueba)",
        domain="[('id', 'in', chain_complexity_level_ids)]",
        help="Solo vista previa en la matriz del área; no afecta cotizaciones.",
    )
    chain_complexity_increase_ids = fields.One2many(
        comodel_name="quoter.area.chain.complexity.increase",
        inverse_name="area_id",
        string="Aumento % por nivel (cadena)",
    )
    chain_complexity_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        string="Niveles con aumento (cadena)",
        compute="_compute_chain_complexity_level_ids",
        help="Niveles definidos manualmente en la tabla de aumento % (cadena).",
    )

    @api.depends("chain_complexity_increase_ids.complexity_level_id")
    def _compute_chain_complexity_level_ids(self):
        for area in self:
            area.chain_complexity_level_ids = (
                area.chain_complexity_increase_ids.mapped("complexity_level_id")
            )

    @api.model
    def _chain_tables_ordered(self):
        self.ensure_one()
        return self.chain_table_ids.sorted(
            key=lambda t: (t.people_min, t.sequence, t.id)
        )

    def _chain_recompute_table_bounds(self):
        """Recalcula people_min: 1 en la primera; anterior máx. + 1 en las demás."""
        for area in self:
            tables = area._chain_tables_ordered()
            for idx, table in enumerate(tables):
                if idx == 0:
                    new_min = 1
                else:
                    prev = tables[idx - 1]
                    if prev.people_max and prev.people_max >= prev.people_min:
                        new_min = prev.people_max + 1
                    else:
                        new_min = max(prev.people_min + 1, 1)
                if table.people_min != new_min:
                    table.sudo().write({"people_min": new_min})

    def _chain_sync_all_table_lines(self):
        for area in self:
            for table in area._chain_tables_ordered():
                table._sync_lines_for_products()

    def _chain_resolve_table_for_employees(self, employee_count):
        self.ensure_one()
        count = int(employee_count or 0)
        if count < 1:
            return self.env["quoter.chain.table"]
        tables = self._chain_tables_ordered()
        if not tables:
            return self.env["quoter.chain.table"]
        chosen = tables[0]
        for table in tables:
            if count < table.people_min:
                break
            chosen = table
            if table.people_max and table.people_max > 0 and count > table.people_max:
                continue
            if not table.people_max or table.people_max <= 0:
                return table
            if count <= table.people_max:
                return table
        return chosen

    def _chain_resolve_table_for_people(self, people_count):
        return self._chain_resolve_table_for_employees(people_count)

    def _chain_resolve_complexity_level(self, complexity_level=None):
        self.ensure_one()
        if complexity_level:
            if isinstance(complexity_level, int):
                return self.env["quoter.complexity.level"].browse(complexity_level)
            return complexity_level
        return self.chain_test_complexity_level_id or self.env["quoter.complexity.level"]

    def _chain_default_complexity_level(self):
        """Primer nivel definido manualmente en la tabla de aumento % (cadena)."""
        self.ensure_one()
        rows = self.chain_complexity_increase_ids.sorted(
            key=lambda r: (r.complexity_level_sequence, r.complexity_level_id.id)
        )
        return rows[:1].complexity_level_id if rows else self.env["quoter.complexity.level"]

    def _chain_clear_stale_test_complexity_level(self):
        for area in self:
            if (
                area.chain_test_complexity_level_id
                and area.chain_test_complexity_level_id
                not in area.chain_complexity_level_ids
            ):
                area.chain_test_complexity_level_id = False

    def _chain_complexity_increase_percent(self, complexity_level=None):
        self.ensure_one()
        level = self._chain_resolve_complexity_level(complexity_level)
        if not level:
            return 0.0
        rule = self.chain_complexity_increase_ids.filtered(
            lambda r, lev=level: r.complexity_level_id == lev
        )[:1]
        return float(rule.increase_percent or 0.0) if rule else 0.0

    def _chain_hours_with_complexity_increase(self, base_hours, complexity_level=None):
        self.ensure_one()
        pct = self._chain_complexity_increase_percent(complexity_level)
        hours = float(base_hours or 0.0)
        if not pct:
            return hours
        return hours * (1.0 + pct / 100.0)

    def _chain_create_table_state(self):
        """Indica si se puede crear otra tabla y mensaje de ayuda si no."""
        self.ensure_one()
        if self._chain_matrix_read_only():
            return False, False
        tables = self._chain_tables_ordered()
        if not tables:
            return True, False
        last = tables[-1]
        if last.people_max and last.people_max >= last.people_min:
            return True, False
        return False, _(
            "Defina la cantidad máxima de empleados en el último tramo "
            "para añadir otra tabla."
        )

    def _chain_compute_hours_map_for_product(
        self,
        employee_count,
        product_tmpl,
        apply_minimum=True,
        complexity_level=None,
    ):
        self.ensure_one()
        product_tmpl = product_tmpl.exists() if product_tmpl else product_tmpl
        if not product_tmpl:
            return {}
        table = self._chain_resolve_table_for_employees(employee_count)
        if not table:
            return {}
        cache = {"_employee_count": int(employee_count or 1)}
        result = {}
        lines = table.line_ids.filtered(
            lambda ln, p=product_tmpl: ln.product_tmpl_id == p
        ).sorted(key=lambda ln: (ln.area_range_sequence, ln.id))
        for line in lines:
            raw = line.get_computed_value(cache=cache)
            if apply_minimum:
                raw = self._apply_output_hours_minimum(raw)
            raw = self._chain_hours_with_complexity_increase(
                raw, complexity_level=complexity_level
            )
            if apply_minimum:
                raw = self._apply_output_hours_minimum(raw)
            result[line.area_range_id.id] = raw
        return result

    def action_chain_create_table(self):
        self.ensure_one()
        if self.hour_matrix_mode != "formula_chain":
            raise UserError(_("El área no usa modo fórmula en cadena."))
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(_("Solo Quoter - Gerente puede editar tablas."))
        if not self.quoter_config_edit_mode:
            raise UserError(_("Abra el editor de tabla para crear tablas."))
        can_create, hint = self._chain_create_table_state()
        if not can_create:
            raise UserError(
                hint
                or _(
                    "Defina la cantidad máxima de empleados en la tabla "
                    "anterior antes de crear una nueva."
                )
            )
        tables = self._chain_tables_ordered()
        seq = (tables[-1].sequence + 10) if tables else 10
        if not tables:
            people_min = 1
            default_max = 10
        else:
            last = tables[-1]
            people_min = last.people_max + 1
            default_max = max(people_min + 9, last.people_max + 10)
            default_delta = last.delta or 1
        new_table = self.env["quoter.chain.table"].create(
            {
                "area_id": self.id,
                "sequence": seq,
                "people_min": people_min,
                "people_max": default_max,
                "delta": default_delta if tables else 1,
            }
        )
        return self.get_chain_matrix_preview_data(active_table_id=new_table.id)

    def action_chain_delete_table(self, table_id):
        self.ensure_one()
        table = self.env["quoter.chain.table"].browse(int(table_id or 0)).exists()
        if not table or table.area_id != self:
            raise UserError(_("Tabla no encontrada."))
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(_("Solo Quoter - Gerente puede eliminar tablas."))
        if not self.quoter_config_edit_mode:
            raise UserError(_("Abra el editor de tabla para eliminar."))
        table.unlink()
        return self.get_chain_matrix_preview_data()

    def get_chain_matrix_preview_data(
        self,
        active_table_id=None,
        test_employee_count=None,
        test_complexity_level_id=None,
    ):
        self.ensure_one()
        if self.hour_matrix_mode != "formula_chain":
            return {}
        emp_count = int(
            test_employee_count
            if test_employee_count is not None
            else (self.chain_test_employee_count or 1)
        )
        if test_complexity_level_id is not None:
            test_level = self.env["quoter.complexity.level"].browse(
                int(test_complexity_level_id or 0)
            )
        else:
            test_level = self.chain_test_complexity_level_id
        increase_pct = self._chain_complexity_increase_percent(test_level)
        tables = self._chain_tables_ordered()
        can_create, create_hint = self._chain_create_table_state()
        if not tables:
            return {
                "area_id": self.id,
                "matrix_read_only": self._chain_matrix_read_only(),
                "matrix_editor_open": bool(self.quoter_config_edit_mode),
                "can_create_table": can_create,
                "chain_create_table_hint": create_hint or False,
                "tables": [],
                "active_table_id": False,
                "ranges": [],
                "rows": [],
                "test_employee_count": emp_count,
                "test_people_count": emp_count,
                "test_complexity_level_id": test_level.id if test_level else False,
                "complexity_increase_percent": increase_pct,
                "complexity_levels": self._chain_complexity_levels_payload(),
                "empty_message": _("Use «Nueva tabla» para crear el primer tramo."),
            }
        if active_table_id:
            active = tables.filtered(lambda t, aid=active_table_id: t.id == aid)[:1]
        else:
            active = self._chain_resolve_table_for_employees(emp_count)
        if not active:
            active = tables[0]
        active._sync_lines_for_products()
        ranges = self.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))
        range_cols = [{"id": r.id, "name": r.name} for r in ranges]
        parent_table = active._parent_table()
        has_parent = bool(parent_table)
        is_first = active._is_first_table()
        rows = []
        cache = {"_employee_count": emp_count}
        for sline in self.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            if not sline.product_tmpl_id:
                continue
            tmpl = sline.product_tmpl_id
            role_cells = []
            for ar in ranges:
                cline = active.line_ids.filtered(
                    lambda ln, t=tmpl, rid=ar.id: ln.product_tmpl_id == t
                    and ln.area_range_id.id == rid
                )[:1]
                if not cline:
                    continue
                parent_computed = 0.0
                if cline.value_kind == "formula":
                    parent_computed = cline._get_formula_fixed_base_value(
                        cache=cache
                    )
                computed = cline.get_computed_value(cache=cache)
                computed = self._chain_hours_with_complexity_increase(
                    computed, complexity_level=test_level
                )
                computed = self._apply_output_hours_minimum(computed)
                expr = cline.get_formula_expression_ui(employee_count=emp_count)
                role_cells.append(
                    {
                        "chain_line_id": cline.id,
                        "range_id": ar.id,
                        "value_kind": cline.value_kind,
                        "fixed_value": cline.fixed_value,
                        "parent_computed": parent_computed,
                        "computed": computed,
                        "formula_composed": expr.get("composed") or "",
                        "formula_expression": expr,
                        "hide_in_quote": bool(
                            cline.value_kind == "fixed"
                            and float(cline.fixed_value or 0.0) == 0.0
                        ),
                    }
                )
            rows.append(
                {
                    "service_line_id": sline.id,
                    "product_name": sline.name or tmpl.display_name or "",
                    "role_cells": role_cells,
                }
            )
        return {
            "area_id": self.id,
            "area_name": self.name,
            "matrix_read_only": self._chain_matrix_read_only(),
            "matrix_editor_open": bool(self.quoter_config_edit_mode),
            "can_create_table": can_create,
            "chain_create_table_hint": create_hint or False,
            "section_title": _("Tablas por cantidad de empleados — %(area)s")
            % {"area": self.name or ""},
            "tables": [
                {
                    "id": t.id,
                    "people_min": t.people_min,
                    "people_max": t.people_max,
                    "delta": t.delta,
                    "label": t.display_label,
                    "tab_label": t.tab_label,
                }
                for t in tables
            ],
            "active_table_id": active.id,
            "active_people_min": active.people_min,
            "active_people_max": active.people_max,
            "active_delta": active.delta,
            "is_first_table": is_first,
            "ranges": range_cols,
            "rows": rows,
            "test_employee_count": emp_count,
            "test_complexity_level_id": test_level.id if test_level else False,
            "complexity_increase_percent": increase_pct,
            "complexity_levels": self._chain_complexity_levels_payload(),
            "resolved_table_id": self._chain_resolve_table_for_employees(emp_count).id,
            "has_parent_table": has_parent,
            "empty_message": _(
                "Agregue productos en la pestaña Productos (con el editor de tabla abierto)."
            ),
        }

    def _chain_complexity_levels_payload(self):
        self.ensure_one()
        return [
            {
                "id": row.complexity_level_id.id,
                "name": row.complexity_level_id.name or "",
                "increase_percent": float(row.increase_percent or 0.0),
            }
            for row in self.chain_complexity_increase_ids.sorted(
                key=lambda r: (r.complexity_level_sequence, r.complexity_level_id.id)
            )
            if row.complexity_level_id
        ]

    def _chain_matrix_read_only(self):
        self.ensure_one()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            return True
        return not self.quoter_config_edit_mode

    def chain_matrix_write_cell(
        self, line_id, write_kind, value, active_table_id=None, table_id=False
    ):
        self.ensure_one()
        if self.hour_matrix_mode != "formula_chain":
            return self.get_chain_matrix_preview_data(active_table_id=active_table_id)
        if self._chain_matrix_read_only():
            raise UserError(_("Abra el editor de tabla para editar."))
        write_kind = (write_kind or "").strip()
        table = self.env["quoter.chain.table"].browse(
            int(active_table_id or table_id or 0)
        )
        if write_kind in ("people_max", "delta"):
            if not table.exists() or table.area_id != self:
                raise UserError(_("Tabla no encontrada."))
            if write_kind == "people_max":
                try:
                    val = int(float(value or 0))
                except (TypeError, ValueError):
                    raise UserError(_("Cantidad máxima no válida.")) from None
                if val > 0 and val < table.people_min:
                    raise UserError(
                        _(
                            "La cantidad máxima debe ser al menos %(n)s "
                            "(mínimo del tramo)."
                        )
                        % {"n": table.people_min}
                    )
                table.write({"people_max": val})
            else:
                try:
                    val = int(float(value or 1))
                except (TypeError, ValueError):
                    raise UserError(_("Delta no válido.")) from None
                if val < 1:
                    raise UserError(_("Delta debe ser al menos 1."))
                table.write({"delta": val})
            self._chain_recompute_table_bounds()
            return self.get_chain_matrix_preview_data(active_table_id=table.id)
        line = self.env["quoter.chain.table.line"].browse(int(line_id or 0)).exists()
        if not line or line.area_id != self:
            raise UserError(_("La celda no pertenece a esta área."))
        if write_kind == "fixed_value":
            try:
                val = float(value or 0.0)
            except (TypeError, ValueError):
                raise UserError(_("Valor no válido.")) from None
            line.write({"fixed_value": val, "value_kind": "fixed"})
        else:
            raise UserError(_("Actualización no reconocida."))
        return self.get_chain_matrix_preview_data(active_table_id=active_table_id)

    def get_chain_line_edit_data(
        self, line_id, employee_count=None, complexity_level_id=None
    ):
        self.ensure_one()
        line = self.env["quoter.chain.table.line"].browse(int(line_id or 0)).exists()
        if not line or line.area_id != self:
            raise UserError(_("Celda no encontrada."))
        emp = (
            int(employee_count)
            if employee_count is not None
            else int(self.chain_test_employee_count or 1)
        )
        level = self._chain_resolve_complexity_level(complexity_level_id)
        return line.get_edit_popup_data(
            employee_count=emp, complexity_level=level
        )

    def save_chain_line_edit(
        self, line_id, value_kind, fixed_value=None, param_values=None
    ):
        self.ensure_one()
        if self._chain_matrix_read_only():
            raise UserError(_("Abra el editor de tabla para editar."))
        line = self.env["quoter.chain.table.line"].browse(int(line_id or 0)).exists()
        if not line or line.area_id != self:
            raise UserError(_("Celda no encontrada."))
        try:
            line.apply_popup_values(value_kind, fixed_value, param_values)
        except ValidationError as err:
            raise UserError(str(err)) from err
        return self.get_chain_matrix_preview_data(active_table_id=line.table_id.id)

    def chain_matrix_set_test_employees(self, count):
        self.ensure_one()
        try:
            val = int(float(count or 1))
        except (TypeError, ValueError):
            raise UserError(_("Cantidad no válida.")) from None
        if val < 1:
            val = 1
        self.write({"chain_test_employee_count": val})
        return self.get_chain_matrix_preview_data(test_employee_count=val)

    def chain_matrix_set_test_people(self, count):
        return self.chain_matrix_set_test_employees(count)

    def chain_matrix_set_test_complexity_level(self, level_id):
        self.ensure_one()
        level = self.env["quoter.complexity.level"].browse(int(level_id or 0))
        if level and level not in self.chain_complexity_level_ids:
            raise UserError(_("El nivel no está configurado en la tabla de aumento %."))
        self.write(
            {
                "chain_test_complexity_level_id": level.id if level else False,
            }
        )
        return self.get_chain_matrix_preview_data(
            test_complexity_level_id=level.id if level else False
        )

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


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
        string="Cerrado (en cotizaciones)",
        default=False,
        groups="quoter.group_quoter_manager",
        help="Si está marcado, el área puede elegirse en pedidos/cotizaciones (campo Áreas). "
        "No bloquea la edición: use «Abrir editor de tabla» / «Cerrar editor de tabla» para eso.",
    )
    quoter_config_edit_mode = fields.Boolean(
        string="Configuración editable",
        default=False,
        help="Cuando está activo, se pueden cambiar la política de matrices, las líneas del "
        "cotizador y la matriz de horas. Al guardar con el botón correspondiente se recalcula "
        "y se vuelve a bloquear.",
    )
    quoter_config_complete = fields.Boolean(
        string="Configuración completa",
        compute="_compute_quoter_config_complete",
        help="True cuando secuencia, roles y niveles están configurados.",
    )

    group_id = fields.Many2one(
        comodel_name="res.groups",
        string="Visibilidad (grupo)",
        help="Si se define, solo usuarios de este grupo ven este sector, las líneas "
        "del cotizador y los productos asociados.",
    )
    is_tax_area = fields.Boolean(
        string="Área TAX",
        compute="_compute_is_tax_area",
        help="True si la visibilidad del área es el grupo Quoter - TAX.",
    )
    is_auditoria_area = fields.Boolean(
        string="Área Auditoría",
        compute="_compute_is_auditoria_area",
        help="True si la visibilidad del área es el grupo Quoter - Auditoría.",
    )
    is_formula_area = fields.Boolean(
        string="Área modo fórmula",
        compute="_compute_is_formula_area",
        help="True si la visibilidad del área es el grupo asignado al modo fórmula (volumen).",
    )
    is_finanzas_area = fields.Boolean(
        string="Área Finanzas",
        compute="_compute_is_finanzas_area",
        help="True si la visibilidad del área es el grupo Quoter - Finanzas.",
    )
    is_payroll_area = fields.Boolean(
        string="Área Payroll",
        compute="_compute_is_payroll_area",
        help="True si la visibilidad del área es el grupo Quoter - Payroll.",
    )
    is_regular_manual_area = fields.Boolean(
        string="Área regular manual",
        compute="_compute_is_regular_manual_area",
    )
    formula_preview_title = fields.Char(
        string="Título vista previa (fórmula)",
        compute="_compute_formula_ui_strings",
    )
    formula_empty_hint = fields.Char(
        string="Texto sin productos (fórmula)",
        compute="_compute_formula_ui_strings",
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
        string="Secciones de cotizador",
        help="Secciones reutilizables entre áreas; sirven para agrupar y dar color en el cotizador.",
    )
    separator_visual_mode = fields.Selection(
        selection=[
            ("none", "Sin color"),
            ("full", "Línea completa con color"),
        ],
        string="Visual separadores",
        default="none",
        required=True,
        help="Cómo se muestran los separadores de etiquetas en las líneas del pedido.",
    )

    complexity_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        relation="quoter_professional_area_complexity_level_rel",
        column1="area_id",
        column2="complexity_level_id",
        string="Niveles de complejidad",
        help="Bajo, medio, alto, etc.: definen variantes de producto y colores en el pedido.",
    )
    complexity_level_custom_label = fields.Char(
        string="Nuevo nombre",
        translate=True,
        help="Si se define, reemplaza la etiqueta «Nivel de complejidad» / «Nivel del área» "
        "en el bloque de cotización del pedido.",
    )
    allow_change_complexity_level = fields.Boolean(
        string="Permite cambiar el nivel",
        default=False,
        help="En cotizaciones, permite modificar el nivel del bloque aunque ya esté guardado; "
        "al cambiarlo se recalculan horas y precios de todas las líneas de producto del bloque.",
    )
    branch_ids = fields.Many2many(
        comodel_name="quoter.area.branch",
        relation="quoter_professional_area_branch_rel",
        column1="area_id",
        column2="branch_id",
        string="Ramas",
        domain=[("selectable", "=", True)],
        help="Primer nivel de segmentación para tabla combinada. Si no define ramas, se usa «Rama única».",
    )
    matrix_branch_id = fields.Many2one(
        comodel_name="quoter.area.branch",
        string="Rama activa (matrices)",
        help="Rama usada para editar/visualizar las tablas del área. Si no se elige, se usa «Rama única».",
    )
    use_branching = fields.Boolean(
        string="Usa ramas en cotización",
        compute="_compute_use_branching",
    )

    area_range_ids = fields.Many2many(
        comodel_name="quoter.area.complexity.range",
        relation="quoter_professional_area_range_rel",
        column1="area_id",
        column2="range_id",
        string="Roles del área",
        help="Roles disponibles para esta área. Se crean desde el menú de roles.",
    )

    hour_matrix_mode = fields.Selection(
        selection=[
            ("regular", "Regular"),
            ("regular_manual", "Regular manual"),
            ("combined", "Combinada"),
            ("formula", "Fórmula"),
            ("formula_chain", "Fórmula en cadena"),
        ],
        string="Tipo de tabla de horas",
        default="regular",
        required=True,
        help="Regular: horas finales por producto y nivel. "
        "Regular manual: cotización línea a línea con horas y precio manuales (Finanzas). "
        "Combinada: tablas A y B. Fórmula: volumen × minutos por rol. "
        "Fórmula en cadena: tablas por cantidad de empleados; fórmula sobre tabla padre.",
    )
    output_hours_minimum = fields.Float(
        string="Redondear el mínimo a",
        default=0.0,
        help="Tabla resultado (salida): si una hora calculada o ingresada queda por debajo "
        "de este valor, se eleva a este mínimo (p. ej. 0,9 con mínimo 1 → 1). "
        "0 = sin ajuste automático.",
    )
    formula_test_volume = fields.Float(
        string="Volumen de prueba (vista fórmula)",
        default=1.0,
        help="Solo para la tabla de prueba en el área; no afecta cotizaciones.",
    )
    table_a_layout = fields.Selection(
        selection=[
            ("normal", "Por rol"),
            ("compact", "Unificada por nivel/rama"),
            ("global", "Unificada global"),
        ],
        string="Formato tabla A",
        default="normal",
        required=True,
        help="Por rol: edición completa por rol. Unificada por nivel/rama: un valor por nivel/rama "
        "replicado a todos los roles. Unificada global: un único valor para toda la tabla A.",
    )
    table_b_kind = fields.Selection(
        selection=[
            ("percent", "Porcentaje (sobre A)"),
            ("multiplier", "Multiplicador"),
            ("formula", "Fórmula (próximamente)"),
        ],
        string="Tipo tabla B",
        default="percent",
        required=True,
        help="Porcentaje: final = A × (B ÷ 100). Multiplicador: final = A × B. "
        "Fórmula: por ahora final = A.",
    )
    table_b_percent_mode = fields.Selection(
        selection=[
            ("exact", "Porcentaje exacto (total 100%)"),
            ("variable", "Porcentaje variable (total libre)"),
        ],
        string="Modo porcentaje B",
        default="exact",
        required=True,
        help="Exacto: mantiene la regla actual (total 100 en escenarios unificados). "
        "Variable: permite totales distintos de 100%.",
    )
    table_b_percent_basis = fields.Selection(
        selection=[
            ("table_a", "Sobre tabla A"),
            (
                "previous_role",
                "Sobre rol anterior (cascada por nivel y rama)",
            ),
        ],
        string="Base del porcentaje B",
        default="table_a",
        required=True,
        help="Sobre tabla A: horas finales = horas A del rol × (B ÷ 100). "
        "Cascada: el primer rol usa su tabla A; cada rol siguiente aplica su % sobre "
        "las horas ya calculadas del rol anterior (mismo nivel de complejidad y rama).",
    )
    matrix_a_unify_role_values = fields.Boolean(
        string="A: unificar valores por rol",
        default=False,
        help="Al editar un rol en tabla A, replica el valor en ese mismo rol para todos los niveles/ramas del producto.",
    )
    matrix_a_hide_repeated_columns = fields.Boolean(
        string="A: ocultar columnas repetidas",
        default=False,
        help="Muestra una sola vez las columnas por rol en tabla A cuando los valores están unificados.",
    )
    matrix_a_unify_category_values = fields.Boolean(
        string="A: unificar valores por nivel de complejidad",
        default=False,
        help="Al editar un nivel de complejidad en tabla A, replica el valor en todos los roles "
        "(Ae, Sr, Gerente, Socio, …) de ese nivel y rama.",
    )
    matrix_a_hide_repeated_category_columns = fields.Boolean(
        string="A: ocultar roles repetidos por nivel de complejidad",
        default=False,
        help="Muestra solo la columna del primer rol bajo cada nivel de complejidad cuando los valores "
        "están unificados por nivel.",
    )
    matrix_b_unify_role_values = fields.Boolean(
        string="B: unificar valores por rol",
        default=False,
        help="Al editar un rol en tabla B, replica el valor en ese mismo rol para todos los niveles/ramas del producto.",
    )
    matrix_b_hide_repeated_columns = fields.Boolean(
        string="B: ocultar columnas repetidas",
        default=False,
        help="Muestra una sola vez las columnas por rol en tabla B cuando los valores están unificados.",
    )
    matrix_unify_branch_values = fields.Boolean(
        string="Unificar valores por rama",
        default=False,
        help="Habilita «Unifica valor» en productos: horas por rama (tabla debajo de A), "
        "sin filas propias en tablas A/B.",
    )
    matrix_shared_b_calculation = fields.Boolean(
        string="Productos varios en tabla B",
        default=False,
        help="Habilita «Productos varios» en cada producto: una sola fila en tabla B "
        "para los marcados; resultado = base (rama o A) × factor B compartido.",
    )
    shared_matrix_b_ids = fields.One2many(
        comodel_name="quoter.area.shared.matrix.b",
        inverse_name="area_id",
        string="Factores B compartidos",
    )
    matrix_b_role_rule_ids = fields.One2many(
        comodel_name="quoter.area.matrix.b.role.rule",
        inverse_name="area_id",
        string="Tabla B: reglas base por rol",
    )
    matrix_b_branch_exception_ids = fields.One2many(
        comodel_name="quoter.area.matrix.b.branch.exception",
        inverse_name="area_id",
        string="Tabla B: excepciones por rama",
    )
    matrix_b_level_exception_ids = fields.One2many(
        comodel_name="quoter.area.matrix.b.level.exception",
        inverse_name="area_id",
        string="Tabla B: excepciones por nivel",
    )
    table_rules_status = fields.Char(
        string="Reglas de tablas",
        compute="_compute_table_rules_status",
    )
    bulk_line_load = fields.Boolean(
        string="Carga múltiple de líneas",
        default=False,
        help="En cotizaciones, muestra «Agregar múltiples líneas» junto a la lista de productos "
        "del bloque para cargar varios productos del área a la vez.",
    )
    load_default_products = fields.Boolean(
        string="Cargar predeterminados",
        default=True,
        help="Si está activo, en cotizaciones se muestra el botón «Cargar predeterminados» "
        "y se pueden incorporar automáticamente los productos marcados como predeterminados.",
    )

    line_ids = fields.One2many(
        comodel_name="quoter.service.line",
        inverse_name="area_id",
        string="Productos del cotizador",
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

    @api.depends("group_id")
    def _compute_is_tax_area(self):
        tax_group = self.env.ref("quoter.group_quoter_tax", raise_if_not_found=False)
        for rec in self:
            rec.is_tax_area = bool(tax_group and rec.group_id == tax_group)

    @api.depends("group_id")
    def _compute_is_auditoria_area(self):
        aud_group = self.env.ref("quoter.group_quoter_auditoria", raise_if_not_found=False)
        for rec in self:
            rec.is_auditoria_area = bool(aud_group and rec.group_id == aud_group)

    @api.depends("group_id")
    def _compute_is_formula_area(self):
        formula_group = self.env.ref("quoter.group_quoter_formula", raise_if_not_found=False)
        for rec in self:
            rec.is_formula_area = bool(formula_group and rec.group_id == formula_group)

    @api.depends("group_id")
    def _compute_is_finanzas_area(self):
        finanzas_group = self.env.ref(
            "quoter.group_quoter_finanzas", raise_if_not_found=False
        )
        for rec in self:
            rec.is_finanzas_area = bool(
                finanzas_group and rec.group_id == finanzas_group
            )

    @api.depends("group_id")
    def _compute_is_payroll_area(self):
        payroll_group = self.env.ref(
            "quoter.group_quoter_payroll", raise_if_not_found=False
        )
        for rec in self:
            rec.is_payroll_area = bool(
                payroll_group and rec.group_id == payroll_group
            )

    @api.depends("hour_matrix_mode")
    def _compute_is_regular_manual_area(self):
        for rec in self:
            rec.is_regular_manual_area = rec.hour_matrix_mode == "regular_manual"

    @api.model
    def _quoter_finanzas_group(self):
        return self.env.ref("quoter.group_quoter_finanzas", raise_if_not_found=False)

    def _quoter_primary_complexity_level(self):
        """Primer nivel configurado en el área (único en Finanzas / regular manual)."""
        self.ensure_one()
        return self.complexity_level_ids.sorted(
            key=lambda lev: (lev.sequence, lev.id)
        )[:1]

    def _quoter_formula_area_label(self):
        """Nombre visible del área para textos de modo fórmula."""
        self.ensure_one()
        return (self.name or "").strip() or _("Área")

    @api.depends("name", "hour_matrix_mode")
    def _compute_formula_ui_strings(self):
        for rec in self:
            if rec.hour_matrix_mode != "formula":
                rec.formula_preview_title = False
                rec.formula_empty_hint = False
                continue
            label = rec._quoter_formula_area_label()
            rec.formula_preview_title = _(
                "Matriz — %(area)s (producto, volumen y horas por rol; abra el editor de tabla)"
            ) % {"area": label}
            rec.formula_empty_hint = _(
                "Sin productos. Agregue líneas en la pestaña Productos."
            )

    def _formula_default_complexity_level(self):
        """Nivel único en modo fórmula (primer nivel configurado en el área)."""
        self.ensure_one()
        return self.complexity_level_ids.sorted(key=lambda lev: (lev.sequence, lev.id))[:1]

    @api.constrains("output_hours_minimum", "is_auditoria_area")
    def _check_output_hours_minimum(self):
        for rec in self:
            minimum = float(rec.output_hours_minimum or 0.0)
            if minimum < 0.0:
                raise ValidationError(
                    _("El mínimo de la tabla resultado no puede ser negativo.")
                )

    def _apply_output_hours_minimum(self, hours):
        self.ensure_one()
        return self.env["quoter.hours.policy"].apply_output_hours_minimum(
            hours, self.output_hours_minimum
        )

    @api.depends("branch_ids")
    def _compute_use_branching(self):
        for rec in self:
            rec.use_branching = bool(rec.branch_ids)

    @api.depends("sequence", "area_range_ids", "complexity_level_ids", "hour_matrix_mode")
    def _compute_quoter_config_complete(self):
        for rec in self:
            if rec.hour_matrix_mode in ("formula", "formula_chain"):
                rec.quoter_config_complete = bool(rec.sequence and rec.area_range_ids)
            else:
                rec.quoter_config_complete = bool(
                    rec.sequence and rec.area_range_ids and rec.complexity_level_ids
                )

    @api.constrains("complexity_level_ids")
    def _check_complexity_level_ids_required(self):
        for rec in self:
            if not rec.complexity_level_ids:
                raise ValidationError(
                    _("Defina al menos un nivel de complejidad en el área.")
                )

    @api.constrains("hour_matrix_mode", "complexity_level_ids")
    def _check_regular_manual_single_level(self):
        for rec in self:
            if (
                rec.hour_matrix_mode == "regular_manual"
                and len(rec.complexity_level_ids) > 1
            ):
                raise ValidationError(
                    _(
                        "En modo «Regular manual» configure un solo nivel "
                        "de complejidad en el área."
                    )
                )

    @api.constrains("branch_ids")
    def _check_branch_config(self):
        default_branch = self._default_quoter_branch()
        for rec in self:
            if default_branch and default_branch in rec.branch_ids:
                raise ValidationError(
                    _(
                        "La rama «Rama única» no se puede seleccionar manualmente en el área. "
                        "Se usa automáticamente cuando no hay ramas configuradas."
                    )
                )

    @api.constrains("matrix_branch_id", "branch_ids")
    def _check_matrix_branch_in_area(self):
        for rec in self:
            if rec.matrix_branch_id and rec.matrix_branch_id not in rec._effective_branch_ids():
                raise ValidationError(
                    _("La rama activa debe pertenecer a las ramas definidas en el área.")
                )

    @api.constrains(
        "matrix_a_unify_role_values",
        "matrix_a_hide_repeated_columns",
        "matrix_a_unify_category_values",
        "matrix_a_hide_repeated_category_columns",
        "matrix_b_unify_role_values",
        "matrix_b_hide_repeated_columns",
    )
    def _check_matrix_unify_hide_flags(self):
        for rec in self:
            if rec.matrix_a_hide_repeated_columns and not rec.matrix_a_unify_role_values:
                raise ValidationError(
                    _("Para ocultar columnas repetidas en tabla A, primero debe activar la unificación por rol.")
                )
            if rec.matrix_a_hide_repeated_category_columns and not rec.matrix_a_unify_category_values:
                raise ValidationError(
                    _(
                        "Para ocultar roles repetidos en tabla A, primero debe activar "
                        "la unificación por nivel de complejidad."
                    )
                )
            if rec.matrix_b_hide_repeated_columns and not rec.matrix_b_unify_role_values:
                raise ValidationError(
                    _("Para ocultar columnas repetidas en tabla B, primero debe activar la unificación por rol.")
                )

    @api.model
    def _default_quoter_branch(self):
        branch = self.env.ref("quoter.quoter_area_branch_unique", raise_if_not_found=False)
        if branch:
            if branch.selectable:
                branch.sudo().write({"selectable": False})
            return branch
        branch = self.env["quoter.area.branch"].search([("name", "=", "Rama única")], limit=1)
        if branch:
            if branch.selectable:
                branch.sudo().write({"selectable": False})
            return branch
        return self.env["quoter.area.branch"].sudo().create(
            {"name": "Rama única", "sequence": 1, "color": 0, "selectable": False}
        )

    def _effective_branch_ids(self):
        self.ensure_one()
        if self.branch_ids:
            return self.branch_ids.sorted(key=lambda b: (b.sequence, b.id))
        return self._default_quoter_branch()

    def _resolve_matrix_branch(self):
        self.ensure_one()
        branches = self._effective_branch_ids()
        if self.matrix_branch_id and self.matrix_branch_id in branches:
            return self.matrix_branch_id
        return branches[:1]

    @api.depends(
        "hour_matrix_mode",
        "table_a_layout",
        "table_b_kind",
        "table_b_percent_mode",
        "table_b_percent_basis",
    )
    def _compute_table_rules_status(self):
        mode_labels = dict(self._fields["hour_matrix_mode"].selection)
        a_labels = dict(self._fields["table_a_layout"].selection)
        b_labels = dict(self._fields["table_b_kind"].selection)
        p_labels = dict(self._fields["table_b_percent_mode"].selection)
        basis_labels = dict(self._fields["table_b_percent_basis"].selection)
        for rec in self:
            if not rec.hour_matrix_mode:
                rec.table_rules_status = _("Falta definir tipo de tabla")
                continue
            mode_label = mode_labels.get(rec.hour_matrix_mode, rec.hour_matrix_mode)
            if rec.hour_matrix_mode in ("formula", "formula_chain", "regular_manual"):
                rec.table_rules_status = mode_label
                continue
            if rec.hour_matrix_mode != "combined":
                rec.table_rules_status = mode_label
                continue
            a_label = a_labels.get(rec.table_a_layout, rec.table_a_layout or "-")
            b_label = b_labels.get(rec.table_b_kind, rec.table_b_kind or "-")
            rec.table_rules_status = _("%(mode)s · A: %(a)s · B: %(b)s") % {
                "mode": mode_label,
                "a": a_label,
                "b": b_label,
            }
            if rec.table_b_kind == "percent":
                p_label = p_labels.get(rec.table_b_percent_mode, rec.table_b_percent_mode or "-")
                rec.table_rules_status += _(" · Porcentaje: %s") % p_label
                basis_label = basis_labels.get(
                    rec.table_b_percent_basis, rec.table_b_percent_basis or "-"
                )
                rec.table_rules_status += _(" · Base B: %s") % basis_label

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "quoter_config_edit_mode" not in vals:
                vals["quoter_config_edit_mode"] = True
        areas = super().create(vals_list)
        for area in areas:
            if not area.matrix_branch_id:
                area.matrix_branch_id = area._resolve_matrix_branch().id
        areas._sync_range_rate_products()
        areas.line_ids._sync_product_level_ranges()
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
        closed = self.filtered("cerrado")
        if closed:
            if vals.get("hour_matrix_mode"):
                raise ValidationError(
                    _(
                        "No puede cambiar la política de horas en un área cerrada. "
                        "Reabra la configuración si debe modificarla."
                    )
                )
            if vals.get("complexity_level_ids"):
                raise ValidationError(
                    _(
                        "No puede cambiar los niveles de complejidad en un área cerrada. "
                        "Reabra la configuración si debe modificarla."
                    )
                )
        policy_fields = (
            "hour_matrix_mode",
            "table_a_layout",
            "table_b_kind",
            "table_b_percent_mode",
            "table_b_percent_basis",
        )
        snapshots = {rec.id: {f: rec[f] for f in policy_fields} for rec in self}
        resort_lines_by_separator = "separator_visual_mode" in vals
        if vals and "matrix_a_unify_role_values" in vals and not vals.get("matrix_a_unify_role_values"):
            vals = dict(vals)
            vals["matrix_a_hide_repeated_columns"] = False
        if vals and "matrix_a_unify_category_values" in vals and not vals.get(
            "matrix_a_unify_category_values"
        ):
            vals = dict(vals)
            vals["matrix_a_hide_repeated_category_columns"] = False
        if vals and "matrix_b_unify_role_values" in vals and not vals.get("matrix_b_unify_role_values"):
            vals = dict(vals)
            vals["matrix_b_hide_repeated_columns"] = False
        if vals.get("matrix_unify_branch_values") is False:
            vals = dict(vals)
            for area in self:
                area.line_ids.filtered("unify_value").write({"unify_value": False})
        if vals.get("matrix_shared_b_calculation") is False:
            vals = dict(vals)
            for area in self:
                area.line_ids.filtered("shared_b_calc").write({"shared_b_calc": False})
        if "branch_ids" in vals:
            for area in self:
                branches = area._effective_branch_ids()
                if (
                    area.matrix_branch_id
                    and branches
                    and area.matrix_branch_id not in branches
                ):
                    area.matrix_branch_id = area._resolve_matrix_branch()
                elif not area.matrix_branch_id and branches:
                    area.matrix_branch_id = area._resolve_matrix_branch()
        res = super().write(vals)
        for rec in self:
            before = snapshots[rec.id]
            after = {f: rec[f] for f in policy_fields}
            if before != after:
                rec._apply_hour_policy_to_level_ranges(before, after)
        if "area_range_ids" in vals:
            for area in self:
                area.line_ids._sync_range_hour_lines()
                if area.hour_matrix_mode == "formula":
                    configs = self.env["quoter.formula.product.config"].search(
                        [("product_tmpl_id.quoter_area_id", "=", area.id)]
                    )
                    configs._sync_formula_range_lines(area=area)
                if area.hour_matrix_mode == "formula_chain":
                    area._chain_sync_all_table_lines()
            self._sync_range_rate_products()
            self._sync_product_level_range_hour_lines()
        if "branch_ids" in vals:
            self.mapped("line_ids")._sync_unify_branch_hour_lines()
        if "area_range_ids" in vals or vals.get("matrix_shared_b_calculation"):
            self.filtered(
                lambda a: a.hour_matrix_mode == "combined" and a.matrix_shared_b_calculation
            )._sync_shared_matrix_b_rows()
        if "complexity_level_ids" in vals or "product_category_id" in vals:
            for area in self:
                area.line_ids._ensure_quoter_product()
                # Crear configuraciones por nivel para productos existentes del área.
                area.line_ids._sync_product_level_ranges()
        if "chain_complexity_increase_ids" in vals:
            self.filtered(
                lambda a: a.hour_matrix_mode == "formula_chain"
            )._chain_clear_stale_test_complexity_level()
        if "branch_ids" in vals:
            for area in self:
                area.line_ids._sync_product_level_ranges()
            orders = self.env["sale.order"].search([("quoter_area_ids", "in", self.ids)])
            if orders:
                orders._quoter_align_block_branches_with_area()
        if resort_lines_by_separator:
            blocks = self.env["quoter.sale.order.area"].search(
                [
                    ("order_id.is_quotation", "=", True),
                    ("area_id", "in", self.ids),
                ]
            )
            if blocks:
                blocks._quoter_rebuild_separator_sections()
        matrix_b_policy_triggers = {
            "hour_matrix_mode",
            "table_a_layout",
            "table_b_kind",
            "table_b_percent_mode",
            "table_b_percent_basis",
            "matrix_b_role_rule_ids",
            "matrix_b_branch_exception_ids",
            "matrix_b_level_exception_ids",
            "area_range_ids",
            "complexity_level_ids",
            "branch_ids",
        }
        if matrix_b_policy_triggers.intersection(vals.keys()):
            self._apply_matrix_b_advanced_rules_to_level_ranges()
            combined_shared = self.filtered(
                lambda a: a.hour_matrix_mode == "combined"
                and a.matrix_shared_b_calculation
            )
            if combined_shared:
                combined_shared._apply_matrix_b_policy_to_shared_matrix_b()
                combined_shared._recompute_shared_b_calc_outputs()
        return res

    def _apply_hour_policy_to_level_ranges(self, before, after):
        """Propaga cambios de política de horas a todas las plantillas nivel×producto del área."""
        self.ensure_one()
        LevelRange = self.env["quoter.product.level.range"]
        lrs = LevelRange.search([("area_id", "=", self.id)])

        if after["hour_matrix_mode"] in (
            "regular",
            "regular_manual",
            "formula",
            "formula_chain",
        ):
            for lr in lrs:
                lr.output_line_ids.write({"matrix_a_id": False})
            lrs.mapped("matrix_a_ids").unlink()
            lrs.mapped("matrix_b_ids").unlink()
            if after["hour_matrix_mode"] == "formula":
                for line in self.line_ids:
                    if line.product_tmpl_id:
                        self.env["quoter.formula.product.config"].get_config_for_template(
                            line.product_tmpl_id, self
                        )
            if after["hour_matrix_mode"] == "formula_chain":
                self._chain_sync_all_table_lines()
            return

        became_combined = (
            before["hour_matrix_mode"] != "combined"
            and after["hour_matrix_mode"] == "combined"
        )
        if became_combined:
            for lr in lrs:
                lr._prepare_combined_defaults_from_final_hours()

        if (
            after["table_b_kind"] != before["table_b_kind"]
            or after["table_b_percent_mode"] != before["table_b_percent_mode"]
            or after["table_b_percent_basis"] != before["table_b_percent_basis"]
        ):
            for lr in lrs:
                lr._apply_table_b_kind_default_factors(
                    after["table_b_kind"], after["table_a_layout"], after["table_b_percent_mode"]
                )

        if (
            after["table_a_layout"] in ("compact", "global")
            and before["table_a_layout"] not in ("compact", "global")
        ):
            for lr in lrs:
                lr._unify_hours_a_compact_from_first_row()
                lr._normalize_matrix_b_for_percent_split_if_needed()

        lrs._apply_combined_final_all()

    def _matrix_b_policy_maps(self):
        """Índices de reglas/excepciones de tabla B para cálculo rápido."""
        self.ensure_one()
        role_defaults = {
            rec.area_range_id.id: float(rec.default_factor or 0.0)
            for rec in self.matrix_b_role_rule_ids
            if rec.area_range_id
        }
        role_flags = {
            rec.area_range_id.id: {
                "is_fixed": bool(rec.is_fixed),
                "is_hidden": bool(rec.is_hidden),
            }
            for rec in self.matrix_b_role_rule_ids
            if rec.area_range_id
        }
        level_overrides = {
            (rec.complexity_level_id.id, rec.area_range_id.id): float(rec.factor_override or 0.0)
            for rec in self.matrix_b_level_exception_ids
            if rec.complexity_level_id and rec.area_range_id
        }
        branch_overrides = {
            (rec.branch_id.id, rec.area_range_id.id): float(rec.factor_override or 0.0)
            for rec in self.matrix_b_branch_exception_ids
            if rec.branch_id and rec.area_range_id
        }
        return role_defaults, role_flags, level_overrides, branch_overrides

    def _matrix_b_policy_factor_for(self, area_range_id, level_id, branch_id, fallback=0.0):
        """Factor final de B respetando prioridad excepción nivel > rama > regla base."""
        self.ensure_one()
        role_defaults, _role_flags, level_overrides, branch_overrides = self._matrix_b_policy_maps()
        if (level_id, area_range_id) in level_overrides:
            return level_overrides[(level_id, area_range_id)]
        if (branch_id, area_range_id) in branch_overrides:
            return branch_overrides[(branch_id, area_range_id)]
        if area_range_id in role_defaults:
            return role_defaults[area_range_id]
        return float(fallback or 0.0)

    def _apply_matrix_b_advanced_rules_to_level_ranges(self, level_ranges=False):
        """Aplica reglas/excepciones de tabla B sobre plantillas nivel×producto del área."""
        LevelRange = self.env["quoter.product.level.range"]
        for area in self:
            if area.hour_matrix_mode != "combined":
                continue
            if level_ranges:
                lrs = level_ranges.filtered(lambda lr, a=area: lr.area_id == a)
            else:
                lrs = LevelRange.search([("area_id", "=", area.id)])
            if not lrs:
                continue
            for lr in lrs:
                if lr._quoter_line_shared_b_calc():
                    continue
                level_id = lr.complexity_level_id.id
                branch_id = lr.branch_id.id
                for brow in lr.matrix_b_ids:
                    factor = area._matrix_b_policy_factor_for(
                        brow.area_range_id.id,
                        level_id,
                        branch_id,
                        fallback=brow.factor,
                    )
                    if float(brow.factor or 0.0) != float(factor or 0.0):
                        brow.with_context(quoter_skip_b_percent_validation=True).write(
                            {"factor": factor}
                        )

    def _apply_matrix_b_policy_to_shared_matrix_b(self):
        """Sincroniza factor base de «Productos varios» solo desde reglas por rol (no excepciones por nivel)."""
        for area in self:
            if area.hour_matrix_mode != "combined" or not area.matrix_shared_b_calculation:
                continue
            role_defaults, role_flags, _level_ov, _branch_ov = area._matrix_b_policy_maps()
            for sb in area.shared_matrix_b_ids:
                ar_id = sb.area_range_id.id
                if ar_id not in role_defaults:
                    continue
                if role_flags.get(ar_id, {}).get("is_hidden"):
                    continue
                factor = role_defaults[ar_id]
                if float(sb.factor or 0.0) != float(factor or 0.0):
                    sb.with_context(quoter_skip_b_percent_validation=True).write(
                        {"factor": factor}
                    )

    def _matrix_preview_set_level_b_exception(self, level_id, area_range_id, factor):
        self.ensure_one()
        LevelExc = self.env["quoter.area.matrix.b.level.exception"]
        exc = self.matrix_b_level_exception_ids.filtered(
            lambda e, lid=level_id, ar=area_range_id: e.complexity_level_id.id == lid
            and e.area_range_id.id == ar
        )[:1]
        if exc:
            exc.write({"factor_override": factor})
        else:
            LevelExc.create(
                {
                    "area_id": self.id,
                    "complexity_level_id": level_id,
                    "area_range_id": area_range_id,
                    "factor_override": factor,
                }
            )

    def _matrix_preview_set_branch_b_exception(self, branch_id, area_range_id, factor):
        self.ensure_one()
        BranchExc = self.env["quoter.area.matrix.b.branch.exception"]
        exc = self.matrix_b_branch_exception_ids.filtered(
            lambda e, bid=branch_id, ar=area_range_id: e.branch_id.id == bid
            and e.area_range_id.id == ar
        )[:1]
        if exc:
            exc.write({"factor_override": factor})
        else:
            BranchExc.create(
                {
                    "area_id": self.id,
                    "branch_id": branch_id,
                    "area_range_id": area_range_id,
                    "factor_override": factor,
                }
            )

    def _sync_product_level_range_hour_lines(self):
        """Filas B / A / salida en plantillas quoter.product.level.range al cambiar roles del área."""
        LevelRange = self.env["quoter.product.level.range"]
        for area in self:
            lines = area.line_ids.filtered("product_tmpl_id")
            if not lines:
                continue
            generic_tmpl_ids = lines.filtered("is_generic_link").mapped("product_tmpl_id").ids
            area_tmpl_ids = lines.filtered(lambda l: not l.is_generic_link).mapped(
                "product_tmpl_id"
            ).ids
            lrs = LevelRange.browse()
            if area_tmpl_ids:
                lrs |= LevelRange.search(
                    [("area_id", "=", area.id), ("product_tmpl_id", "in", area_tmpl_ids)]
                )
            if generic_tmpl_ids:
                lrs |= LevelRange.search(
                    [("area_id", "=", False), ("product_tmpl_id", "in", generic_tmpl_ids)]
                )
            if lrs:
                lrs.with_context(quoter_sync_matrix_area_id=area.id)._sync_matrix_rows()

    def _complexity_levels_ordered(self):
        """Niveles asignados al área ordenados por secuencia (menor → mayor) e id."""
        self.ensure_one()
        return self.complexity_level_ids.sorted(key=lambda lev: (lev.sequence, lev.id))

    @staticmethod
    def _matrix_b_cell_value(row, li, ri):
        lm = row.get("levels_matrix_b") or []
        if li >= len(lm):
            return None
        line = lm[li]
        if ri >= len(line):
            return None
        return round(float(line[ri] or 0.0), 6)

    def _matrix_b_role_expansion_kind(self, ri, level_branch_specs, rows_out):
        """none | by_level | by_branch_level según si el rol varía solo entre niveles o también entre ramas."""
        if not rows_out or not level_branch_specs:
            return "none"
        all_vals = set()
        for row in rows_out:
            for li in range(len(level_branch_specs)):
                v = self._matrix_b_cell_value(row, li, ri)
                if v is not None:
                    all_vals.add(v)
        if len(all_vals) <= 1:
            return "none"
        by_level = {}
        for li, spec in enumerate(level_branch_specs):
            lev_id = spec["level_id"]
            for row in rows_out:
                v = self._matrix_b_cell_value(row, li, ri)
                if v is None:
                    continue
                by_level.setdefault(lev_id, set()).add(v)
        for vs in by_level.values():
            if len(vs) > 1:
                return "by_branch_level"
        if len(by_level) > 1:
            return "by_level"
        return "by_branch_level"

    def _matrix_b_compact_column_defs(self, ranges, levels, branches, level_branch_specs, rows_out):
        cols = []
        range_list = list(ranges)
        for ri, r in enumerate(range_list):
            kind = self._matrix_b_role_expansion_kind(ri, level_branch_specs, rows_out)
            if kind == "none":
                cols.append(
                    {
                        "area_range_id": r.id,
                        "expand": "none",
                        "level_id": False,
                        "branch_id": False,
                        "role_name": r.name,
                        "level_name": "",
                        "branch_name": "",
                        "level_color": 0,
                    }
                )
            elif kind == "by_level":
                br0 = branches[:1]
                has_selected_branches = bool(
                    self.branch_ids.filtered(lambda b: b.selectable)
                )
                br_name = (br0.name if br0 and has_selected_branches else "") or ""
                br_id = br0.id if br0 else False
                for lev in levels:
                    cols.append(
                        {
                            "area_range_id": r.id,
                            "expand": "level",
                            "level_id": lev.id,
                            "branch_id": br_id,
                            "role_name": r.name,
                            "level_name": lev.name,
                            "branch_name": br_name,
                            "level_color": int(lev.color or 0),
                        }
                    )
            else:
                for spec in level_branch_specs:
                    cols.append(
                        {
                            "area_range_id": r.id,
                            "expand": "branch_level",
                            "level_id": spec["level_id"],
                            "branch_id": spec["branch_id"],
                            "role_name": r.name,
                            "level_name": spec["name"],
                            "branch_name": spec["branch_name"] or "",
                            "level_color": int(spec.get("color") or 0),
                        }
                    )
        return cols

    def _matrix_b_first_lr_brow_for_role(
        self, tmpl_id, area_range_id, level_branch_specs, LevelRange, is_generic_link=False
    ):
        for spec in level_branch_specs:
            lr = LevelRange.search(
                self._matrix_level_range_domain(
                    tmpl_id,
                    spec["level_id"],
                    spec["branch_id"],
                    is_generic_link=is_generic_link,
                ),
                limit=1,
            )
            if not lr:
                continue
            brec = lr.matrix_b_ids.filtered(
                lambda b, arid=area_range_id: b.area_range_id.id == arid
            )[:1]
            if brec:
                return lr, brec
        return LevelRange.browse(), self.env["quoter.product.level.range.matrix.b"].browse()

    def _matrix_b_compact_cell_meta(
        self,
        tmpl_id,
        col,
        level_branch_specs,
        branches,
        levels,
        LevelRange,
        is_generic_link=False,
    ):
        self.ensure_one()
        ar_id = col["area_range_id"]
        lr = LevelRange.browse()
        brec = self.env["quoter.product.level.range.matrix.b"].browse()
        exp = col.get("expand") or "none"
        if exp == "none":
            lr, brec = self._matrix_b_first_lr_brow_for_role(
                tmpl_id, ar_id, level_branch_specs, LevelRange, is_generic_link
            )
        elif exp == "level":
            bid = col["branch_id"] or (branches[0].id if branches else False)
            lid = col["level_id"]
            if bid and lid:
                lr = LevelRange.search(
                    self._matrix_level_range_domain(
                        tmpl_id, lid, bid, is_generic_link=is_generic_link
                    ),
                    limit=1,
                )
                if lr:
                    brec = lr.matrix_b_ids.filtered(
                        lambda b, aid=ar_id: b.area_range_id.id == aid
                    )[:1]
        else:
            bid = col["branch_id"]
            lid = col["level_id"]
            if bid and lid:
                lr = LevelRange.search(
                    self._matrix_level_range_domain(
                        tmpl_id, lid, bid, is_generic_link=is_generic_link
                    ),
                    limit=1,
                )
                if lr:
                    brec = lr.matrix_b_ids.filtered(
                        lambda b, aid=ar_id: b.area_range_id.id == aid
                    )[:1]
        val = round(float(brec.factor or 0.0), 2) if brec else 0.0
        return {
            "value": val,
            "level_range_id": lr.id if lr else 0,
            "matrix_b_id": brec.id if brec else 0,
            "area_range_id": ar_id,
        }

    def _matrix_level_range_domain(self, tmpl_id, level_id, branch_id, is_generic_link=False):
        """Dominio de plantilla nivel: propia del área o genérica global (area_id vacío)."""
        domain = [
            ("product_tmpl_id", "=", tmpl_id),
            ("complexity_level_id", "=", level_id),
            ("branch_id", "=", branch_id),
        ]
        if is_generic_link:
            domain.append(("area_id", "=", False))
        else:
            domain.append(("area_id", "=", self.id))
        return domain

    def _matrix_level_range_for_line_spec(self, line, spec):
        LevelRange = self.env["quoter.product.level.range"]
        return LevelRange.search(
            self._matrix_level_range_domain(
                line.product_tmpl_id.id,
                spec["level_id"],
                spec["branch_id"],
                is_generic_link=line.is_generic_link,
            ),
            limit=1,
        )

    def _matrix_validate_level_range_for_area(self, level_range):
        """Valida que la plantilla pertenezca a un producto listado en el área."""
        self.ensure_one()
        if not level_range:
            raise UserError(_("Plantilla de nivel no válida para esta área."))
        tmpl_ids = set(self.line_ids.filtered("product_tmpl_id").mapped("product_tmpl_id").ids)
        if level_range.product_tmpl_id.id not in tmpl_ids:
            raise UserError(_("Plantilla de nivel no válida para esta área."))
        if level_range.area_id and level_range.area_id != self:
            raise UserError(_("Plantilla de nivel no válida para esta área."))

    def _quoter_sync_level_range_matrix_rows(self):
        """Asegura líneas de salida (regular) o A/B (combinada) antes de mostrar/editar la matriz."""
        self.ensure_one()
        LevelRange = self.env["quoter.product.level.range"]
        lines = self.line_ids.filtered("product_tmpl_id")
        if not lines:
            return
        generic_tmpl_ids = lines.filtered("is_generic_link").mapped("product_tmpl_id").ids
        area_tmpl_ids = lines.filtered(lambda l: not l.is_generic_link).mapped(
            "product_tmpl_id"
        ).ids
        lrs = LevelRange.browse()
        if area_tmpl_ids:
            lrs |= LevelRange.search(
                [("area_id", "=", self.id), ("product_tmpl_id", "in", area_tmpl_ids)]
            )
        if generic_tmpl_ids:
            lrs |= LevelRange.search(
                [("area_id", "=", False), ("product_tmpl_id", "in", generic_tmpl_ids)]
            )
        if lrs:
            lrs.with_context(quoter_sync_matrix_area_id=self.id)._sync_matrix_rows()
        if self.matrix_unify_branch_values or self.matrix_shared_b_calculation:
            self._sync_shared_matrix_b_rows()

    def _sync_shared_matrix_b_rows(self):
        """Factores B de la fila «Productos varios» (un factor por rol del área)."""
        SB = self.env["quoter.area.shared.matrix.b"]
        for area in self:
            ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:4]
            keep_ids = set(ranges.ids)
            area.shared_matrix_b_ids.filtered(
                lambda b: b.area_range_id.id not in keep_ids
            ).unlink()
            for ar in ranges:
                if not area.shared_matrix_b_ids.filtered(
                    lambda b, role=ar: b.area_range_id == role
                ):
                    SB.create(
                        {
                            "area_id": area.id,
                            "area_range_id": ar.id,
                            "factor": 0.0,
                        }
                    )

    def _matrix_recompute_after_write(self, level_ranges):
        """Tras editar tabla A o B: recalcula salida (compartida o por producto normal)."""
        self.ensure_one()
        if self.hour_matrix_mode != "combined" or not level_ranges:
            return
        shared_tmpls = set(
            self.line_ids.filtered("shared_b_calc").mapped("product_tmpl_id").ids
        )
        if (
            self.matrix_shared_b_calculation
            and shared_tmpls
            and any(
                lr.product_tmpl_id.id in shared_tmpls
                for lr in level_ranges
                if lr.product_tmpl_id
            )
        ):
            self._recompute_shared_b_calc_outputs()
        for lr in level_ranges:
            if lr._quoter_line_unify_value() or lr._quoter_line_shared_b_calc():
                continue
            lr._recompute_combined_output_hours()

    def _recompute_normal_combined_outputs(self):
        """Recalcula salida de productos normales (sin unifica valor ni productos varios)."""
        self.ensure_one()
        if self.hour_matrix_mode != "combined":
            return
        LevelRange = self.env["quoter.product.level.range"]
        skip_tmpls = set(
            self.line_ids.filtered(lambda l: l.unify_value or l.shared_b_calc).mapped(
                "product_tmpl_id"
            ).ids
        )
        for line in self.line_ids.filtered(
            lambda l: l.product_tmpl_id and l.product_tmpl_id.id not in skip_tmpls
        ):
            if line.is_generic_link:
                domain = [
                    ("area_id", "=", False),
                    ("product_tmpl_id", "=", line.product_tmpl_id.id),
                ]
            else:
                domain = [
                    ("area_id", "=", self.id),
                    ("product_tmpl_id", "=", line.product_tmpl_id.id),
                ]
            for lr in LevelRange.search(domain):
                lr._recompute_combined_output_hours()

    def _recompute_shared_b_calc_outputs(self):
        """Recalcula salida para productos con «Productos varios» (base × B compartido)."""
        for area in self:
            if area.hour_matrix_mode != "combined" or not area.matrix_shared_b_calculation:
                continue
            area._recompute_shared_b_calc_outputs_single()

    def _recompute_shared_b_calc_outputs_single(self):
        """Recalcula salida B compartida para un único área (modo combinado)."""
        self.ensure_one()
        LevelRange = self.env["quoter.product.level.range"]
        lines = self.line_ids.filtered(lambda l: l.shared_b_calc and l.product_tmpl_id)
        if not lines:
            return
        ranges = self.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))[:4]
        ctx = dict(self.env.context, quoter_skip_output_hours_guard=True)
        for line in lines:
            if line.is_generic_link:
                lrs = LevelRange.search(
                    [
                        ("area_id", "=", False),
                        ("product_tmpl_id", "=", line.product_tmpl_id.id),
                    ]
                )
            else:
                lrs = LevelRange.search(
                    [
                        ("area_id", "=", self.id),
                        ("product_tmpl_id", "=", line.product_tmpl_id.id),
                    ]
                )
            cascade = (
                self.hour_matrix_mode == "combined"
                and self.table_b_kind == "percent"
                and self.table_b_percent_basis == "previous_role"
            )
            for lr in lrs.sorted(
                key=lambda r: (
                    r.complexity_level_id.sequence or 0,
                    r.complexity_level_id.id,
                    r.branch_id.sequence or 0,
                    r.branch_id.id,
                )
            ):
                prev_output = None
                for ar in ranges:
                    out = lr.output_line_ids.filtered(
                        lambda o, role=ar: o.area_range_id == role
                    )[:1]
                    sb = self.shared_matrix_b_ids.filtered(
                        lambda b, role=ar: b.area_range_id == role
                    )[:1]
                    if not out or not sb:
                        continue
                    if line.unify_value:
                        ub = line.unify_branch_hour_ids.filtered(
                            lambda h, b=lr.branch_id: h.branch_id == b
                        )[:1]
                        hours_a = float(ub.hours or 0.0) if ub else 0.0
                    else:
                        arow = lr.matrix_a_ids.filtered(
                            lambda a, role=ar: a.area_range_id == role
                        )[:1]
                        hours_a = float(arow.hours or 0.0) if arow else 0.0
                    factor = self._matrix_b_policy_factor_for(
                        ar.id,
                        lr.complexity_level_id.id,
                        lr.branch_id.id,
                        fallback=float(sb.factor or 0.0),
                    )
                    if cascade:
                        base = prev_output if prev_output is not None else hours_a
                        h = base * (factor / 100.0) if factor else 0.0
                    else:
                        h = lr._final_hours_from_a_and_b(hours_a, factor)
                    prev_output = h
                    h = self._apply_output_hours_minimum(h)
                    if float(out.hours or 0.0) != float(h):
                        out.with_context(ctx).write({"hours": h})

    def _matrix_preview_shared_b_row(self, ranges, level_branch_specs):
        """Fila sintética «Productos varios» en tabla B (productos con «Productos varios» marcado)."""
        self.ensure_one()
        if not self.matrix_shared_b_calculation:
            return None
        if not self.line_ids.filtered(lambda l: l.shared_b_calc and l.product_tmpl_id):
            return None
        self._sync_shared_matrix_b_rows()
        levels_matrix_b = []
        levels_meta = []
        shared_ids = []
        for spec in level_branch_specs:
            level_id = spec.get("level_id")
            branch_id = spec.get("branch_id")
            row_b = []
            row_ids = []
            row_level_ids = []
            row_branch_ids = []
            for ar in ranges:
                sb = self.shared_matrix_b_ids.filtered(
                    lambda b, role=ar: b.area_range_id == role
                )[:1]
                fallback = float(sb.factor or 0.0) if sb else 0.0
                factor = (
                    self._matrix_b_policy_factor_for(
                        ar.id, level_id, branch_id, fallback=fallback
                    )
                    if level_id and branch_id
                    else fallback
                )
                row_b.append(round(factor, 2))
                row_ids.append(sb.id if sb else 0)
                row_level_ids.append(level_id or 0)
                row_branch_ids.append(branch_id or 0)
            levels_matrix_b.append(row_b)
            levels_meta.append(
                {
                    "level_range_id": 0,
                    "output_ids": [0] * len(ranges),
                    "matrix_a_ids": [0] * len(ranges),
                    "matrix_b_ids": row_ids,
                    "level_ids": row_level_ids,
                    "branch_ids": row_branch_ids,
                    "shared_b": True,
                }
            )
            if not shared_ids and row_ids:
                shared_ids = row_ids
        return {
            "line_name": _("Productos varios"),
            "is_shared_b_row": True,
            "shared_b_calc": True,
            "unify_value": False,
            "levels_matrix_b": levels_matrix_b,
            "levels_meta": levels_meta,
            "levels_hours": [[0.0] * len(ranges) for _ in level_branch_specs],
            "levels_matrix_a": [[0.0] for _ in level_branch_specs],
        }

    def get_hours_matrix_preview_data(self):
        """Datos para la matriz JS del formulario de área (horas resultado por producto / nivel / rol)."""
        self.ensure_one()
        self.line_ids._sync_product_level_ranges()
        self._quoter_sync_level_range_matrix_rows()
        combined_preview = self.hour_matrix_mode == "combined"
        if combined_preview and self.matrix_shared_b_calculation:
            self._sync_shared_matrix_b_rows()
            if self.line_ids.filtered("shared_b_calc"):
                self._recompute_shared_b_calc_outputs()
        if combined_preview:
            self._recompute_normal_combined_outputs()
        can_edit_matrix = self.env.user.has_group("quoter.group_quoter_manager")
        matrix_read_only = not self.quoter_config_edit_mode or not can_edit_matrix
        ranges = self.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))
        levels = self._complexity_levels_ordered()
        selected_branches = self.branch_ids.filtered(lambda b: b.selectable).sorted(
            key=lambda b: (b.sequence, b.id)
        )
        # Solo aplican ramas explícitamente seleccionadas en el área.
        # Si no hay ninguna, usar una única rama técnica y ocultar cabeceras de rama.
        branches = selected_branches or self._default_quoter_branch()
        if not selected_branches:
            branches = branches[:1]
        level_branch_specs = []
        use_branch_labels = len(selected_branches) > 1
        for lev in levels:
            for branch in branches:
                level_branch_specs.append(
                    {
                        "level_id": lev.id,
                        "branch_id": branch.id,
                        "name": lev.name,
                        "branch_name": branch.name if use_branch_labels else "",
                        "color": int(lev.color or 0),
                    }
                )
        mode_meta = self.fields_get(["hour_matrix_mode"])["hour_matrix_mode"]
        mode_label = dict(mode_meta["selection"]).get(self.hour_matrix_mode, "")
        labels = {
            "complexity": _("COMPLEJIDAD (en Hrs por tarea)"),
            "task": _("TAREA"),
            "mode": mode_label,
            # Solo cabecera de ramas en la matriz si el área tiene ramas explícitas (many2many).
            "matrix_has_area_branches": bool(use_branch_labels),
        }
        if not ranges or not levels:
            return {
                "labels": labels,
                "area_id": self.id,
                "matrix_read_only": matrix_read_only,
                "hour_matrix_mode": self.hour_matrix_mode,
                "table_a_layout": self.table_a_layout,
                "table_b_kind": self.table_b_kind,
                "show_matrix_ab": False,
                "range_ids": [],
                "ranges": [],
                "levels": [],
                "rows": [],
                "matrix_b_compact_columns": [],
                "empty_message": _("Defina roles del área y niveles de complejidad."),
            }
        LevelRange = self.env["quoter.product.level.range"]
        combined = self.hour_matrix_mode == "combined"
        compact_a = self.table_a_layout in ("compact", "global")
        global_a = self.table_a_layout == "global"
        b_kind_meta = self.fields_get(["table_b_kind"])["table_b_kind"]
        b_kind_label = dict(b_kind_meta["selection"]).get(self.table_b_kind, "")
        if self.hour_matrix_mode == "regular":
            labels["output_title"] = _("Salida (horas finales)")
        else:
            labels["output_title"] = _("Salida (horas resultado)")
            labels["matrix_a_title"] = _("Tabla A (horas base)")
            labels["matrix_b_title"] = _("Tabla B (%s)") % (b_kind_label or self.table_b_kind)
            labels["unify_branch_title"] = _("Horas por rama (unifica valor)")
        labels["percent_mode"] = self.table_b_percent_mode
        labels["matrix_a_unify_role_values"] = bool(self.matrix_a_unify_role_values)
        labels["matrix_a_hide_repeated_columns"] = bool(self.matrix_a_hide_repeated_columns)
        labels["matrix_a_unify_category_values"] = bool(self.matrix_a_unify_category_values)
        labels["matrix_a_hide_repeated_category_columns"] = bool(
            self.matrix_a_hide_repeated_category_columns
        )
        labels["matrix_b_unify_role_values"] = bool(self.matrix_b_unify_role_values)
        labels["matrix_b_hide_repeated_columns"] = bool(self.matrix_b_hide_repeated_columns)
        if not self.quoter_config_edit_mode:
            labels["matrix_edit_hint"] = _(
                "Pulse «Abrir editor de tabla» en la cabecera del área para modificar la matriz. "
                "(Solo el grupo Quoter - Gerente.)"
            )
        rows_out = []
        unify_branch_rows = []
        unify_branches = []
        if selected_branches:
            unify_branches = [
                {"branch_id": b.id, "name": b.name}
                for b in selected_branches.sorted(key=lambda b: (b.sequence, b.id))
            ]
        elif branches:
            unify_branches = [{"branch_id": branches[0].id, "name": branches[0].name}]

        for line in self.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            if not line.product_tmpl_id:
                continue
            if line.unify_value and combined:
                line._sync_unify_branch_hour_lines()
                cells = []
                for ub in unify_branches:
                    bid = ub["branch_id"]
                    row_ub = line.unify_branch_hour_ids.filtered(
                        lambda h, b=bid: h.branch_id.id == b
                    )[:1]
                    cells.append(
                        {
                            "branch_id": bid,
                            "hours": round(float(row_ub.hours or 0.0), 2) if row_ub else 0.0,
                            "record_id": row_ub.id if row_ub else 0,
                        }
                    )
                unify_branch_rows.append(
                    {
                        "line_id": line.id,
                        "line_name": line.name or line.product_tmpl_id.display_name,
                        "cells": cells,
                    }
                )
            tmpl_id = line.product_tmpl_id.id
            is_unify_value = bool(line.unify_value and combined)
            is_shared_b = bool(
                line.shared_b_calc and combined and self.matrix_shared_b_calculation
            )
            levels_hours = []
            levels_matrix_a = []
            levels_matrix_b = []
            levels_meta = []
            global_matrix_a_value = 0.0
            global_matrix_a_level_range_id = 0
            for spec in level_branch_specs:
                lr = self._matrix_level_range_for_line_spec(line, spec)
                zr = [0.0] * len(ranges)
                if not lr:
                    levels_hours.append(list(zr))
                    levels_matrix_a.append([0.0] if (compact_a or global_a) else list(zr))
                    levels_matrix_b.append(list(zr))
                    levels_meta.append(
                        {
                            "level_range_id": False,
                            "output_ids": [0] * len(ranges),
                            "matrix_a_ids": [0] * len(ranges),
                            "matrix_b_ids": [0] * len(ranges),
                        }
                    )
                    continue
                out_by_range = {
                    o.area_range_id.id: self._apply_output_hours_minimum(o.hours)
                    for o in lr.output_line_ids
                }
                levels_hours.append([round(out_by_range.get(r.id, 0.0), 2) for r in ranges])
                a_by_range = {
                    a.area_range_id.id: float(a.hours or 0.0) for a in lr.matrix_a_ids
                }
                if compact_a or global_a:
                    av = 0.0
                    if ranges:
                        av = float(a_by_range.get(ranges[0].id, 0.0) or 0.0)
                    if not av and a_by_range:
                        av = float(next(iter(a_by_range.values())))
                    levels_matrix_a.append([round(av, 2)])
                    if global_a and not global_matrix_a_level_range_id:
                        global_matrix_a_level_range_id = lr.id
                        global_matrix_a_value = round(av, 2)
                else:
                    levels_matrix_a.append([round(a_by_range.get(r.id, 0.0), 2) for r in ranges])
                b_by_range = {
                    b.area_range_id.id: float(b.factor or 0.0) for b in lr.matrix_b_ids
                }
                levels_matrix_b.append([round(b_by_range.get(r.id, 0.0), 2) for r in ranges])
                output_ids = []
                matrix_a_ids = []
                matrix_b_ids = []
                for r in ranges:
                    orec = lr.output_line_ids.filtered(lambda o, ar=r: o.area_range_id == ar)[:1]
                    output_ids.append(orec.id if orec else 0)
                    arec = lr.matrix_a_ids.filtered(lambda a, ar=r: a.area_range_id == ar)[:1]
                    matrix_a_ids.append(arec.id if arec else 0)
                    brec = lr.matrix_b_ids.filtered(lambda b, ar=r: b.area_range_id == ar)[:1]
                    matrix_b_ids.append(brec.id if brec else 0)
                levels_meta.append(
                    {
                        "level_range_id": lr.id,
                        "output_ids": output_ids,
                        "matrix_a_ids": matrix_a_ids,
                        "matrix_b_ids": matrix_b_ids,
                    }
                )
            if is_unify_value and combined and not is_shared_b:
                continue
            rows_out.append(
                {
                    "line_id": line.id,
                    "line_name": line.name or line.product_tmpl_id.display_name,
                    "unify_value": is_unify_value,
                    "shared_b_calc": is_shared_b,
                    "levels_hours": levels_hours,
                    "levels_matrix_a": levels_matrix_a,
                    "levels_matrix_b": levels_matrix_b,
                    "levels_meta": levels_meta,
                    "global_matrix_a_value": global_matrix_a_value,
                    "global_matrix_a_level_range_id": global_matrix_a_level_range_id,
                }
            )
        matrix_b_compact_columns = []
        if combined and self.matrix_b_unify_role_values and self.matrix_b_hide_repeated_columns and rows_out:
            levels_ord = self._complexity_levels_ordered()
            branches_eff = self._effective_branch_ids()
            matrix_b_compact_columns = self._matrix_b_compact_column_defs(
                ranges, levels_ord, branches_eff, level_branch_specs, rows_out
            )
            lines_with_product = self.line_ids.filtered(lambda l: l.product_tmpl_id).sorted(
                key=lambda l: (l.sequence, l.id)
            )
            rows_by_line_id = {row["line_id"]: row for row in rows_out if row.get("line_id")}
            for line in lines_with_product:
                row = rows_by_line_id.get(line.id)
                if not row:
                    continue
                tmpl_id = line.product_tmpl_id.id
                row["matrix_b_compact_cells"] = [
                    self._matrix_b_compact_cell_meta(
                        tmpl_id,
                        c,
                        level_branch_specs,
                        branches_eff,
                        levels_ord,
                        LevelRange,
                        line.is_generic_link,
                    )
                    for c in matrix_b_compact_columns
                ]
        matrix_b_shared_row = None
        if combined and self.matrix_shared_b_calculation:
            matrix_b_shared_row = self._matrix_preview_shared_b_row(
                ranges, level_branch_specs
            )
        return {
            "labels": labels,
            "area_id": self.id,
            "matrix_read_only": matrix_read_only,
            "hour_matrix_mode": self.hour_matrix_mode,
            "table_a_layout": self.table_a_layout,
            "table_b_kind": self.table_b_kind,
            "table_b_percent_mode": self.table_b_percent_mode,
            "table_b_percent_basis": self.table_b_percent_basis,
            "show_matrix_ab": combined,
            "matrix_a_unify_role_values": bool(self.matrix_a_unify_role_values),
            "matrix_a_hide_repeated_columns": bool(self.matrix_a_hide_repeated_columns),
            "matrix_a_unify_category_values": bool(self.matrix_a_unify_category_values),
            "matrix_a_hide_repeated_category_columns": bool(
                self.matrix_a_hide_repeated_category_columns
            ),
            "matrix_b_unify_role_values": bool(self.matrix_b_unify_role_values),
            "matrix_b_hide_repeated_columns": bool(self.matrix_b_hide_repeated_columns),
            "matrix_unify_branch_values": bool(self.matrix_unify_branch_values),
            "matrix_shared_b_calculation": bool(self.matrix_shared_b_calculation),
            "unify_branch_branches": unify_branches,
            "unify_branch_rows": unify_branch_rows,
            "matrix_b_shared_row": matrix_b_shared_row,
            "matrix_b_compact_columns": matrix_b_compact_columns,
            "range_ids": [r.id for r in ranges],
            "ranges": [{"name": r.name} for r in ranges],
            "levels": [
                {
                    "level_id": spec["level_id"],
                    "branch_id": spec["branch_id"],
                    "name": spec["name"],
                    "branch_name": spec["branch_name"],
                    "color": spec["color"],
                }
                for spec in level_branch_specs
            ],
            "rows": rows_out,
            "empty_message": _("No hay líneas con producto asociado."),
        }

    def _matrix_level_ranges_same_branch(self, lr, generic_link=False):
        """Niveles del mismo producto y rama (para unificación por rama en tablas A/B)."""
        LevelRange = self.env["quoter.product.level.range"]
        branch_id = lr.branch_id.id
        domain = [
            ("product_tmpl_id", "=", lr.product_tmpl_id.id),
            ("branch_id", "=", branch_id),
        ]
        if generic_link:
            domain.append(("area_id", "=", False))
        else:
            domain.append(("area_id", "=", self.id))
        return LevelRange.search(domain)

    def _quoter_line_for_product_tmpl(self, product_tmpl):
        self.ensure_one()
        if not product_tmpl:
            return self.env["quoter.service.line"]
        return self.line_ids.filtered(
            lambda l, t=product_tmpl: l.product_tmpl_id == t
        )[:1]

    def matrix_preview_write_unify_branch(self, line_id, branch_id, value):
        """Horas manuales en la tabla por rama (productos con «Unifica valor»)."""
        self.ensure_one()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(_("Solo el grupo Quoter - Gerente puede editar la matriz."))
        if not self.quoter_config_edit_mode:
            raise UserError(
                _(
                    "La configuración del área está bloqueada: solo un usuario del grupo "
                    "Quoter - Gerente puede abrir el editor de tabla desde la cabecera del área."
                )
            )
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise UserError(_("Valor numérico no válido.")) from None
        Policy = self.env["quoter.hours.policy"]
        try:
            Policy.validate_hours_non_negative(val, _("Horas"))
        except ValidationError as e:
            raise UserError(str(e)) from e
        line = self.env["quoter.service.line"].browse(int(line_id)).exists()
        if not line or line.area_id != self or not line.unify_value:
            raise UserError(_("Línea de producto no válida para la tabla por rama."))
        branch = self.env["quoter.area.branch"].browse(int(branch_id))
        if branch not in self._effective_branch_ids():
            raise UserError(_("La rama no pertenece al área."))
        ub = line.unify_branch_hour_ids.filtered(lambda h: h.branch_id == branch)[:1]
        if not ub:
            line._sync_unify_branch_hour_lines()
            ub = line.unify_branch_hour_ids.filtered(lambda h: h.branch_id == branch)[:1]
        if ub:
            ub.write({"hours": val})
        line._apply_unify_branch_hours_to_level_ranges(branch.id, val)
        if line.shared_b_calc and line.area_id.matrix_shared_b_calculation:
            line.area_id._recompute_shared_b_calc_outputs()
        return True

    def matrix_preview_write_cell(
        self,
        level_range_id,
        area_range_id,
        write_kind,
        value,
        complexity_level_id=0,
        branch_id=0,
    ):
        """Persistir celda desde la matriz JS (salida en regular; A y B en combinada)."""
        self.ensure_one()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(_("Solo el grupo Quoter - Gerente puede editar la matriz."))
        if not self.quoter_config_edit_mode:
            raise UserError(
                _(
                    "La configuración del área está bloqueada: solo un usuario del grupo "
                    "Quoter - Gerente puede abrir el editor de tabla desde la cabecera del área."
                )
            )
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise UserError(_("Valor numérico no válido.")) from None

        Policy = self.env["quoter.hours.policy"]
        hour_kinds = {
            "output",
            "matrix_a",
            "matrix_a_compact",
            "matrix_a_global",
            "matrix_b_single",
        }
        if write_kind in hour_kinds:
            try:
                Policy.validate_hours_non_negative(val, _("Horas"))
            except ValidationError as e:
                raise UserError(str(e)) from e
        elif write_kind in ("matrix_b", "matrix_b_single", "matrix_b_shared"):
            try:
                Policy.validate_matrix_b_factor_positive(
                    val, self.table_b_kind or "percent"
                )
            except ValidationError as e:
                raise UserError(str(e)) from e

        ar_id = int(area_range_id)
        ar_rec = self.env["quoter.area.complexity.range"].browse(ar_id)
        if not ar_rec or ar_rec not in self.area_range_ids:
            raise UserError(_("El rol no pertenece al área."))

        combined = self.hour_matrix_mode == "combined"

        if write_kind == "matrix_b_shared":
            if not combined:
                raise UserError(_("La tabla B solo aplica en modo combinado."))
            if not self.matrix_shared_b_calculation:
                raise UserError(_("Active «Productos varios en tabla B» en reglas de tablas."))
            self._sync_shared_matrix_b_rows()
            level_id = int(complexity_level_id or 0)
            br_id = int(branch_id or 0)
            try:
                if level_id:
                    if level_id not in self.complexity_level_ids.ids:
                        raise UserError(_("El nivel no pertenece al área."))
                    self._matrix_preview_set_level_b_exception(level_id, ar_id, val)
                elif br_id:
                    if br_id not in self._effective_branch_ids().ids:
                        raise UserError(_("La rama no pertenece al área."))
                    self._matrix_preview_set_branch_b_exception(br_id, ar_id, val)
                else:
                    sbrow = self.shared_matrix_b_ids.filtered(
                        lambda b: b.area_range_id.id == ar_id
                    )[:1]
                    if not sbrow:
                        raise UserError(_("No hay fila B compartida para ese rol."))
                    sbrow.write({"factor": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            self._recompute_shared_b_calc_outputs()
            return True

        LevelRange = self.env["quoter.product.level.range"]
        lr = LevelRange.browse(int(level_range_id)).exists()
        self._matrix_validate_level_range_for_area(lr)
        compact_a = self.table_a_layout == "compact"
        qline = self._quoter_line_for_product_tmpl(lr.product_tmpl_id)
        if qline and qline.shared_b_calc and write_kind in ("matrix_b", "matrix_b_single"):
            raise UserError(
                _(
                    "Este producto usa «Productos varios»: edite la fila homónima en tabla B."
                )
            )
        if qline and qline.unify_value and write_kind not in ("output",):
            raise UserError(
                _(
                    "Este producto usa «Unifica valor»: no se edita en tablas A ni B. "
                    "Use la tabla por rama (debajo de A) y la fila «Productos varios» en B."
                )
            )

        if write_kind == "output":
            if combined:
                if qline and qline.unify_value:
                    raise UserError(
                        _(
                            "«Unifica valor» no usa tabla resultado: edite horas por rama "
                            "y, si aplica, la fila «Productos varios» en tabla B."
                        )
                    )
                if qline and qline.shared_b_calc:
                    raise UserError(
                        _(
                            "La salida se calcula al editar la fila «Productos varios» en tabla B."
                        )
                    )
                raise UserError(
                    _("En modo combinado la salida se calcula desde las tablas A y B; edite esas tablas.")
                )
            val = self._apply_output_hours_minimum(val)
            sync_ctx = dict(self.env.context, quoter_sync_matrix_area_id=self.id)
            lr.with_context(sync_ctx)._sync_matrix_rows()
            out = lr.output_line_ids.filtered(lambda o: o.area_range_id.id == ar_id)[:1]
            if not out:
                O = self.env["quoter.product.level.range.output"]
                out = O.with_context(
                    quoter_allow_zero_hours=True, quoter_skip_output_hours_guard=True
                ).create(
                    {
                        "level_range_id": lr.id,
                        "area_range_id": ar_id,
                        "matrix_a_id": False,
                        "hours": val,
                    }
                )
            else:
                try:
                    out.with_context(quoter_skip_output_hours_guard=True).write({"hours": val})
                except ValidationError as e:
                    raise UserError(str(e)) from e
            return True

        if write_kind == "matrix_a_compact":
            if not combined:
                raise UserError(_("La tabla A solo aplica en modo combinado."))
            if not lr.matrix_a_ids:
                raise UserError(_("No hay filas de tabla A para este nivel."))
            try:
                lr.matrix_a_ids.write({"hours": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            return True

        if write_kind == "matrix_a_global":
            if not combined:
                raise UserError(_("La tabla A solo aplica en modo combinado."))
            if self.table_a_layout != "global":
                raise UserError(_("La edición global solo aplica con formato A unificada global."))
            line = self.line_ids.filtered(
                lambda l: l.product_tmpl_id == lr.product_tmpl_id
            )[:1]
            if line.is_generic_link:
                target_lrs = LevelRange.search(
                    [
                        ("area_id", "=", False),
                        ("product_tmpl_id", "=", lr.product_tmpl_id.id),
                    ]
                )
            else:
                target_lrs = LevelRange.search(
                    [
                        ("area_id", "=", self.id),
                        ("product_tmpl_id", "=", lr.product_tmpl_id.id),
                    ]
                )
            if not target_lrs:
                raise UserError(_("No hay filas de tabla A para el producto."))
            try:
                target_lrs.with_context(quoter_sync_matrix_area_id=self.id)._sync_matrix_rows()
                target_lrs.mapped("matrix_a_ids").write({"hours": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            return True

        if write_kind == "matrix_a":
            if not combined:
                raise UserError(_("La tabla A solo aplica en modo combinado."))
            if compact_a:
                raise UserError(_("Use la celda unificada de tabla A para este formato."))
            arow = lr.matrix_a_ids.filtered(lambda a: a.area_range_id.id == ar_id)[:1]
            if not arow:
                raise UserError(_("No hay fila de tabla A para ese rol."))
            try:
                generic = bool(qline and qline.is_generic_link)
                product_domain = [
                    ("product_tmpl_id", "=", lr.product_tmpl_id.id),
                    ("branch_id", "=", lr.branch_id.id),
                ]
                if generic:
                    product_domain.append(("area_id", "=", False))
                else:
                    product_domain.append(("area_id", "=", self.id))
                if self.matrix_a_unify_category_values:
                    lr.matrix_a_ids.write({"hours": val})
                elif self.matrix_a_unify_role_values:
                    target_lrs = LevelRange.search(product_domain)
                    target_rows = target_lrs.mapped("matrix_a_ids").filtered(
                        lambda r, aid=ar_id: r.area_range_id.id == aid
                    )
                    target_rows.write({"hours": val})
                else:
                    arow.write({"hours": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            return True

        if write_kind == "matrix_b":
            if not combined:
                raise UserError(_("La tabla B solo aplica en modo combinado."))
            brow = lr.matrix_b_ids.filtered(lambda b: b.area_range_id.id == ar_id)[:1]
            if not brow:
                raise UserError(_("No hay fila de tabla B para ese rol."))
            try:
                generic = bool(qline and qline.is_generic_link)
                product_domain = [
                    ("product_tmpl_id", "=", lr.product_tmpl_id.id),
                    ("branch_id", "=", lr.branch_id.id),
                ]
                if generic:
                    product_domain.append(("area_id", "=", False))
                else:
                    product_domain.append(("area_id", "=", self.id))
                if self.matrix_b_unify_role_values:
                    target_lrs = LevelRange.search(product_domain)
                    target_rows = target_lrs.mapped("matrix_b_ids").filtered(
                        lambda r, aid=ar_id: r.area_range_id.id == aid
                    )
                    target_rows.write({"factor": val})
                else:
                    brow.write({"factor": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            return True

        if write_kind == "matrix_b_single":
            if not combined:
                raise UserError(_("La tabla B solo aplica en modo combinado."))
            brow = lr.matrix_b_ids.filtered(lambda b: b.area_range_id.id == ar_id)[:1]
            if not brow:
                raise UserError(_("No hay fila de tabla B para ese rol."))
            try:
                brow.write({"factor": val})
            except ValidationError as e:
                raise UserError(str(e)) from e
            return True

        raise UserError(_("Tipo de escritura no reconocido."))

    def matrix_preview_set_option(self, option_name, enabled):
        self.ensure_one()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(_("Solo el grupo Quoter - Gerente puede modificar opciones de la matriz."))
        if not self.quoter_config_edit_mode:
            raise UserError(
                _(
                    "La configuración del área está bloqueada: solo un usuario del grupo "
                    "Quoter - Gerente puede abrir el editor de tabla desde la cabecera del área."
                )
            )
        allowed = {
            "matrix_a_unify_role_values",
            "matrix_a_hide_repeated_columns",
            "matrix_a_unify_category_values",
            "matrix_a_hide_repeated_category_columns",
            "matrix_b_unify_role_values",
            "matrix_b_hide_repeated_columns",
        }
        if option_name not in allowed:
            raise UserError(_("Opción de matriz no válida."))
        enabled = bool(enabled)
        vals = {option_name: enabled}
        if option_name == "matrix_a_unify_role_values" and not enabled:
            vals["matrix_a_hide_repeated_columns"] = False
        if option_name == "matrix_a_unify_category_values" and not enabled:
            vals["matrix_a_hide_repeated_category_columns"] = False
        if option_name == "matrix_b_unify_role_values" and not enabled:
            vals["matrix_b_hide_repeated_columns"] = False
        if option_name == "matrix_a_hide_repeated_columns" and enabled and not self.matrix_a_unify_role_values:
            vals["matrix_a_unify_role_values"] = True
        if (
            option_name == "matrix_a_hide_repeated_category_columns"
            and enabled
            and not self.matrix_a_unify_category_values
        ):
            vals["matrix_a_unify_category_values"] = True
        if option_name == "matrix_b_hide_repeated_columns" and enabled and not self.matrix_b_unify_role_values:
            vals["matrix_b_unify_role_values"] = True
        self.write(vals)
        return True

    def action_open_quoter_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Productos del cotizador"),
            "res_model": "quoter.service.line",
            "view_mode": "tree,form",
            "domain": [("area_id", "=", self.id)],
            "context": dict(self.env.context, default_area_id=self.id),
        }

    def _quoter_product_domain_for_area(self):
        self.ensure_one()
        general = self.env.ref("quoter.product_category_quoter_general", raise_if_not_found=False)
        domain = [("is_quoter_range_rate_product", "=", False), ("is_quoter_product", "=", True)]
        if self.product_category_id and general:
            domain += [
                "|",
                "&",
                ("product_tmpl_id.quoter_area_id", "=", self.id),
                ("categ_id", "=", self.product_category_id.id),
                ("categ_id", "=", general.id),
            ]
        elif self.product_category_id:
            domain += [
                ("product_tmpl_id.quoter_area_id", "=", self.id),
                ("categ_id", "=", self.product_category_id.id),
            ]
        else:
            domain.append(("product_tmpl_id.quoter_area_id", "=", self.id))
        return domain

    def action_open_quoter_products(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Productos del cotizador"),
            "res_model": "product.product",
            "view_mode": "tree,form",
            "domain": self._quoter_product_domain_for_area(),
            "context": self.env.context,
        }

    def _quoter_validate_config_before_lock(self):
        """Exige reglas al cerrar edición (p. ej. % B que sumen 100 en A unificada + B porcentaje)."""
        self.ensure_one()
        lrs = self.env["quoter.product.level.range"].search([("area_id", "=", self.id)])
        split = lrs.filtered(lambda r: r._matrix_b_percent_split_mode())
        if split:
            split._validate_matrix_b_percent_split_total_on_save()

    def _quoter_recompute_after_config_save(self):
        """Tras validar: recalcular horas de salida en modo combinado (A×B). Solo desde «Cerrar editor de tabla»."""
        self.ensure_one()
        if self.hour_matrix_mode != "combined":
            return
        lrs = self.env["quoter.product.level.range"].search([("area_id", "=", self.id)])
        lrs._apply_combined_final_all()

    def action_quoter_area_unlock_config(self):
        self.ensure_one()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(
                _("Solo los usuarios del grupo Quoter - Gerente pueden abrir o cerrar el editor de tabla.")
            )
        self._quoter_sync_level_range_matrix_rows()
        self.write({"quoter_config_edit_mode": True})
        return True

    def action_quoter_area_lock_config(self):
        self.ensure_one()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(
                _("Solo los usuarios del grupo Quoter - Gerente pueden abrir o cerrar el editor de tabla.")
            )
        self._quoter_validate_config_before_lock()
        self._quoter_recompute_after_config_save()
        self.write({"quoter_config_edit_mode": False})
        # True recarga el formulario en el cliente web (display_notification suele fallar en botones type="object").
        return True

    def _formula_config_applies_to_area(self, config):
        """True si la config de fórmula aplica a esta área (incl. productos genéricos)."""
        self.ensure_one()
        if not config:
            return False
        if config.area_id:
            return config.area_id == self
        tmpl = config.product_tmpl_id
        if not tmpl:
            return False
        return bool(
            self.line_ids.filtered(lambda line, t=tmpl: line.product_tmpl_id == t)
        )

    def _formula_matrix_read_only(self):
        self.ensure_one()
        can_edit = self.env.user.has_group("quoter.group_quoter_manager")
        return not self.quoter_config_edit_mode or not can_edit

    def _formula_matrix_row_payload(self, sline, config, ranges, Policy):
        is_fixed = config.tipo_calculo == "fija"
        volume = float(config.volumen_default or self.formula_test_volume or 1.0)
        use_vol = 0.0 if is_fixed else volume
        hours_map = config.compute_hours_by_range(use_vol, area=self)
        role_cells = []
        hours = []
        row_below_min = False
        config._sync_formula_range_lines(area=self)
        for ar in ranges:
            line_r = config.range_line_ids.filtered(
                lambda l, rid=ar.id: l.area_range_id.id == rid
            )[:1]
            if not line_r and not is_fixed:
                line_r = config.ensure_range_line(ar, area=self)
            h_raw = float(hours_map.get(ar.id, 0.0))
            h_out = Policy.apply_output_hours_minimum(
                h_raw, self.output_hours_minimum
            )
            hours.append(h_out)
            expr = (
                line_r.get_formula_expression_ui(volume=volume)
                if line_r
                else {"composed": "", "template": "inactive"}
            )
            cell_below = False
            if (
                not is_fixed
                and line_r
                and line_r.formula_active
                and line_r.formula_kind == "threshold"
            ):
                from .quoter_formula_product_config_param import PARAM_VOL_MIN

                vmin = line_r._get_param_value(PARAM_VOL_MIN, 1.0)
                if volume < vmin:
                    cell_below = True
                    row_below_min = True
            role_cells.append(
                {
                    "range_id": ar.id,
                    "range_line_id": int(line_r.id) if line_r else 0,
                    "service_line_id": sline.id,
                    "formula_active": bool(line_r and line_r.formula_active),
                    "formula_kind": line_r.formula_kind if line_r else False,
                    "horas_fijas": float(line_r.horas_fijas or 0.0) if line_r else 0.0,
                    "hours": h_out,
                    "formula_composed": expr.get("composed") or "",
                    "formula_expression": expr,
                    "below_vol_min": cell_below,
                }
            )
        return {
            "line_id": sline.id,
            "config_id": config.id,
            "product_name": sline.name or "",
            "referencia": config.referencia_volumen or "",
            "tipo_calculo": config.tipo_calculo,
            "formula_kind": config.formula_kind or "linear",
            "volume": volume,
            "below_vol_min": row_below_min,
            "is_fixed": is_fixed,
            "role_cells": role_cells,
            "hours": hours,
        }

    def get_formula_test_preview_data(self, test_volume=None):
        """Matriz JS del área: producto, volumen, roles (editor de tabla)."""
        self.ensure_one()
        if self.hour_matrix_mode != "formula":
            return {}
        FormulaConfig = self.env["quoter.formula.product.config"]
        Policy = self.env["quoter.hours.policy"]
        ranges = self.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))
        range_cols = [{"id": r.id, "name": r.name} for r in ranges]
        tipo_field = FormulaConfig._fields["tipo_calculo"]
        RangeLine = self.env["quoter.formula.product.config.range"]
        kind_field = RangeLine._fields["formula_kind"]
        rows = []
        for sline in self.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            if not sline.product_tmpl_id:
                continue
            config = FormulaConfig.get_config_for_template(sline.product_tmpl_id, self)
            if not config:
                continue
            rows.append(self._formula_matrix_row_payload(sline, config, ranges, Policy))
        label = self._quoter_formula_area_label()
        read_only = self._formula_matrix_read_only()
        return {
            "area_id": self.id,
            "area_name": label,
            "matrix_read_only": read_only,
            "matrix_editor_open": bool(self.quoter_config_edit_mode),
            "section_title": _("Matriz %(area)s — volumen y horas por rol") % {"area": label},
            "ranges": range_cols,
            "rows": rows,
            "tipo_options": [
                {"value": v, "label": lbl} for v, lbl in tipo_field.selection
            ],
            "formula_kind_options": [
                {"value": v, "label": lbl} for v, lbl in kind_field.selection
            ],
            "empty_message": _(
                "Agregue productos en la pestaña Productos (con el editor de tabla abierto)."
            ),
        }

    def matrix_preview_write_formula(
        self, service_line_id, write_kind, value, area_range_id=None, param_code=None
    ):
        """Persiste celda/campo de la matriz fórmula (editor de tabla del área)."""
        self.ensure_one()
        if self.hour_matrix_mode != "formula":
            return self.get_formula_test_preview_data()
        if not self.env.user.has_group("quoter.group_quoter_manager"):
            raise AccessError(_("Solo el grupo Quoter - Gerente puede editar la matriz."))
        if self._formula_matrix_read_only():
            raise UserError(
                _(
                    "Abra el editor de tabla desde la cabecera del área para editar "
                    "volúmenes y parámetros."
                )
            )
        line = self.line_ids.browse(int(service_line_id)).exists()
        if not line or line.area_id != self:
            raise UserError(_("La línea no pertenece a esta área."))
        if not line.product_tmpl_id:
            raise UserError(_("La línea no tiene producto."))
        FormulaConfig = self.env["quoter.formula.product.config"]
        config = FormulaConfig.get_config_for_template(line.product_tmpl_id, self)
        if not config:
            return self.get_formula_test_preview_data()

        write_kind = (write_kind or "").strip()
        if write_kind == "volume":
            try:
                config.write({"volumen_default": float(value or 0.0)})
            except (TypeError, ValueError):
                raise UserError(_("Volumen no válido.")) from None
        elif write_kind == "referencia":
            config.write({"referencia_volumen": value or ""})
        elif write_kind == "tipo_calculo":
            if value not in ("formula", "fija"):
                raise UserError(_("Tipo de cálculo no válido."))
            config.write({"tipo_calculo": value})
        elif write_kind == "formula_kind":
            if value not in ("linear", "threshold"):
                raise UserError(_("Plantilla de fórmula no válida."))
            config.write({"formula_kind": value})
            config.range_line_ids.write({"formula_kind": value})
            config.mapped("range_line_ids")._ensure_range_params()
        elif write_kind == "range_formula_kind":
            ar_id = int(area_range_id or 0)
            if ar_id not in self.area_range_ids.ids:
                raise UserError(_("El rol no pertenece al área."))
            if value not in ("linear", "threshold"):
                raise UserError(_("Plantilla de fórmula no válida."))
            rline = config.range_line_ids.filtered(
                lambda l, rid=ar_id: l.area_range_id.id == rid
            )[:1]
            if rline:
                rline.write({"formula_kind": value, "formula_active": True})
                rline._ensure_range_params()
        elif write_kind == "horas_fijas":
            ar_id = int(area_range_id or 0)
            if ar_id not in self.area_range_ids.ids:
                raise UserError(_("El rol no pertenece al área."))
            try:
                val = float(value or 0.0)
            except (TypeError, ValueError):
                raise UserError(_("Valor numérico no válido.")) from None
            try:
                self.env["quoter.hours.policy"].validate_hours_non_negative(
                    val, _("Horas")
                )
            except ValidationError as err:
                raise UserError(str(err)) from err
            rline = config.range_line_ids.filtered(
                lambda l, rid=ar_id: l.area_range_id.id == rid
            )[:1]
            if rline:
                rline.write({"horas_fijas": val})
        else:
            raise UserError(_("Tipo de actualización no reconocido."))

        return self.get_formula_test_preview_data()

    def _resolve_formula_range_line(self, service_line_id, area_range_id):
        self.ensure_one()
        if self._formula_matrix_read_only():
            raise UserError(
                _(
                    "Abra el editor de tabla desde la cabecera del área para editar "
                    "las fórmulas por rol."
                )
            )
        sline = self.line_ids.browse(int(service_line_id or 0)).exists()
        if not sline or sline.area_id != self:
            raise UserError(_("La línea no pertenece a esta área."))
        if not sline.product_tmpl_id:
            raise UserError(_("La línea no tiene producto."))
        ar = self.env["quoter.area.complexity.range"].browse(int(area_range_id or 0)).exists()
        if not ar or ar not in self.area_range_ids:
            raise UserError(_("El rol no pertenece al área."))
        FormulaConfig = self.env["quoter.formula.product.config"]
        config = FormulaConfig.get_config_for_template(sline.product_tmpl_id, self)
        if not config:
            raise UserError(_("Sin configuración de fórmula para este producto."))
        if config.tipo_calculo == "fija":
            raise UserError(_("El producto usa horas fijas, no fórmula por rol."))
        return config.ensure_range_line(ar, area=self)

    def get_formula_range_edit_data(self, service_line_id, area_range_id):
        """Datos para popup JS: solo la línea de fórmula editable."""
        self.ensure_one()
        rline = self._resolve_formula_range_line(service_line_id, area_range_id)
        volume = float(rline.config_id.volumen_default or self.formula_test_volume or 1.0)
        expr = rline.get_formula_expression_ui(volume=volume)
        return {
            "range_line_id": rline.id,
            "role_name": rline.area_range_id.name or "",
            "expression": expr,
        }

    def save_formula_range_edit(self, range_line_id, param_values):
        """Persiste parámetros desde el popup JS."""
        self.ensure_one()
        if self._formula_matrix_read_only():
            raise UserError(
                _(
                    "Abra el editor de tabla desde la cabecera del área para editar "
                    "las fórmulas por rol."
                )
            )
        rline = self.env["quoter.formula.product.config.range"].browse(
            int(range_line_id or 0)
        ).exists()
        if not rline or not self._formula_config_applies_to_area(rline.config_id):
            raise UserError(_("La configuración de rol no pertenece a esta área."))
        try:
            rline.apply_ui_param_values(param_values)
        except ValidationError as err:
            raise UserError(str(err)) from err
        return self.get_formula_test_preview_data()

    def get_formula_range_form_action(self, range_line_id):
        """Abre el formulario de fórmula del rol (popup desde la matriz JS)."""
        self.ensure_one()
        line = self.env["quoter.formula.product.config.range"].browse(
            int(range_line_id or 0)
        ).exists()
        area = line.config_id.area_id
        if not line or area != self:
            raise UserError(_("La configuración de rol no pertenece a esta área."))
        view = self.env.ref(
            "quoter.view_quoter_formula_product_config_range_form_popup",
            raise_if_not_found=False,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Fórmula — %(role)s") % {"role": line.area_range_id.name},
            "res_model": "quoter.formula.product.config.range",
            "res_id": line.id,
            "view_mode": "form",
            "target": "new",
            "views": [(view.id if view else False, "form")],
            "context": {
                "form_view_initial_mode": "edit",
                "default_config_id": line.config_id.id,
            },
        }

    def get_formula_area_config_preview_data(self, test_volume=None):
        """Alias RPC para la matriz del área."""
        return self.get_formula_test_preview_data(test_volume=test_volume)

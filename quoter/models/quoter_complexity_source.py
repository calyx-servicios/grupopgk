# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Datos objetivos que determinan el nivel de complejidad de un bloque de área.

- Convenios colectivos (Payroll): cada convenio tiene un nivel base y la combinación
  de convenios del cliente define el nivel final (Tabla #5).
- Tamaño de empresa (Tax / Auditoría): facturación del año anterior × industria,
  categorizada con los topes de la Resolución SICYPYME vigente; el tamaño se
  traduce a nivel con la tabla de cada área (Tabla #4 en Tax).
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

COMPANY_SIZE_SELECTION = [
    ("micro", "Micro"),
    ("small", "Pequeña"),
    ("medium", "Mediana"),
    ("large", "Grande"),
]


class QuoterComplexityLevelLaborAgreement(models.Model):
    _inherit = "quoter.complexity.level"

    labor_agreement_ok = fields.Boolean(
        string="Apto para convenio",
        default=False,
        help="Si está marcado, el nivel puede asignarse a los convenios colectivos (Payroll).",
    )

    @api.constrains("labor_agreement_ok")
    def _check_labor_agreement_ok_in_use(self):
        Agreement = self.env["quoter.labor.agreement"].with_context(active_test=False)
        for level in self.filtered(lambda lev: not lev.labor_agreement_ok):
            count = Agreement.search_count([("complexity_level_id", "=", level.id)])
            if count:
                raise ValidationError(
                    _(
                        "El nivel «%(level)s» está asignado a %(count)s convenios: "
                        "no puede dejar de ser apto para convenio."
                    )
                    % {"level": level.display_name, "count": count}
                )


class QuoterLaborAgreement(models.Model):
    _name = "quoter.labor.agreement"
    _description = "Convenio colectivo"
    _order = "name, id"

    name = fields.Char(
        string="Convenio",
        required=True,
    )
    complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel de complejidad",
        required=True,
        ondelete="restrict",
        domain=[("labor_agreement_ok", "=", True)],
        help="Nivel base del convenio. El nivel final de la cotización combina "
        "todos los convenios seleccionados. Solo niveles marcados como aptos para convenio.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "uniq_labor_agreement_name",
            "UNIQUE(name)",
            "Ya existe un convenio con ese nombre.",
        ),
    ]

    @api.constrains("complexity_level_id")
    def _check_complexity_level_labor_agreement_ok(self):
        for rec in self:
            if not rec.complexity_level_id.labor_agreement_ok:
                raise ValidationError(
                    _("El nivel «%s» no está marcado como apto para convenio.")
                    % rec.complexity_level_id.display_name
                )


class QuoterIndustry(models.Model):
    _name = "quoter.industry"
    _description = "Industria (categorización SICYPYME)"
    _order = "sequence, id"

    name = fields.Char(
        string="Industria",
        required=True,
        translate=True,
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )
    active = fields.Boolean(default=True)
    branch_id = fields.Many2one(
        comodel_name="quoter.area.branch",
        string="Rama",
        ondelete="restrict",
        help="Rama de la matriz de horas que corresponde a la industria en las áreas "
        "que cotizan por rama (Auditoría).",
    )
    threshold_ids = fields.One2many(
        comodel_name="quoter.sicypyme.threshold",
        inverse_name="industry_id",
        string="Topes de facturación",
    )

    def _quoter_threshold_for_date(self, date=None):
        """Topes vigentes a la fecha (el más reciente con vigencia <= fecha)."""
        self.ensure_one()
        thresholds = self.threshold_ids.sorted(key=lambda t: (t.date_from, t.id))
        date = fields.Date.to_date(date)
        if date:
            valid = thresholds.filtered(lambda t: t.date_from <= date)
            if valid:
                return valid[-1]
            return thresholds[:1]
        return thresholds[-1:]

    def _quoter_company_size(self, revenue, date=None):
        """Tamaño de empresa según facturación anual; False si faltan datos."""
        self.ensure_one()
        if not revenue or revenue <= 0:
            return False
        threshold = self._quoter_threshold_for_date(date)
        if not threshold:
            return False
        if revenue <= threshold.micro_max:
            return "micro"
        if revenue <= threshold.small_max:
            return "small"
        if revenue <= threshold.medium_max:
            return "medium"
        return "large"


class QuoterSicypymeThreshold(models.Model):
    _name = "quoter.sicypyme.threshold"
    _description = "Topes de facturación SICYPYME por industria"
    _order = "date_from desc, industry_id, id"

    industry_id = fields.Many2one(
        comodel_name="quoter.industry",
        string="Industria",
        required=True,
        ondelete="cascade",
        index=True,
    )
    date_from = fields.Date(
        string="Vigente desde",
        required=True,
        help="Los topes se actualizan anualmente: cargue una nueva fila por industria "
        "con la fecha de la nueva resolución en lugar de pisar la anterior.",
    )
    resolution = fields.Char(
        string="Resolución",
        help="Ej.: Resolución N° 1/2026 (SICYPYME).",
    )
    micro_max = fields.Float(
        string="Micro hasta",
        digits=(16, 2),
        required=True,
    )
    small_max = fields.Float(
        string="Pequeña hasta",
        digits=(16, 2),
        required=True,
    )
    medium_max = fields.Float(
        string="Mediana hasta",
        digits=(16, 2),
        required=True,
        help="Por encima de este importe la empresa es Grande.",
    )

    _sql_constraints = [
        (
            "uniq_sicypyme_threshold_industry_date",
            "UNIQUE(industry_id, date_from)",
            "Ya existen topes para esa industria con la misma fecha de vigencia.",
        ),
    ]

    @api.constrains("micro_max", "small_max", "medium_max")
    def _check_thresholds_ascending(self):
        for rec in self:
            if not 0 < rec.micro_max < rec.small_max < rec.medium_max:
                raise ValidationError(
                    _(
                        "Los topes de «%s» deben ser positivos y crecientes "
                        "(Micro < Pequeña < Mediana)."
                    )
                    % rec.industry_id.display_name
                )


class QuoterAreaSizeLevel(models.Model):
    _name = "quoter.area.size.level"
    _description = "Nivel de complejidad por tamaño de empresa"
    _order = "area_id, id"

    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        string="Área",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_size = fields.Selection(
        selection=COMPANY_SIZE_SELECTION,
        string="Tamaño",
        required=True,
    )
    complexity_level_id = fields.Many2one(
        comodel_name="quoter.complexity.level",
        string="Nivel de riesgo / complejidad",
        required=True,
        ondelete="restrict",
        help="Define las horas que se cotizan: si dos tamaños comparten nivel, "
        "cotizan las mismas horas.",
    )
    area_level_ids = fields.Many2many(
        comodel_name="quoter.complexity.level",
        related="area_id.complexity_level_ids",
        string="Niveles del área",
        readonly=True,
    )

    _sql_constraints = [
        (
            "uniq_area_size_level",
            "UNIQUE(area_id, company_size)",
            "Cada tamaño de empresa solo puede tener un nivel por área.",
        ),
    ]

    @api.constrains("area_id", "complexity_level_id")
    def _check_level_in_area(self):
        for rec in self:
            if rec.complexity_level_id not in rec.area_id._quoter_ordered_complexity_levels():
                raise ValidationError(
                    _("El nivel «%(level)s» no está configurado en el área «%(area)s».")
                    % {
                        "level": rec.complexity_level_id.display_name,
                        "area": rec.area_id.display_name,
                    }
                )

    def action_quoter_recompute_draft_levels(self):
        return self.mapped("area_id").action_quoter_recompute_draft_levels()


class QuoterProfessionalAreaComplexitySource(models.Model):
    _inherit = "quoter.professional.area"

    complexity_source = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("labor_agreement", "Convenios colectivos"),
            ("company_size", "Tamaño de empresa (facturación × industria)"),
        ],
        string="Determinación del nivel",
        default="manual",
        required=True,
        help="Manual: el cotizador elige el nivel. En los demás casos el nivel se "
        "calcula a partir de los datos del bloque y no puede editarse.",
    )
    size_level_ids = fields.One2many(
        comodel_name="quoter.area.size.level",
        inverse_name="area_id",
        string="Nivel por tamaño de empresa",
    )

    def _quoter_ordered_complexity_levels(self):
        """Niveles del área de menor a mayor complejidad (secuencia del nivel)."""
        self.ensure_one()
        if self.hour_matrix_mode == "formula_chain":
            levels = self.chain_complexity_increase_ids.mapped("complexity_level_id")
        else:
            levels = self.complexity_level_ids
        return levels.sorted(key=lambda lev: (lev.sequence, lev.id))

    def _quoter_level_for_labor_agreements(self, agreements):
        """Tabla #5: nivel final según los convenios del cliente.

        - Ninguno: nivel más bajo del área.
        - Uno: el nivel de ese convenio.
        - Dos: como mínimo el nivel medio, salvo que uno sea mayor.
        - Tres o más: siempre el nivel más alto.
        """
        self.ensure_one()
        levels = self._quoter_ordered_complexity_levels()
        if not levels:
            return self.env["quoter.complexity.level"]
        count = len(agreements)
        if not count:
            return levels[0]
        if count >= 3:
            return levels[-1]
        candidates = agreements.mapped("complexity_level_id")
        if count == 2 and len(levels) > 2:
            candidates |= levels[1]
        return max(candidates, key=lambda lev: (lev.sequence, lev.id))

    @api.constrains("complexity_source", "size_level_ids")
    def _check_size_levels_complete(self):
        """Por tamaño de empresa: los 4 tamaños tienen que tener nivel asignado."""
        sizes = {size for size, _label in COMPANY_SIZE_SELECTION}
        for area in self.filtered(lambda a: a.complexity_source == "company_size"):
            if set(area.size_level_ids.mapped("company_size")) != sizes:
                raise ValidationError(
                    _("En «%s» los 4 tamaños de empresa deben tener un nivel asignado.")
                    % area.display_name
                )

    def action_quoter_recompute_draft_levels(self):
        """Aplica la configuración actual del nivel a las cotizaciones en preparación.

        Solo toca bloques abiertos de cotizaciones «En preparación»: las que ya están en
        aprobación o enviadas al cliente conservan su nivel y sus horas.
        """
        areas = self.filtered(lambda a: a.complexity_source != "manual")
        blocks = self.env["quoter.sale.order.area"].search(
            [
                ("area_id", "in", areas.ids),
                ("state", "=", "draft"),
                ("order_id.is_quotation", "=", True),
                ("order_id.state", "in", ("draft", "sent")),
                ("order_id.quoter_workflow_state", "=", "en_preparacion"),
            ]
        )
        old_levels = {block.id: block.complexity_level_id for block in blocks}
        changed = blocks.with_context(
            quoter_recompute_derived_levels=True
        )._quoter_apply_derived_complexity_level()
        for block in changed:
            block._quoter_message_post_block(
                [
                    _("Nivel recalculado por cambio de configuración: %(old)s → %(new)s")
                    % {
                        "old": old_levels[block.id].display_name or "-",
                        "new": block.complexity_level_id.display_name,
                    }
                ]
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Recalcular cotizaciones en borrador"),
                "message": _(
                    "Cotizaciones en preparación revisadas: %(total)s. "
                    "Con cambio de nivel: %(changed)s."
                )
                % {
                    "total": len(blocks.mapped("order_id")),
                    "changed": len(changed.mapped("order_id")),
                },
                "type": "success",
                "sticky": False,
            },
        }

    def _quoter_level_for_company_size(self, company_size):
        self.ensure_one()
        row = self.size_level_ids.filtered(lambda r: r.company_size == company_size)[:1]
        return row.complexity_level_id

# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models

from .quoter_formula_product_config_param import (
    FORMULA_KIND_LINEAR_LABEL,
    FORMULA_KIND_THRESHOLD_LABEL,
)

_LEGACY_MINUTOS = ("minutos_ae", "minutos_sr", "minutos_gte", "minutos_socio")
_LEGACY_HORAS = ("horas_ae", "horas_sr", "horas_gte", "horas_socio")


class QuoterFormulaProductConfig(models.Model):
    _name = "quoter.formula.product.config"
    _description = "Configuración por volumen por producto (fórmula o horas fijas)"
    _rec_name = "referencia_volumen"

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Producto",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_id = fields.Many2one(
        comodel_name="quoter.professional.area",
        related="product_tmpl_id.quoter_area_id",
        store=True,
        readonly=True,
    )
    range_line_ids = fields.One2many(
        comodel_name="quoter.formula.product.config.range",
        inverse_name="config_id",
        string="Fórmulas por rol",
    )
    tipo_calculo = fields.Selection(
        selection=[
            ("formula", "Fórmula"),
            ("fija", "Horas fijas"),
        ],
        string="Tipo de cálculo",
        default="formula",
        required=True,
    )
    formula_kind = fields.Selection(
        selection=[
            ("linear", FORMULA_KIND_LINEAR_LABEL),
            ("threshold", FORMULA_KIND_THRESHOLD_LABEL),
        ],
        string="Plantilla por defecto (nuevos roles)",
        default="linear",
        help="Se aplica al crear líneas de rol nuevas; cada rol puede cambiar su plantilla.",
    )
    referencia_volumen = fields.Char(
        string="Referencia de volumen",
        translate=True,
        help="Texto que describe qué debe ingresar el usuario (ej. cantidad de facturas por mes).",
    )
    volumen_default = fields.Float(
        string="Volumen predeterminado",
        default=0.0,
        help="Valor sugerido al agregar el producto a una cotización.",
    )
    # Legacy (migración / formulario servicio); los cálculos usan parámetros por rol.
    valor_minimo_volumen = fields.Float(string="Volumen mínimo (legacy)", default=1.0)
    horas_si_menor = fields.Float(string="Horas si volumen menor (legacy)", default=1.0)
    horas_base_si_mayor = fields.Float(string="Horas desde el piso (legacy)", default=1.0)
    minutos_por_unidad_excedente = fields.Float(
        string="Min./unidad excedente (legacy)", default=1.0
    )
    minutos_ae = fields.Float(string="Minutos AE / unidad", default=0.0)
    minutos_sr = fields.Float(string="Minutos SR / unidad", default=0.0)
    minutos_gte = fields.Float(string="Minutos GTE / unidad", default=0.0)
    minutos_socio = fields.Float(string="Minutos Socio / unidad", default=0.0)
    horas_ae = fields.Float(string="Horas AE (fijas)", default=0.0)
    horas_sr = fields.Float(string="Horas SR (fijas)", default=0.0)
    horas_gte = fields.Float(string="Horas GTE (fijas)", default=0.0)
    horas_socio = fields.Float(string="Horas Socio (fijas)", default=0.0)

    _sql_constraints = [
        (
            "uniq_formula_config_product_tmpl",
            "UNIQUE(product_tmpl_id)",
            "Ya existe configuración por volumen para este producto.",
        )
    ]

    def _ordered_area_ranges(self, area=None):
        self.ensure_one()
        area = area or self.area_id
        if not area:
            return self.env["quoter.area.complexity.range"]
        return area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))

    def _sync_formula_range_lines(self, area=None):
        """Filas por rol del área."""
        RangeLine = self.env["quoter.formula.product.config.range"]
        for config in self:
            area = area or config.area_id
            if not area:
                continue
            ranges = config._ordered_area_ranges(area=area)
            keep_ids = set(ranges.ids)
            config.range_line_ids.filtered(
                lambda line, k=keep_ids: line.area_range_id.id not in k
            ).unlink()
            existing = {line.area_range_id.id: line for line in config.range_line_ids}
            legacy_min = [float(config[f] or 0.0) for f in _LEGACY_MINUTOS]
            legacy_horas = [float(config[f] or 0.0) for f in _LEGACY_HORAS]
            default_kind = config.formula_kind or "linear"
            for idx, ar in enumerate(ranges):
                line = existing.get(ar.id)
                if not line:
                    mins = legacy_min[idx] if idx < len(legacy_min) else 0.0
                    RangeLine.create(
                        {
                            "config_id": config.id,
                            "area_range_id": ar.id,
                            "formula_kind": default_kind,
                            "formula_active": bool(mins or default_kind),
                            "minutos_por_unidad": mins,
                            "horas_fijas": legacy_horas[idx]
                            if idx < len(legacy_horas)
                            else 0.0,
                        }
                    )
                else:
                    if idx < len(legacy_min) and not line.minutos_por_unidad and legacy_min[idx]:
                        line.minutos_por_unidad = legacy_min[idx]
                    if idx < len(legacy_horas) and not line.horas_fijas and legacy_horas[idx]:
                        line.horas_fijas = legacy_horas[idx]

    def ensure_range_line(self, area_range, area=None):
        """Garantiza la fila de fórmula para un rol del área."""
        self.ensure_one()
        area = area or self.area_id
        self._sync_formula_range_lines(area=area)
        line = self.range_line_ids.filtered(
            lambda l, ar=area_range: l.area_range_id == ar
        )[:1]
        if not line:
            line = self.env["quoter.formula.product.config.range"].create(
                {
                    "config_id": self.id,
                    "area_range_id": area_range.id,
                    "formula_kind": self.formula_kind or "linear",
                    "formula_active": True,
                }
            )
        line._ensure_range_params()
        return line

    def compute_hours_by_range(self, volume, area=None):
        """Devuelve {area_range_id: horas} — una fórmula independiente por rol."""
        self.ensure_one()
        area = area or self.area_id
        self._sync_formula_range_lines(area=area)
        out = {}
        for ar in self._ordered_area_ranges(area=area):
            line = self.range_line_ids.filtered(
                lambda l, rid=ar.id: l.area_range_id.id == rid
            )[:1]
            out[ar.id] = line.compute_hours(volume) if line else 0.0
        return out

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_formula_range_lines()
        records.mapped("range_line_ids")._ensure_range_params()
        return records

    def write(self, vals):
        res = super().write(vals)
        if set(vals.keys()) & set(_LEGACY_MINUTOS + _LEGACY_HORAS):
            self._sync_formula_range_lines()
        if "formula_kind" in vals:
            for config in self:
                for line in config.range_line_ids:
                    if len(line.param_ids) <= 1:
                        line.write({"formula_kind": config.formula_kind})
        return res

    @api.model
    def get_config_for_template(self, product_tmpl, area=None):
        if not product_tmpl:
            return self.browse()
        config = self.search([("product_tmpl_id", "=", product_tmpl.id)], limit=1)
        if config:
            config._sync_formula_range_lines(area=area or product_tmpl.quoter_area_id)
            config.mapped("range_line_ids")._ensure_range_params()
            return config
        if not area and product_tmpl.quoter_area_id:
            area = product_tmpl.quoter_area_id
        if not area or area.hour_matrix_mode != "formula":
            return self.browse()
        config = self.create(
            {
                "product_tmpl_id": product_tmpl.id,
                "tipo_calculo": "formula",
                "formula_kind": "linear",
                "referencia_volumen": product_tmpl.name or _("Volumen"),
            }
        )
        config._sync_formula_range_lines(area=area)
        config.mapped("range_line_ids")._ensure_range_params()
        return config

    @api.model
    def sync_from_service_line_vals(self, product_tmpl, vals):
        """Crea o actualiza config desde valores del formulario de línea de servicio."""
        if not product_tmpl:
            return
        config = self.get_config_for_template(product_tmpl)
        if not config:
            return
        keys = [
            "tipo_calculo",
            "formula_kind",
            "referencia_volumen",
            "volumen_default",
            "valor_minimo_volumen",
            "horas_si_menor",
            "horas_base_si_mayor",
            "minutos_por_unidad_excedente",
        ] + list(_LEGACY_MINUTOS) + list(_LEGACY_HORAS)
        write_vals = {k: vals[k] for k in keys if k in vals}
        if write_vals:
            config.write(write_vals)
            config._sync_formula_range_lines()

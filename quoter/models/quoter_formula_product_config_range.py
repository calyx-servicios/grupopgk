# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .quoter_formula_product_config_param import (
    FORMULA_KIND_LINEAR_LABEL,
    FORMULA_KIND_THRESHOLD_LABEL,
    FORMULA_LABEL_VOLUME,
    FORMULA_PARAM_SYMBOL,
    PARAM_HOURS_BASE,
    PARAM_HOURS_BELOW,
    PARAM_MIN_EXCESS,
    PARAM_MINUTES_LINEAR,
    PARAM_VOL_MIN,
)


class QuoterFormulaProductConfigRange(models.Model):
    _name = "quoter.formula.product.config.range"
    _description = "Fórmula o horas fijas por rol (config fórmula)"
    _order = "area_range_sequence, id"

    config_id = fields.Many2one(
        comodel_name="quoter.formula.product.config",
        string="Configuración",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_range_id = fields.Many2one(
        comodel_name="quoter.area.complexity.range",
        string="Rol del área",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_range_sequence = fields.Integer(
        related="area_range_id.sequence",
        store=True,
        readonly=True,
    )
    formula_active = fields.Boolean(
        string="Usar fórmula",
        default=True,
        help="Desactivado: este rol no aporta horas por fórmula (celda vacía).",
    )
    formula_kind = fields.Selection(
        selection=[
            ("linear", FORMULA_KIND_LINEAR_LABEL),
            ("threshold", FORMULA_KIND_THRESHOLD_LABEL),
        ],
        string="Plantilla",
        default="linear",
        required=True,
    )
    param_ids = fields.One2many(
        comodel_name="quoter.formula.product.config.param",
        inverse_name="range_id",
        string="Parámetros",
        copy=True,
    )
    formula_composed = fields.Char(
        string="Fórmula compuesta",
        compute="_compute_formula_composed",
    )
    minutos_por_unidad = fields.Float(
        string="Minutos / unidad (legacy)",
        default=0.0,
        help="Obsoleto: use parámetros de fórmula por rol.",
    )
    horas_fijas = fields.Float(
        string="Horas fijas",
        default=0.0,
        help="Tipo de cálculo «Horas fijas» a nivel producto.",
    )

    _sql_constraints = [
        (
            "uniq_cfg_area_range",
            "UNIQUE(config_id, area_range_id)",
            "Ya hay parámetros para ese rol en esta configuración.",
        )
    ]

    @api.constrains("minutos_por_unidad", "horas_fijas")
    def _check_non_negative(self):
        for row in self:
            if (row.minutos_por_unidad or 0.0) < 0.0 or (row.horas_fijas or 0.0) < 0.0:
                raise ValidationError(_("Los valores no pueden ser negativos."))

    @api.constrains("area_range_id", "config_id")
    def _check_range_in_area(self):
        for row in self:
            area = row.config_id.area_id
            if not area or not row.area_range_id:
                continue
            if row.area_range_id not in area.area_range_ids:
                raise ValidationError(
                    _("El rol debe pertenecer a los roles configurados en el área.")
                )

    def _get_param_record(self, code):
        self.ensure_one()
        return self.param_ids.filtered(lambda p, c=code: p.code == c)[:1]

    def _get_param_value(self, code, default=1.0):
        self.ensure_one()
        param = self._get_param_record(code)
        if param:
            return float(param.value or 0.0)
        if code == PARAM_MINUTES_LINEAR and self.minutos_por_unidad:
            return float(self.minutos_por_unidad)
        return default

    def _set_param_value(self, code, value):
        self.ensure_one()
        val = float(value or 0.0)
        param = self._get_param_record(code)
        if param:
            param.write({"value": val})
        else:
            self.env["quoter.formula.product.config.param"].create(
                {"range_id": self.id, "code": code, "value": val}
            )
        if code == PARAM_MINUTES_LINEAR:
            self.minutos_por_unidad = val

    def apply_ui_param_values(self, param_values):
        """Guarda valores desde el popup JS ({code: value} o lista de dicts)."""
        self.ensure_one()
        self._ensure_range_params()
        Policy = self.env["quoter.hours.policy"]
        items = param_values or []
        if isinstance(items, dict):
            items = [{"code": k, "value": v} for k, v in items.items()]
        for item in items:
            code = (item.get("code") or "").strip()
            if not code:
                continue
            try:
                val = float(item.get("value") or 0.0)
            except (TypeError, ValueError):
                raise ValidationError(_("Valor numérico no válido.")) from None
            if code in (PARAM_HOURS_BELOW, PARAM_HOURS_BASE):
                Policy.validate_hours_non_negative(val, _("Horas"))
            elif val < 0:
                raise ValidationError(_("Los parámetros no pueden ser negativos."))
            self._set_param_value(code, val)
        return True

    def _ensure_range_params(self):
        Param = self.env["quoter.formula.product.config.param"]
        for line in self:
            if line.config_id.tipo_calculo != "formula" or not line.formula_active:
                continue
            codes = (
                [PARAM_MINUTES_LINEAR]
                if line.formula_kind == "linear"
                else [
                    PARAM_VOL_MIN,
                    PARAM_HOURS_BELOW,
                    PARAM_HOURS_BASE,
                    PARAM_MIN_EXCESS,
                ]
            )
            allowed = set(codes)
            line.param_ids.filtered(
                lambda p, a=allowed: p.code not in a
            ).unlink()
            existing = {p.code for p in line.param_ids}
            seq = 10
            for code in codes:
                if code not in existing:
                    val = 1.0
                    if code == PARAM_MINUTES_LINEAR and line.minutos_por_unidad:
                        val = float(line.minutos_por_unidad)
                    Param.create(
                        {
                            "range_id": line.id,
                            "code": code,
                            "value": val,
                            "sequence": seq,
                        }
                    )
                else:
                    line._get_param_record(code).write({"sequence": seq})
                seq += 10

    @api.model
    def _threshold_hours_from_params(self, volume, v_min, h_below, h_base, m_excess):
        v = float(volume or 0.0)
        vmin = float(v_min or 0.0)
        if v < vmin:
            return float(h_below or 0.0)
        base = float(h_base or 0.0)
        extra = float(m_excess or 0.0)
        return base + ((v - vmin) * extra) / 60.0 if extra else base

    def compute_hours(self, volume):
        """Horas de este rol para el volumen dado."""
        self.ensure_one()
        if self.config_id.tipo_calculo == "fija":
            return float(self.horas_fijas or 0.0)
        if not self.formula_active:
            return 0.0
        self._ensure_range_params()
        v = float(volume or 0.0)
        if self.formula_kind == "linear":
            minutes = self._get_param_value(PARAM_MINUTES_LINEAR, 1.0)
            return (v * minutes) / 60.0 if minutes else 0.0
        return self._threshold_hours_from_params(
            v,
            self._get_param_value(PARAM_VOL_MIN, 1.0),
            self._get_param_value(PARAM_HOURS_BELOW, 1.0),
            self._get_param_value(PARAM_HOURS_BASE, 1.0),
            self._get_param_value(PARAM_MIN_EXCESS, 1.0),
        )

    def _format_num(self, n):
        x = float(n or 0.0)
        if x == int(x):
            return str(int(x))
        return ("%.4f" % x).rstrip("0").rstrip(".")

    def get_formula_expression_ui(self, volume=None):
        """Partes para tooltip / vista (etiquetas VOLUMEN y nº en plantilla)."""
        self.ensure_one()
        config = self.config_id
        v = float(
            volume
            if volume is not None
            else (config.volumen_default or 1.0)
        )
        sym = FORMULA_PARAM_SYMBOL
        vol_lbl = FORMULA_LABEL_VOLUME
        if config.tipo_calculo == "fija":
            return {
                "template": "fixed",
                "volume": v,
                "result_hours": float(self.horas_fijas or 0.0),
                "parts": [],
                "composed": "",
            }
        if not self.formula_active:
            return {
                "template": "inactive",
                "volume": v,
                "result_hours": 0.0,
                "parts": [],
                "composed": "",
            }
        self._ensure_range_params()
        result = self.compute_hours(v)
        if self.formula_kind == "linear":
            minutes = self._get_param_value(PARAM_MINUTES_LINEAR, 1.0)
            parts = [
                {"type": "text", "content": "=("},
                {"type": "text", "content": vol_lbl},
                {"type": "text", "content": "×"},
                {
                    "type": "param",
                    "code": PARAM_MINUTES_LINEAR,
                    "value": minutes,
                    "label": sym,
                },
                {"type": "text", "content": ")/60"},
            ]
            composed = "=(%s×%s)/60" % (vol_lbl, self._format_num(minutes))
            return {
                "template": "linear",
                "volume": v,
                "result_hours": result,
                "parts": parts,
                "composed": composed,
            }
        v1 = self._get_param_value(PARAM_VOL_MIN, 1.0)
        h1 = self._get_param_value(PARAM_HOURS_BELOW, 1.0)
        h2 = self._get_param_value(PARAM_HOURS_BASE, 1.0)
        m1 = self._get_param_value(PARAM_MIN_EXCESS, 1.0)
        parts = [
            {"type": "text", "content": "=SI("},
            {"type": "text", "content": vol_lbl},
            {"type": "text", "content": "<"},
            {"type": "param", "code": PARAM_VOL_MIN, "value": v1, "label": sym},
            {"type": "text", "content": ";"},
            {"type": "param", "code": PARAM_HOURS_BELOW, "value": h1, "label": sym},
            {"type": "text", "content": ";("},
            {"type": "param", "code": PARAM_HOURS_BASE, "value": h2, "label": sym},
            {"type": "text", "content": "+(("},
            {"type": "text", "content": vol_lbl},
            {"type": "text", "content": "-"},
            {"type": "param", "code": PARAM_VOL_MIN, "value": v1, "label": sym},
            {"type": "text", "content": ")×"},
            {"type": "param", "code": PARAM_MIN_EXCESS, "value": m1, "label": sym},
            {"type": "text", "content": ")/60))"},
        ]
        composed = "=SI(%s<%s;%s;(%s+((%s-%s)×%s)/60)))" % (
            vol_lbl,
            self._format_num(v1),
            self._format_num(h1),
            self._format_num(h2),
            vol_lbl,
            self._format_num(v1),
            self._format_num(m1),
        )
        return {
            "template": "threshold",
            "volume": v,
            "result_hours": result,
            "parts": parts,
            "composed": composed,
        }

    @api.depends(
        "formula_kind",
        "formula_active",
        "param_ids.value",
        "config_id.volumen_default",
        "config_id.tipo_calculo",
    )
    def _compute_formula_composed(self):
        for line in self:
            vol = line.config_id.volumen_default or 1.0
            line.formula_composed = line.get_formula_expression_ui(
                volume=vol
            ).get("composed", "")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_range_params()
        return records

    def write(self, vals):
        res = super().write(vals)
        if set(vals.keys()) & {"formula_kind", "formula_active"}:
            self._ensure_range_params()
        return res

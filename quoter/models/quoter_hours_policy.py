# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, models
from odoo.exceptions import ValidationError


class QuoterHoursPolicy(models.AbstractModel):
    """Helpers de validación de horas/factores (uso vía env['quoter.hours.policy'])."""

    _name = "quoter.hours.policy"
    _description = "Política de validación de horas del cotizador"

    @api.model
    def _quoter_skip_strict_hours_validation(self):
        return bool(self.env.context.get("quoter_allow_zero_hours"))

    @api.model
    def validate_hours_strictly_positive(self, value, label=None):
        """Horas editadas por usuario: deben ser > 0 (no 0 ni negativas)."""
        if self._quoter_skip_strict_hours_validation():
            return float(value or 0.0)
        hours = float(value or 0.0)
        if hours <= 0.0:
            field = label or _("Horas")
            raise ValidationError(_("%s deben ser mayores a cero.") % field)
        return hours

    @api.model
    def validate_hours_non_negative(self, value, label=None):
        """Horas por rol: permiten 0; no negativas (la suma > 0 se valida al guardar)."""
        if self._quoter_skip_strict_hours_validation():
            return float(value or 0.0)
        hours = float(value or 0.0)
        if hours < 0.0:
            field = label or _("Horas")
            raise ValidationError(_("%s no pueden ser negativas.") % field)
        return hours

    @api.model
    def validate_quotation_line_hours_sum(self, total, product_name=None):
        """Suma de horas por rol en línea: permite 0; solo bloquea negativos."""
        if self._quoter_skip_strict_hours_validation():
            return float(total or 0.0)
        hours = float(total or 0.0)
        if hours < 0.0:
            if product_name:
                raise ValidationError(
                    _(
                        "La suma de horas por rol no puede ser negativa en la línea «%s»."
                    )
                    % product_name
                )
            raise ValidationError(
                _("La suma de horas por rol no puede ser negativa.")
            )
        return hours

    @api.model
    def validate_adjustment_hours_nonzero(self, value, range_name=None):
        """Ajuste por rol: permite 0 y negativas; el tope se valida en la línea (base + ajuste)."""
        if self._quoter_skip_strict_hours_validation():
            return float(value or 0.0)
        return float(value or 0.0)

    @api.model
    def apply_output_hours_minimum(self, hours, minimum):
        """Piso de horas en tabla resultado: si minimum > 0 y hours < minimum, devuelve minimum."""
        h = float(hours or 0.0)
        m = float(minimum or 0.0)
        if m > 0.0 and h < m:
            return m
        return h

    @api.model
    def validate_matrix_b_factor_positive(self, value, table_b_kind="percent"):
        if self._quoter_skip_strict_hours_validation():
            return float(value or 0.0)
        factor = float(value or 0.0)
        if factor <= 0.0:
            if table_b_kind == "percent":
                raise ValidationError(
                    _("El porcentaje de la tabla B debe ser mayor a cero.")
                )
            raise ValidationError(_("El factor de la tabla B debe ser mayor a cero."))
        return factor

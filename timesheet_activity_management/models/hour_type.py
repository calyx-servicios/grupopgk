from odoo import fields, models, _
from odoo.exceptions import ValidationError


class TimesheetHourType(models.Model):
    _name = "timesheet.hour.type"
    _description = "Tipo de hora"
    _order = "sequence, name"

    name = fields.Char(string="Tipo de hora", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    include_in_management_report = fields.Boolean(
        string="Incluir en reporte de gestión",
        default=False,
    )
    _sql_constraints = [
        (
            "timesheet_hour_type_name_unique",
            "unique(name)",
            "Ya existe un tipo de hora con ese nombre.",
        ),
    ]

    def unlink(self):
        used_count = self.env["account.analytic.line"].sudo().search_count([
            ("hour_type_id", "in", self.ids),
        ])
        if used_count:
            raise ValidationError(_(
                "No se pueden eliminar tipos de hora utilizados. "
                "Archívelos para conservar la clasificación histórica."
            ))
        return super().unlink()

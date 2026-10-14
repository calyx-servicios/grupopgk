from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


HOUR_ENTRY_FIELDS = (
    "project_id",
    "task_id",
    "employee_id",
    "timesheet_id",
    "unit_amount",
    "hour_type_id",
    "activity_date",
    "name",
    "move_id",
    "consolidation_line",
)


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    hour_type_id = fields.Many2one(
        "timesheet.hour.type",
        string="Tipo de hora",
        ondelete="restrict",
        index=True,
        copy=True,
    )
    activity_date = fields.Date(
        string="Fecha de actividad",
        index=True,
        copy=True,
    )
    hour_type_in_management_report = fields.Boolean(
        related="hour_type_id.include_in_management_report",
        string="Tipo incluido en reporte de gestión",
    )

    def _is_real_hour_entry(self):
        self.ensure_one()
        if (
            not self.project_id
            or not self.unit_amount
            or self.move_id
        ):
            return False
        if "consolidation_line" in self._fields and self.consolidation_line:
            return False
        allocation_project = self.env.ref(
            "timesheet_odoo.hours_to_allocate",
            raise_if_not_found=False,
        )
        return not allocation_project or self.project_id != allocation_project

    @api.constrains(*HOUR_ENTRY_FIELDS)
    def _check_hour_entry_classification(self):
        for line in self:
            if not line._is_real_hour_entry():
                continue
            if not line.hour_type_id:
                raise ValidationError(_(
                    "Toda carga de horas debe indicar un tipo de hora."
                ))
            if not line.activity_date:
                raise ValidationError(_(
                    "Toda carga de horas debe indicar la fecha de actividad."
                ))
            if (
                line.hour_type_id.include_in_management_report
                and not (line.name or "").strip().strip("/")
            ):
                raise ValidationError(_(
                    "La descripción es obligatoria para los tipos incluidos "
                    "en el reporte de gestión."
                ))
            if line.timesheet_id and (
                line.activity_date < line.timesheet_id.start_of_period
                or line.activity_date > line.timesheet_id.end_of_period
            ):
                raise ValidationError(_(
                    "La fecha de actividad debe estar dentro del período "
                    "SIGE de la carga."
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            type_id = vals.get("hour_type_id")
            if type_id and not self.env["timesheet.hour.type"].browse(
                type_id
            ).active:
                raise ValidationError(_(
                    "No se puede asignar un tipo de hora archivado a una "
                    "carga nueva."
                ))
        return super().create(vals_list)

    def write(self, vals):
        type_id = vals.get("hour_type_id")
        if type_id and any(line.hour_type_id.id != type_id for line in self):
            if not self.env["timesheet.hour.type"].browse(type_id).active:
                raise ValidationError(_(
                    "No se puede asignar un tipo de hora archivado a una "
                    "carga."
                ))
        return super().write(dict(vals))

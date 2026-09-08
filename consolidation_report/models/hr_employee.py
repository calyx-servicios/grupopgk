from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    no_timesheet = fields.Boolean(
        string='Does Not Use Timesheets',
        default=False,
        help='El informe de consolidación ignora las horas de este empleado. '
             'Para quienes no cargan parte de horas y cuyo costo llega por '
             'factura de proveedor.',
    )

    @api.constrains('identification_id')
    def _check_identification_id(self):
        for rec in self:
            if not rec.identification_id:
                continue
            value = rec.identification_id.strip()
            if not value.isdigit() or len(value) != 11:
                raise ValidationError(
                    "El número de identificación debe ser numérico, "
                    "sin guiones y tener exactamente 11 dígitos (CUIT)."
                )
            duplicate = self.search([
                ('id', '!=', rec.id),
                ('identification_id', '=', value),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "El número de identificación '%s' ya está asignado al empleado %s." %
                    (value, duplicate.name)
                )

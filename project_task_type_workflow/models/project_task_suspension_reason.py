from odoo import fields, models


class ProjectTaskSuspensionReason(models.Model):
    """Predefined reasons for suspending a project task."""

    _name = "project.task.suspension.reason"
    _description = "Motivo de suspensión de tarea"
    _order = "sequence, id"

    name = fields.Char(
        string="Motivo",
        required=True,
        translate=True,
    )
    is_other = fields.Boolean(
        string="Es 'Otro' (requiere detalle)",
        default=False,
        help="Indica si este motivo requiere completar obligatoriamente el "
        "detalle libre al suspender la tarea.",
    )
    active = fields.Boolean(
        string="Activo",
        default=True,
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )

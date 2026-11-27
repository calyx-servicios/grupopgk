from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProjectTaskEvent(models.Model):
    """Traceability history of significant events on project tasks."""

    _name = "project.task.event"
    _description = "Historial de evento de tarea"
    _order = "date desc, id desc"

    task_id = fields.Many2one(
        comodel_name="project.task",
        string="Tarea",
        required=True,
        ondelete="cascade",
        index=True,
    )
    project_id = fields.Many2one(
        comodel_name="project.project",
        related="task_id.project_id",
        store=True,
        readonly=True,
        index=True,
    )
    date = fields.Datetime(
        string="Fecha y hora",
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Usuario",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
    )
    event_type = fields.Selection(
        selection=[
            ("testing_failed", "Testing Failed"),
            ("suspended", "Suspendida"),
        ],
        string="Tipo de evento",
        required=True,
        index=True,
    )
    error_target = fields.Selection(
        selection=[
            ("code", "Error de código"),
            ("deploy", "Error de deploy"),
        ],
        string="A qué apunta el error",
    )
    suspension_reason_id = fields.Many2one(
        comodel_name="project.task.suspension.reason",
        string="Motivo de suspensión",
    )
    suspension_reason_detail = fields.Text(
        string="Detalle del motivo",
    )
    description = fields.Text(
        string="Descripción del caso",
        required=True,
    )
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="project_task_event_ir_attachment_rel",
        column1="event_id",
        column2="attachment_id",
        string="Adjuntos",
    )
    origin_stage_id = fields.Many2one(
        comodel_name="project.task.type",
        string="Etapa origen",
        readonly=True,
    )
    destination_stage_id = fields.Many2one(
        comodel_name="project.task.type",
        string="Etapa destino",
        readonly=True,
    )

    @api.constrains("event_type", "error_target", "description", "suspension_reason_id", "suspension_reason_detail")
    def _check_event_consistency(self):
        """Ensure required fields are supplied depending on event type."""
        for event in self:
            if event.event_type == "testing_failed":
                if not event.error_target:
                    raise ValidationError(_(
                        "Para un fallo de testing debe indicar a qué apunta "
                        "el error (código o deploy)."
                    ))
                if not (event.description and event.description.strip()):
                    raise ValidationError(_(
                        "La descripción del caso es obligatoria en Testing Failed."
                    ))
            elif event.event_type == "suspended":
                if not event.suspension_reason_id:
                    raise ValidationError(_(
                        "Debe seleccionar un motivo de suspensión."
                    ))
                if event.suspension_reason_id.is_other and not (
                    (event.suspension_reason_detail and event.suspension_reason_detail.strip())
                    or (event.description and event.description.strip())
                ):
                    raise ValidationError(_(
                        "Al seleccionar «Otro» motivo, debe completar el detalle obligatorio."
                    ))

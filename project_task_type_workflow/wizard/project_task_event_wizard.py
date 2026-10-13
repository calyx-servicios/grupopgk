from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTaskEventWizard(models.TransientModel):
    """Collect required information before moving a task to Testing Failed or Suspendida."""

    _name = "project.task.event.wizard"
    _description = "Asistente de registro de eventos de tarea"

    task_id = fields.Many2one(
        comodel_name="project.task",
        string="Tarea",
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
        readonly=True,
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
    is_other_reason = fields.Boolean(
        related="suspension_reason_id.is_other",
        string="Es 'Otro' motivo",
        readonly=True,
    )
    suspension_reason_detail = fields.Text(
        string="Detalle del motivo (obligatorio para «Otro»)",
    )
    description = fields.Text(
        string="Descripción del caso",
    )
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="project_task_event_wizard_ir_attachment_rel",
        column1="wizard_id",
        column2="attachment_id",
        string="Adjuntos",
    )

    @api.onchange("event_type", "suspension_reason_id")
    def _onchange_reason(self):
        if self.event_type == "suspended" and self.suspension_reason_id and not self.description:
            self.description = self.suspension_reason_id.name

    def action_confirm(self):
        """Validate inputs, record the task event, and update the task stage."""
        self.ensure_one()
        task = self.task_id

        if self.event_type == "testing_failed":
            if not self.error_target:
                raise UserError(_("Debe indicar obligatoriamente a qué apunta el error (código o deploy)."))
            if not (self.description and self.description.strip()):
                raise UserError(_("La descripción del caso es obligatoria para registrar Testing Failed."))
            target_stage = task._workflow_stage("stage_testing_failed")
            if not target_stage:
                raise UserError(_("No se encontró la etapa canónica «Testing Failed»."))
        elif self.event_type == "suspended":
            if not self.suspension_reason_id:
                raise UserError(_("Debe seleccionar obligatoriamente un motivo de suspensión."))
            if self.is_other_reason and not (
                (self.suspension_reason_detail and self.suspension_reason_detail.strip())
                or (self.description and self.description.strip())
            ):
                raise UserError(_("Al seleccionar «Otro» motivo, debe completar obligatoriamente el detalle."))
            target_stage = task._workflow_stage("stage_suspendida")
            if not target_stage:
                raise UserError(_("No se encontró la etapa canónica «Suspendida»."))
            if not self.description:
                self.description = (
                    self.suspension_reason_detail
                    if self.is_other_reason
                    else self.suspension_reason_id.name
                )
        else:
            raise UserError(_("Tipo de evento no reconocido."))

        event_vals = {
            "task_id": task.id,
            "event_type": self.event_type,
            "error_target": self.error_target if self.event_type == "testing_failed" else False,
            "suspension_reason_id": self.suspension_reason_id.id if self.event_type == "suspended" else False,
            "suspension_reason_detail": self.suspension_reason_detail if self.event_type == "suspended" else False,
            "description": self.description or self.suspension_reason_detail or "",
            "origin_stage_id": task.stage_id.id,
            "destination_stage_id": target_stage.id,
        }
        if self.attachment_ids:
            event_vals["attachment_ids"] = [(6, 0, self.attachment_ids.ids)]

        self.env["project.task.event"].create(event_vals)

        task.with_context(skip_event_check=True).write({
            "stage_id": target_stage.id,
        })

        return {"type": "ir.actions.act_window_close"}

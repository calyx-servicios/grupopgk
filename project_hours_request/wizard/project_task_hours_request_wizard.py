from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTaskHoursRequestWizard(models.TransientModel):
    """Collect an additional-hours request for one task segment."""

    _name = 'project.task.hours.request.wizard'
    _description = 'Wizard para solicitar horas adicionales a Contratos'

    task_id = fields.Many2one(
        string="Tarea",
        comodel_name="project.task",
        required=True,
        domain=[('parent_id', '=', False)],
    )
    segment = fields.Selection(
        selection=[
            ("development", "Desarrollo"),
            ("deploy", "Deploy"),
            ("functional_test", "Funcional Pruebas"),
        ],
        string="Tramo",
        required=True,
    )
    current_hours_cap = fields.Float(
        string="Tope de horas actual",
        related="task_id.hours_cap",
        readonly=True
    )
    requested_hours = fields.Float(
        string="Horas adicionales solicitadas",
        required=True
    )
    reason = fields.Text(
        string="Motivo",
        required=True
    )

    @api.onchange("task_id")
    def _onchange_task_id(self):
        """Default the request segment from the task's current stage."""
        if self.task_id:
            stage_type = self.task_id.stage_id.get_timesheet_stage_type()
            if stage_type in dict(self._fields["segment"].selection):
                self.segment = stage_type

    def action_confirm(self):
        """Create and open the additional-hours request."""
        self.ensure_one()
        if self.task_id.parent_id:
            raise UserError(_(
                "Las horas adicionales solo pueden solicitarse desde la "
                "tarea padre."
            ))
        request = self.env["project.task.hours.request"].create({
            "task_id": self.task_id.id,
            "segment": self.segment,
            "requested_hours": self.requested_hours,
            "reason": self.reason,
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Solicitud de horas adicionales",
            "res_model": "project.task.hours.request",
            "view_mode": "form",
            "res_id": request.id,
        }

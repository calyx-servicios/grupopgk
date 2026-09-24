from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProjectTask(models.Model):
    """Apply planning and lifecycle rules to project tasks."""

    _inherit = 'project.task'

    development_card = fields.Boolean(
        string="Tarjeta de Desarrollo",
    )
    estimated_dev_hours = fields.Float(
        string="Horas Estimadas Dev",
    )
    estimated_deploy_hours = fields.Float(
        string="Horas Estimada Deploy",
    )
    estimated_functional_test_hours = fields.Float(
        string="Horas Estimada Funcional Pruebas",
    )
    margin_hours = fields.Float(
        string="Horas Margen",
    )
    can_edit_estimated_hours = fields.Boolean(
        compute="_compute_can_edit_estimated_hours",
    )

    def _get_planned_hours(self, segment):
        """Return planned hours for a controlled timesheet segment."""
        self.ensure_one()
        field_by_segment = {
            "development": "estimated_dev_hours",
            "deploy": "estimated_deploy_hours",
            "functional_test": "estimated_functional_test_hours",
        }
        return self[field_by_segment[segment]]

    def _get_consumed_hours(self, segment):
        """Return hours charged to one stored segment."""
        self.ensure_one()
        lines = self.env["account.analytic.line"].search([
            ("task_id", "=", self.id),
            ("timesheet_segment", "=", segment),
        ])
        return sum(lines.mapped("unit_amount"))

    def _get_approved_margin_hours(self, segment):
        """Return approved margin allocated to a segment."""
        self.ensure_one()
        requests = self.hours_request_ids.filtered(
            lambda request: (
                request.state == "approved"
                and request.margin_authorization
                and request.segment == segment
            )
        )
        return sum(requests.mapped("requested_hours"))

    @api.model
    def _get_segment_label(self, segment):
        """Return the user-facing label for a segment."""
        labels = {
            "development": _("Desarrollo"),
            "deploy": _("Deploy"),
            "functional_test": _("Funcional Pruebas"),
        }
        return labels[segment]

    hours_cap = fields.Float(
        string="Tope de horas"
    )
    hours_request_ids = fields.One2many(
        string="Solicitudes de horas adicionales",
        comodel_name="project.task.hours.request",
        inverse_name="task_id"
    )
    hours_request_count = fields.Integer(
        string="Cantidad de solicitudes",
        compute="_compute_hours_request_count"
    )

    @api.depends("hours_request_ids")
    def _compute_hours_request_count(self):
        """Count additional-hours requests for the task."""
        for rec in self:
            rec.hours_request_count = len(rec.hours_request_ids)

    def _compute_can_edit_estimated_hours(self):
        """Allow estimates to be edited only by the project's tech lead."""
        current_user = self.env.user
        for task in self:
            task.can_edit_estimated_hours = (
                task.project_id.technical_leader_id == current_user
            )

    def _check_estimated_hours_editor(self, vals, project=None):
        """Reject estimate changes made by users other than the tech lead."""
        estimated_fields = {
            "development_card",
            "estimated_dev_hours",
            "estimated_deploy_hours",
            "estimated_functional_test_hours",
            "margin_hours",
        }
        if not estimated_fields.intersection(vals) or self.env.su:
            return
        projects = project or self.mapped("project_id")
        for task_project in projects:
            if task_project.technical_leader_id != self.env.user:
                raise UserError(_(
                    "Solo el Líder Técnico del proyecto puede editar las "
                    "horas estimadas y el margen."
                ))

    @api.constrains(
        "estimated_dev_hours",
        "estimated_deploy_hours",
        "estimated_functional_test_hours",
        "margin_hours",
    )
    def _check_nonnegative_estimated_hours(self):
        """Prevent negative planned-hour values."""
        for task in self:
            if any(
                hours < 0
                for hours in (
                    task.estimated_dev_hours,
                    task.estimated_deploy_hours,
                    task.estimated_functional_test_hours,
                    task.margin_hours,
                )
            ):
                raise ValidationError(_(
                    "Las horas estimadas y el margen no pueden ser negativos."
                ))

    @api.model_create_multi
    def create(self, vals_list):
        """Allow task creation; estimate permissions apply on later edits."""
        return super().create(vals_list)

    def write(self, vals):
        """Enforce estimate permissions and prevent empty finalization."""
        target_project = self.env["project.project"].browse(
            vals.get("project_id")
        )
        self._check_estimated_hours_editor(
            vals,
            project=target_project or self.mapped("project_id"),
        )
        if vals.get("stage_id"):
            target_stage = self.env["project.task.type"].browse(
                vals["stage_id"]
            )
            if target_stage.get_timesheet_stage_type() == "done":
                empty_tasks = self.filtered(
                    lambda task: (
                        sum(task.timesheet_ids.mapped("unit_amount")) <= 0
                    )
                )
                if empty_tasks:
                    raise UserError(_(
                        "No se puede finalizar una tarea sin horas cargadas."
                    ))
        result = super().write(vals)
        if {
            "development_card",
            "estimated_dev_hours",
            "estimated_deploy_hours",
            "estimated_functional_test_hours",
            "margin_hours",
        }.intersection(vals):
            self.timesheet_ids._validate_development_caps()
            for task in self.filtered("development_card"):
                approved_margin = sum(
                    task.hours_request_ids.filtered(
                        lambda request: (
                            request.state == "approved"
                            and request.margin_authorization
                        )
                    ).mapped("requested_hours")
                )
                if approved_margin > task.margin_hours:
                    raise UserError(_(
                        "El Margen no puede ser menor que las horas "
                        "adicionales "
                        "ya aprobadas."
                    ))
        return result

    def action_open_hours_request_wizard(self):
        """Open the additional-hours request wizard."""
        self.ensure_one()
        stage_type = self.stage_id.get_timesheet_stage_type()
        segment = (
            stage_type
            if stage_type in (
                "development",
                "deploy",
                "functional_test",
            )
            else False
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Solicitar horas adicionales",
            "res_model": "project.task.hours.request.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_id": self.id,
                "default_segment": segment,
            },
        }

    def action_view_hours_requests(self):
        """Open additional-hours requests linked to the task."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Solicitudes de horas adicionales",
            "res_model": "project.task.hours.request",
            "view_mode": "tree,form",
            "domain": [("task_id", "=", self.id)],
            "context": {"default_task_id": self.id},
        }

import unicodedata

from odoo import api, fields, models


class ProjectTaskType(models.Model):
    """Classify task stages for timesheet controls."""

    _inherit = "project.task.type"

    timesheet_stage_type = fields.Selection(
        selection=[
            ("automatic", "Automático según el nombre"),
            ("unrestricted", "Sin control"),
            ("pending", "Pendiente (bloquea horas)"),
            ("development", "Desarrollo"),
            ("deploy", "Deploy"),
            ("functional_test", "Funcional Pruebas"),
            ("uat_support", "UAT/Soporte"),
            ("done", "Finalizada (bloquea horas)"),
        ],
        string="Tramo para control de horas",
        default="automatic",
        required=True,
    )

    def get_timesheet_stage_type(self):
        """Return the configured type or infer it from known stage names."""
        if not self:
            return "unrestricted"
        self.ensure_one()
        inferred_type = self._infer_timesheet_stage_type()
        canonical = self.env.ref(
            "project_task_type_workflow.stage_uat_cliente",
            raise_if_not_found=False,
        )
        if self == canonical or inferred_type == "uat_support":
            return "uat_support"
        if self.timesheet_stage_type == "automatic":
            return inferred_type
        # A stage named Pendiente/Finalizada must block even if set to no control.
        if (
            self.timesheet_stage_type == "unrestricted"
            and inferred_type in ("pending", "done")
        ):
            return inferred_type
        return self.timesheet_stage_type

    def _infer_timesheet_stage_type(self):
        """Infer the timesheet stage type from the stage name."""
        normalized_name = unicodedata.normalize("NFKD", self.name or "")
        normalized_name = "".join(
            character
            for character in normalized_name
            if not unicodedata.combining(character)
        ).strip().lower()
        inferred_types = {
            "pendiente": "pending",
            "desarrollo": "development",
            "deploy a staging": "deploy",
            "deploy a produccion": "deploy",
            "pruebas": "functional_test",
            "funcional pruebas": "functional_test",
            "uat cliente": "uat_support",
            "finalizada": "done",
            "finalizado": "done",
        }
        return inferred_types.get(normalized_name, "unrestricted")

    @api.model
    def configure_uat_stage(self) -> None:
        """Configure only the canonical UAT segment on install and upgrade."""
        stage = self.env.ref(
            "project_task_type_workflow.stage_uat_cliente",
            raise_if_not_found=False,
        )
        if stage:
            stage.write({"timesheet_stage_type": "uat_support"})
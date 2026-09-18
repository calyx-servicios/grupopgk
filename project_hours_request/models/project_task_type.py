import unicodedata

from odoo import fields, models


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
        if self.timesheet_stage_type != "automatic":
            return self.timesheet_stage_type

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
            "finalizada": "done",
            "finalizado": "done",
        }
        return inferred_types.get(normalized_name, "unrestricted")
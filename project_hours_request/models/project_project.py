from odoo import fields, models


class ProjectProject(models.Model):
    """Expose the project's additional-hours request history."""

    _inherit = "project.project"

    hours_request_ids = fields.One2many(
        comodel_name="project.task.hours.request",
        inverse_name="project_id",
        string="Solicitudes de horas adicionales",
    )
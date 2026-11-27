from odoo import fields, models


class ProjectTaskAcceptanceCriteria(models.Model):
    _name = "project.task.acceptance.criteria"
    _description = "Criterio de aceptación de tarea"
    _order = "sequence, id"

    task_id = fields.Many2one(
        comodel_name="project.task",
        string="Tarea",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Criterio", required=True)
    is_validated = fields.Boolean(string="Validado")

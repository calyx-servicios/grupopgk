from odoo import fields, models

# Canonical stages seeded by data/project_task_type_data.xml, auto-linked to every
# project so they're selectable regardless of which projects created them first.
CANONICAL_STAGE_XMLIDS = [
    "stage_pendiente_functional",
    "stage_en_curso",
    "stage_finalizada_functional",
    "stage_pendiente_development",
    "stage_estimacion",
    "stage_desestimada",
    "stage_lista_para_hacer",
    "stage_desarrollo",
    "stage_suspendida",
    "stage_deploy_staging",
    "stage_deploy_failed_staging",
    "stage_pruebas",
    "stage_testing_failed",
    "stage_testing_ok",
    "stage_uat_cliente",
    "stage_deploy_produccion",
    "stage_deploy_failed_produccion",
    "stage_revision_general_funcional",
    "stage_finalizada_development",
]


class ProjectTaskType(models.Model):
    """Classify which task types (Gestión/Funcional, Desarrollo) may use each stage."""

    _inherit = "project.task.type"

    task_type_scope = fields.Selection(
        selection=[
            ("functional", "Gestión/Funcional"),
            ("development", "Desarrollo"),
        ],
        string="Tipo de tarea habilitado",
        help="Determina para qué tipo de tarea está disponible este estado.",
    )

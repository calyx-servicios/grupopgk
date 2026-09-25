from odoo import api, SUPERUSER_ID


CANONICAL_STAGES = {
    "stage_pendiente_functional": ("Pendiente", 10, "functional", False, False),
    "stage_en_curso": ("En curso", 20, "functional", False, False),
    "stage_finalizada_functional": ("Finalizada", 30, "functional", True, True),
    "stage_pendiente_development": ("Pendiente", 10, "development", False, False),
    "stage_estimacion": ("Estimación", 20, "development", False, False),
    "stage_desestimada": ("Desestimada", 30, "development", True, True),
    "stage_lista_para_hacer": ("Lista para hacer", 40, "development", False, False),
    "stage_desarrollo": ("Desarrollo", 50, "development", False, False),
    "stage_suspendida": ("Suspendida", 60, "development", False, False),
    "stage_deploy_staging": ("Deploy a Staging", 70, "development", False, False),
    "stage_deploy_failed_staging": ("Deploy Failed Staging", 80, "development", False, False),
    "stage_pruebas": ("Pruebas", 90, "development", False, False),
    "stage_testing_failed": ("Testing Failed", 100, "development", False, False),
    "stage_testing_ok": ("Testing OK", 110, "development", False, False),
    "stage_uat_cliente": ("UAT Cliente", 120, "development", False, False),
    "stage_deploy_produccion": ("Deploy a Producción", 130, "development", False, False),
    "stage_deploy_failed_produccion": ("Deploy Failed Producción", 140, "development", False, False),
    "stage_revision_general_funcional": ("Revisión general funcional", 150, "development", False, False),
    "stage_finalizada_development": ("Finalizada", 160, "development", True, True),
}


def _get_or_create_stage(env, xmlid, values):
    """Return the canonical stage record, creating its XML ID if needed."""
    module = "project_task_type_workflow"
    stage = env.ref(f"{module}.{xmlid}", raise_if_not_found=False)
    if not stage:
        stage = env["project.task.type"].create(values)
        env["ir.model.data"].create({
            "module": module,
            "name": xmlid,
            "model": "project.task.type",
            "res_id": stage.id,
            "noupdate": True,
        })
    else:
        stage.write(values)
    return stage


def migrate(cr, version):
    """Split shared task stages by task type and migrate old development cards."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        UPDATE project_task_type
           SET task_type_scope = NULL
         WHERE task_type_scope = 'both'
    """)
    stages = env["project.task.type"]
    for xmlid, (name, sequence, scope, fold, is_closed) in CANONICAL_STAGES.items():
        stages |= _get_or_create_stage(env, xmlid, {
            "name": name,
            "sequence": sequence,
            "task_type_scope": scope,
            "fold": fold,
            "is_closed": is_closed,
        })
    projects = env["project.project"].search([])
    if stages and projects:
        stages.write({"project_ids": [(4, project.id) for project in projects]})

    if "development_card" in env["project.task"]._fields:
        cr.execute("""
            UPDATE project_task
               SET task_type = 'development'
             WHERE development_card IS TRUE
               AND (task_type IS NULL OR task_type = 'unclassified')
        """)

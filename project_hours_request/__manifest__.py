{
    "name": "Project Hours Cap Request",
     "summary": """
         Solicitud y aprobación de ampliación del tope de horas de tareas
     """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["mbravo"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Project",
    "version": "15.0.1.1.1",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "hr_timesheet",
        "mail",
        "project_contrated_hours",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizard/project_task_hours_request_wizard_view.xml",
        "views/project_task_hours_request_views.xml",
        "views/project_task_views.xml",
        "views/project_task_type_views.xml",
        "views/project_project_views.xml",
    ],
}

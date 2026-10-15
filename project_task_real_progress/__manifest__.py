{
    "name": "Project Task Real Progress",
    "summary": """
        Avance real por subtareas y criterios de aceptación, separado del
        consumo de horas
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["mbravo"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Project",
    "version": "15.0.1.0.1",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "hr_timesheet",
        "project_task_type_workflow",
        "project_task_description_checklist",
    ],
    "data": [
        "views/project_task_views.xml",
        "views/project_task_report_views.xml",
    ],
    "post_init_hook": "post_init_hook",
}

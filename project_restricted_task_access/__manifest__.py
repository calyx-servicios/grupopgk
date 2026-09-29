{
    "name": "Project Restricted Task Access",
    "summary": """
        Acceso restringido a Proyecto para Funcional y Developer: solo sus
        tareas asignadas, agrupadas por proyecto, sin la ficha de Proyecto
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["mbravo"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Project",
    "version": "15.0.1.0.0",
    "development_status": "Beta",
    "application": False,
    "installable": True,
    "depends": [
        "project",
        "hr_timesheet",
    ],
    "data": [
        "security/security.xml",
        "views/project_task_views.xml",
    ],
}

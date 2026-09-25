{
    "name": "Project Task Type Workflow",
    "summary": """
        Tipo de tarea (Gestión/Funcional, Desarrollo) que determina los estados
        habilitados y el responsable jerárquico máximo
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
        "project",
        "project_contrated_hours",
    ],
    "data": [
        "data/project_task_type_data.xml",
        "views/project_task_type_views.xml",
        "views/project_task_views.xml",
    ],
    "post_init_hook": "post_init_hook",
}

{
    "name": "Project Task Description Checklist",
    "summary": """
       Descripción obligatoria en tareas (cambios trackeados en el chatter),
       con checklist de Criterio de aceptación en pestaña propia
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
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/project_task_views.xml",
    ],
}

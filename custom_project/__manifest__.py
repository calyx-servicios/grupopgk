{
    "name": "Custom Project",
    "summary": """
        This module customize project
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["AgusCFx"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.2",
    "application": False,
    "installable": True,
    "depends": [
        'project',
        'hr_timesheet'
    ],
    "data": [
        'views/project_project_views.xml',
        'views/project_task_views.xml'
    ]
}
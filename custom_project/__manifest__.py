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
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        'project'
    ],
    "data": [
        'views/project_project_views.xml'
    ]
}
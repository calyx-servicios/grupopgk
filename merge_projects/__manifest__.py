{
    "name": "Merge Projects",
    "summary": """
        This module allows you to merge several projects into one for the same clients.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "project_for_each_sol",
    ],
    "data": [
        "security/permissions.xml",
        "views/action_menu.xml",
        "wizards/merge_project_wizard.xml",
    ]
}

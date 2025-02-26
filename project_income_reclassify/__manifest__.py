{
    "name": "Project Income Reclassify",
    "summary": """
       This module allows to reclassify the income of a project
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["fcarlini"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Project",
    "version": "15.0.0.0.1",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "project"
    ],
    "data": [
        "views/project_income_reclassify_views.xml",
        "wizard/project_income_reclassify_wizard_view.xml",
        "security/ir.model.access.csv"
    ],
}

{
    "name": "Project contrated hours",
    "summary": """
        This module add contrated hours from sale order lines
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["AgusCFx"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.1",
    "application": False,
    "installable": True,
    "depends": [
        'sale',
        'project'
    ],
    "data": [
        "views/sale_order_line_views.xml",
        "views/project_project_views.xml"
    ]
}

{
    "name": "Project contrated hours",
    "summary": """
        This module add contrated hours from sale order lines
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["AgusCFx", "EstebanSuarez21"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.3.1.3",
    "application": False,
    "installable": True,
    "depends": [
        'sale', 'project', 'sale_timesheet', 'account_sale_timesheet', 'analytic'
    ],
    "data": [
        "views/sale_order_line_views.xml",
        "views/project_project_views.xml",
        "views/account_analytic_group_form_view.xml"
    ]
}
